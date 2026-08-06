import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config import SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_FEED_CHANNEL_ID
from services.issue_service import IssueService
from services.project_service import ProjectService
from services import ai_service
from workflows.pm_doc_workflow import load_approvals, save_approvals

app = App(token=SLACK_BOT_TOKEN)

issue_service = IssueService()
project_service = ProjectService()

# thread_ts -> conversation history, for the NL agent. In-memory is fine for a POC;
# a real deployment would persist this per-thread.
_conversations = {}

MENTION_PATTERN = re.compile(r"<@[^>]+>\s*")


def _issue_summary(issue):
    return {
        "id": issue["id"],
        "identifier": issue["identifier"],
        "title": issue["title"],
        "state": issue["state"]["name"],
        "assignee": issue["assignee"]["name"] if issue.get("assignee") else None,
        "priority": issue.get("priority"),
        "url": issue.get("url"),
    }


def _resolve_uuid(identifier, open_issues):
    for issue in open_issues:
        if issue["identifier"] == identifier:
            return issue["id"]

    # Not in the already-fetched page (e.g. it was closed) — look it up directly.
    issue = issue_service.get_issue_by_identifier(identifier)
    return issue["id"] if issue else identifier


def _tool_search_open_issues():
    return [_issue_summary(i) for i in project_service.get_open_issues()]


def _tool_get_issue(identifier):
    issue = issue_service.get_issue_by_identifier(identifier)
    if not issue:
        return {"error": f"No issue found for {identifier}"}
    return _issue_summary(issue)


def _tool_create_issue(title, description, priority=None, assignee_name=None):
    assignee_id = None
    if assignee_name is not None:
        member, error = _find_member_by_name(assignee_name)
        if error:
            return {"error": error}
        assignee_id = member["id"]

    result = issue_service.create_issue(title, description, priority, assignee_id=assignee_id)
    if not result or not result["issueCreate"]["success"]:
        return {"error": "Failed to create issue"}
    return result["issueCreate"]["issue"]


def _tool_add_comment(issue_id, body):
    result = issue_service.add_comment(issue_id, body)
    if not result or not result["commentCreate"]["success"]:
        return {"error": "Failed to add comment"}
    return {"success": True}


def _find_member_by_name(name):
    members = issue_service.list_team_members()
    name_lower = name.strip().lower()

    matches = [m for m in members if name_lower in m["name"].lower()]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, f"'{name}' matches multiple people: {[m['name'] for m in matches]}. Ask which one."
    return None, f"No team member matching '{name}'. Known members: {[m['name'] for m in members]}"


def _find_state_by_name(name):
    states = issue_service.list_team_states()
    name_lower = name.strip().lower()

    matches = [s for s in states if s["name"].lower() == name_lower]
    if not matches:
        matches = [s for s in states if name_lower in s["name"].lower()]

    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, f"'{name}' matches multiple states: {[s['name'] for s in matches]}. Ask which one."
    return None, f"No workflow state matching '{name}'. Known states: {[s['name'] for s in states]}"


def _tool_update_issue(identifier, assignee_name=None, priority=None, state_name=None):
    issue = issue_service.get_issue_by_identifier(identifier)
    if not issue:
        return {"error": f"No issue found for {identifier}"}

    assignee_id = None
    if assignee_name is not None:
        member, error = _find_member_by_name(assignee_name)
        if error:
            return {"error": error}
        assignee_id = member["id"]

    state_id = None
    if state_name is not None:
        state, error = _find_state_by_name(state_name)
        if error:
            return {"error": error}
        state_id = state["id"]

    result = issue_service.update_issue(issue["id"], assignee_id, priority, state_id)
    if not result or not result["issueUpdate"]["success"]:
        return {"error": "Failed to update issue"}
    return result["issueUpdate"]["issue"]


def _tool_list_team_members():
    return [{"name": m["name"], "email": m["email"]} for m in issue_service.list_team_members()]


