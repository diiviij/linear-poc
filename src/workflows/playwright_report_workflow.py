import base64
import io
import json
import re
import zipfile
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from config import JENKINS_URL, JENKINS_USER, JENKINS_API_TOKEN, JENKINS_JOB_NAME, WORKFLOW_STATES
from services import ai_service
from services.issue_service import IssueService
from services.project_service import ProjectService

STATE_FILE = Path(__file__).resolve().parent.parent.parent / "state" / "playwright_report_state.json"

REPORT_BLOB_PATTERN = re.compile(
    r'<template id="playwrightReportBase64">data:application/zip;base64,([^<]+)</template>'
)

issue_service = IssueService()
project_service = ProjectService()

_auth = HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN)


def _load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _build_artifact_url(build_number, relative_path):
    return f"{JENKINS_URL}/job/{JENKINS_JOB_NAME}/{build_number}/artifact/{relative_path}"


def _fetch_report(build_number):
    """Downloads the Playwright HTML report and extracts its embedded report.json — the report
    embeds the full structured test results (including which failures are final vs. flaky-but-
    recovered-on-retry) as a base64 zip inside the HTML itself, so no HTML/DOM parsing is needed."""
    resp = requests.get(_build_artifact_url(build_number, "playwright-report/index.html"), auth=_auth)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()

    match = REPORT_BLOB_PATTERN.search(resp.text)
    if not match:
        return None

    raw_zip = base64.b64decode(match.group(1))
    zf = zipfile.ZipFile(io.BytesIO(raw_zip))
    return json.loads(zf.read("report.json"))


def _final_failures(report):
    """Tests whose outcome is 'unexpected' — Playwright's own label for a test that failed on
    its last attempt (excludes 'flaky' tests that failed then passed on retry)."""
    failures = []
    for file_entry in report.get("files", []):
        for test in file_entry.get("tests", []):
            if test.get("outcome") != "unexpected":
                continue

            attachments = test["results"][-1]["attachments"] if test.get("results") else []
            error_attachment = next((a for a in attachments if a["name"] == "error-context"), None)
            if not error_attachment:
                continue

            screenshot_attachment = next((a for a in attachments if a["name"] == "screenshot"), None)
            trace_attachment = next((a for a in attachments if a["name"] == "trace"), None)

            full_title = " > ".join(test.get("path", []) + [test["title"]])
            failures.append(
                {
                    "test_id": test["testId"],
                    "title": full_title,
                    "error_context_path": error_attachment["path"],
                    "screenshot_path": screenshot_attachment["path"] if screenshot_attachment else None,
                    "trace_path": trace_attachment["path"] if trace_attachment else None,
                }
            )
    return failures


def _fetch_error_context(build_number, relative_path):
    resp = requests.get(
        _build_artifact_url(build_number, f"playwright-report/{relative_path}"), auth=_auth
    )
    resp.raise_for_status()
    return resp.text


def _fetch_binary_artifact(build_number, relative_path):
    resp = requests.get(
        _build_artifact_url(build_number, f"playwright-report/{relative_path}"), auth=_auth
    )
    resp.raise_for_status()
    return resp.content


def _upload_attachments_markdown(build_number, failure):
    """Uploads the failure's screenshot/trace to Linear's own storage (so they're viewable by
    anyone with issue access, without needing Jenkins credentials) and returns a markdown snippet
    embedding/linking them."""
    parts = []

    if failure["screenshot_path"]:
        screenshot_bytes = _fetch_binary_artifact(build_number, failure["screenshot_path"])
        filename = failure["screenshot_path"].rsplit("/", 1)[-1]
        asset_url = issue_service.upload_file("image/png", filename, screenshot_bytes)
        parts.append(f"![Screenshot at failure]({asset_url})")

    if failure["trace_path"]:
        trace_bytes = _fetch_binary_artifact(build_number, failure["trace_path"])
        filename = failure["trace_path"].rsplit("/", 1)[-1]
        asset_url = issue_service.upload_file("application/zip", filename, trace_bytes)
        parts.append(f"[Trace file]({asset_url}) (open with `npx playwright show-trace`)")

    return "\n\n".join(parts)


def _find_existing_ticket(test_id, open_issues):
    for issue in open_issues:
        if test_id in (issue.get("description") or ""):
            return issue
    return None


def _passed_test_ids(report):
    return {
        test["testId"]
        for file_entry in report.get("files", [])
        for test in file_entry.get("tests", [])
        if test.get("outcome") == "expected"
    }


def _check_recoveries(build_number, report, open_issues):
    """If a test that previously failed (and has an open ticket) passes in this build, move that
    ticket to QA for human sign-off rather than closing it automatically."""
    for test_id in _passed_test_ids(report):
        existing = _find_existing_ticket(test_id, open_issues)
        if not existing:
            continue

        issue_service.update_issue(existing["id"], state_id=WORKFLOW_STATES["QA"])
        issue_service.add_comment(
            existing["id"],
            f"Test now passes in build #{build_number} — moved to QA for verification.",
        )


def poll():
    """Checks new Jenkins builds' Playwright reports for final (non-flaky) test failures, has the
    model judge whether each is a real application bug, and files/comments a Linear ticket only
    for ones judged real. Already-processed builds are tracked in a local state file."""
    state = _load_state()

    resp = requests.get(
        f"{JENKINS_URL}/job/{JENKINS_JOB_NAME}/api/json",
        params={"tree": "builds[number,result]"},
        auth=_auth,
    )
    resp.raise_for_status()
    builds = resp.json().get("builds", [])

    for build in builds:
        number = str(build["number"])
        if number in state or build.get("result") is None:
            continue

        report = _fetch_report(build["number"])
        if report:
            open_issues = project_service.get_open_issues()
            _process_failures(build["number"], report, open_issues)
            _check_recoveries(build["number"], report, open_issues)

        state[number] = {"processed": True}

    _save_state(state)


def _process_failures(build_number, report, open_issues):
    for failure in _final_failures(report):
        error_context = _fetch_error_context(build_number, failure["error_context_path"])
        analysis = ai_service.analyze_test_failure(failure["title"], error_context)

        if not analysis["is_real_issue"]:
            continue

        existing = _find_existing_ticket(failure["test_id"], open_issues)
        report_url = _build_artifact_url(build_number, "playwright-report/index.html")
        attachments_markdown = _upload_attachments_markdown(build_number, failure)

        if existing:
            issue_service.add_comment(
                existing["id"],
                f"Failed again in build #{build_number}: {report_url}\n\n"
                f"{analysis['reasoning']}\n\n{attachments_markdown}",
            )
            continue

        description = (
            f"{analysis['description']}\n\n"
            f"{attachments_markdown}\n\n"
            f"---\nPlaywright test ID: {failure['test_id']}\n"
            f"Report: {report_url}"
        )
        issue_service.create_issue(failure["title"], description, analysis["priority"])
