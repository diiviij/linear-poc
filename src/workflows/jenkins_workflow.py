import json
import re
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from config import (
    JENKINS_URL,
    JENKINS_USER,
    JENKINS_API_TOKEN,
    JENKINS_JOB_NAME,
    WORKFLOW_STATES,
)
from services.issue_service import IssueService

ISSUE_ID_PATTERN = re.compile(r"\b([A-Z]{2,10}-\d+)\b")

# If CI fails on an issue already past active development, treat it as a regression
# and pull the issue back into "In Progress" rather than leaving it in QA/Done.
REGRESSION_STATE_TYPES = {"started", "completed"}

STATE_FILE = Path(__file__).resolve().parent.parent.parent / "state" / "jenkins_poll_state.json"

issue_service = IssueService()


def _load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _extract_issue_identifier(build):
    params = {}
    for action in build.get("actions", []):
        for param in action.get("parameters", []):
            params[param.get("name")] = param.get("value")

    haystack = " ".join(str(v) for v in params.values() if v)
    match = ISSUE_ID_PATTERN.search(haystack)
    return match.group(1) if match else None


def poll():
    """Checks a Jenkins job's build history for finished builds and posts the result to
    the linked Linear issue (extracted from build parameters, e.g. a branch name param).
    Already-processed builds are tracked in a local state file, safe to run on an interval."""
    state = _load_state()

    response = requests.get(
        f"{JENKINS_URL}/job/{JENKINS_JOB_NAME}/api/json",
        params={"tree": "builds[number,result,url,actions[parameters[name,value]]]"},
        auth=HTTPBasicAuth(JENKINS_USER, JENKINS_API_TOKEN),
    )
    response.raise_for_status()
    builds = response.json().get("builds", [])

    for build in builds:
        number = str(build["number"])
        if number in state:
            continue
        if build.get("result") is None:
            continue  # still running

        identifier = _extract_issue_identifier(build)
        if identifier:
            _handle_build(identifier, build)

        state[number] = {"processed": True}

    _save_state(state)


def _handle_build(identifier, build):
    issue = issue_service.get_issue_by_identifier(identifier)
    if not issue:
        return

    if build["result"] == "SUCCESS":
        issue_service.add_comment(
            issue["id"], f"✅ CI passed — build #{build['number']}: {build['url']}"
        )
        return

    issue_service.add_comment(
        issue["id"], f"❌ CI failed — build #{build['number']}: {build['url']}"
    )

    if issue["state"]["type"] in REGRESSION_STATE_TYPES:
        issue_service.update_issue(issue["id"], state_id=WORKFLOW_STATES["IN_PROGRESS"])
