from config import WORKFLOW_STATES, QA_SUBISSUE_PREFIX
from services.issue_service import IssueService
from services.project_service import ProjectService

issue_service = IssueService()
project_service = ProjectService()


def run():
    """Scans all issues on an interval (e.g. every few minutes via cron):
    - issues that entered "QA" get an auto-created verification sub-issue (once)
    - issues marked "Done" while a sub-issue is still open get reverted back to "QA"
    """
    issues = project_service.get_all_issues()

    for issue in issues:
        children = issue.get("children", {}).get("nodes", [])

        if issue["state"]["name"] == "QA":
            _ensure_qa_subissue(issue, children)
        elif issue["state"]["type"] == "completed":
            _enforce_qa_gate(issue, children)


def _ensure_qa_subissue(issue, children):
    already_has_subissue = any(
        child["title"].startswith(QA_SUBISSUE_PREFIX) for child in children
    )
    if already_has_subissue:
        return

    created = issue_service.create_issue(
        title=f"{QA_SUBISSUE_PREFIX}{issue['title']}",
        description=(
            f"Verify the fix for {issue['identifier']} in a QA/staging environment "
            "before marking it Done."
        ),
        parent_id=issue["id"],
    )
    sub_issue = created["issueCreate"]["issue"] if created else None

    if sub_issue:
        issue_service.add_comment(
            issue["id"], f"Created QA verification sub-issue: {sub_issue['url']}"
        )


def _enforce_qa_gate(issue, children):
    open_children = [
        child for child in children if child["state"]["type"] not in ("completed", "canceled")
    ]
    if not open_children:
        return

    issue_service.update_issue(issue["id"], state_id=WORKFLOW_STATES["QA"])
    names = ", ".join(child["title"] for child in open_children)
    issue_service.add_comment(
        issue["id"],
        f"⛔ Reverted to QA — sub-issue(s) still open: {names}. "
        "Complete QA verification before marking Done.",
    )
