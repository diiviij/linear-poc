import json
import re
from pathlib import Path

import requests

from config import GITHUB_TOKEN, GITHUB_REPO, WORKFLOW_STATES
from services.issue_service import IssueService

ISSUE_ID_PATTERN = re.compile(r"\b([A-Z]{2,10}-\d+)\b")

STATE_FILE = Path(__file__).resolve().parent.parent.parent / "state" / "github_poll_state.json"

issue_service = IssueService()


def _normalize_repo(repo):
    """Accepts either 'owner/repo' or a full GitHub URL."""
    repo = repo.strip().rstrip("/")
    repo = re.sub(r"^https?://github\.com/", "", repo)
    repo = re.sub(r"\.git$", "", repo)
    return repo


def _load_state():
    if not STATE_FILE.exists():
        return {"prs": {}, "branches": {}}

    data = json.loads(STATE_FILE.read_text())
    if "prs" not in data:
        data = {"prs": data, "branches": {}}  # migrate from the pre-branch-tracking format
    data.setdefault("branches", {})
    return data


def _save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _extract_issue_identifier(pr):
    haystack = " ".join(
        filter(None, [pr.get("title"), pr.get("body"), pr.get("head", {}).get("ref")])
    )
    match = ISSUE_ID_PATTERN.search(haystack)
    return match.group(1) if match else None


def _github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def poll():
    """Checks recently created branches and updated PRs for linked Linear issues and reacts
    to branch-created/PR-opened/PR-merged events. Safe to run on an interval (e.g. every few
    minutes via cron) — already-handled branches/PRs are tracked in a local state file so
    actions aren't repeated."""
    state = _load_state()
    _poll_branches(state)
    _poll_pull_requests(state)
    _save_state(state)


def _poll_branches(state):
    branches_state = state["branches"]

    response = requests.get(
        f"https://api.github.com/repos/{_normalize_repo(GITHUB_REPO)}/branches",
        headers=_github_headers(),
        params={"per_page": 100},
    )
    response.raise_for_status()
    branches = response.json()

    for branch in branches:
        name = branch["name"]
        if name in branches_state:
            continue

        match = ISSUE_ID_PATTERN.search(name)
        if match:
            _handle_branch_created(match.group(1), name)

        branches_state[name] = {"processed": True}


def _poll_pull_requests(state):
    prs_state = state["prs"]

    response = requests.get(
        f"https://api.github.com/repos/{_normalize_repo(GITHUB_REPO)}/pulls",
        headers=_github_headers(),
        params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 30},
    )
    response.raise_for_status()
    pulls = response.json()

    for pr in pulls:
        number = str(pr["number"])
        pr_state = prs_state.get(number, {})

        identifier = _extract_issue_identifier(pr)
        if not identifier:
            continue

        if pr.get("merged_at") and not pr_state.get("moved_to_qa"):
            _handle_merged(identifier, pr)
            pr_state["moved_to_qa"] = True
        elif pr["state"] == "open" and not pr_state.get("commented_opened"):
            _handle_opened(identifier, pr)
            pr_state["commented_opened"] = True

        prs_state[number] = pr_state


def _handle_branch_created(identifier, branch_name):
    issue = issue_service.get_issue_by_identifier(identifier)
    if not issue:
        return

    if issue["state"]["type"] != "backlog":
        return  # already past Backlog (e.g. a PR already moved it further) — don't regress

    issue_service.add_comment(issue["id"], f"Branch created: `{branch_name}`")
    issue_service.update_issue(issue["id"], state_id=WORKFLOW_STATES["TODO"])


def _handle_opened(identifier, pr):
    issue = issue_service.get_issue_by_identifier(identifier)
    if not issue:
        return

    issue_service.add_comment(issue["id"], f"PR opened: {pr['html_url']}")
    issue_service.update_issue(issue["id"], state_id=WORKFLOW_STATES["IN_REVIEW"])


def _handle_merged(identifier, pr):
    issue = issue_service.get_issue_by_identifier(identifier)
    if not issue:
        return

    issue_service.add_comment(
        issue["id"], f"Merged via {pr['html_url']} — ready for QA verification."
    )
    issue_service.update_issue(issue["id"], state_id=WORKFLOW_STATES["QA"])