TOOL_EXECUTORS = {
    "search_open_issues": _tool_search_open_issues,
    "get_issue": _tool_get_issue,
    "create_issue": _tool_create_issue,
    "add_comment": _tool_add_comment,
    "update_issue": _tool_update_issue,
    "list_team_members": _tool_list_team_members,
}


@app.event("message")
def handle_feed_message(event, say):
    """Raw bug reports / feedback posted in the triage feed channel get classified,
    deduped against open issues, and turned into (or attached to) a Linear issue."""
    if event.get("channel") != SLACK_FEED_CHANNEL_ID:
        return
    if event.get("bot_id") or event.get("subtype"):
        return

    text = event.get("text", "").strip()
    if not text:
        return

    open_issues = project_service.get_open_issues()
    result = ai_service.classify_and_dedupe(text, open_issues)

    if result["is_duplicate"] and result["duplicate_identifier"]:
        issue_uuid = _resolve_uuid(result["duplicate_identifier"], open_issues)
        issue_service.add_comment(issue_uuid, f"Additional report via Slack:\n\n{text}")
        say(
            text=f"Looks like a duplicate of *{result['duplicate_identifier']}* — added your report there as a comment.",
            thread_ts=event["ts"],
        )
        return

    created = issue_service.create_issue(result["title"], result["description"], result["priority"])
    issue = created["issueCreate"]["issue"] if created else None

    if issue:
        say(
            text=f"Created <{issue['url']}|{issue['identifier']}: {issue['title']}>",
            thread_ts=event["ts"],
        )
    else:
        say(text="Couldn't create a Linear issue for this — check the logs.", thread_ts=event["ts"])


@app.event("app_mention")
def handle_mention(event, say):
    _respond(event, say)


@app.event("message")
def handle_dm(event, say):
    if event.get("channel_type") != "im":
        return
    if event.get("bot_id") or event.get("subtype"):
        return
    _respond(event, say)


@app.event("message")
def handle_approval_reply(event, say):
    """Thread replies to a PM-doc ticket-suggestion prompt: 'yes' creates the ticket, anything
    else (starting with 'no') skips it — no ticket is created without an explicit yes."""
    print(f"DEBUG approval_reply raw event: {event}")

    thread_ts = event.get("thread_ts")
    if not thread_ts or event.get("bot_id") or event.get("subtype"):
        print(f"DEBUG bailing: thread_ts={thread_ts!r} bot_id={event.get('bot_id')!r} subtype={event.get('subtype')!r}")
        return

    approvals = load_approvals()
    print(f"DEBUG pending keys: {list(approvals.keys())}, looking for: {thread_ts!r}")
    pending = approvals.get(thread_ts)
    if not pending:
        return

    text = event.get("text", "").strip().lower()

    if text in ("yes", "y", "approve", "approved"):
        created = issue_service.create_issue(pending["title"], pending["description"], pending["priority"])
        issue = created["issueCreate"]["issue"] if created else None
        if issue:
            say(text=f"Created <{issue['url']}|{issue['identifier']}: {issue['title']}>", thread_ts=thread_ts)
        else:
            say(text="Couldn't create the issue — check the logs.", thread_ts=thread_ts)
        del approvals[thread_ts]
        save_approvals(approvals)
    elif text in ("no", "n", "reject", "skip"):
        say(text="Skipped — no ticket created.", thread_ts=thread_ts)
        del approvals[thread_ts]
        save_approvals(approvals)
    else:
        say(text="Reply `yes` or `no` to resolve this suggestion.", thread_ts=thread_ts)


def _respond(event, say):
    thread_key = event.get("thread_ts") or event["ts"]
    history = _conversations.get(thread_key, [])

    text = MENTION_PATTERN.sub("", event.get("text", "")).strip()
    reply, updated_history = ai_service.run_agent(text, TOOL_EXECUTORS, history)
    _conversations[thread_key] = updated_history

    say(text=reply, thread_ts=thread_key)


def start():
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
