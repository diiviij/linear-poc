import json
from collections import defaultdict
from datetime import datetime, timezone

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, STALE_ISSUE_DAYS

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client

# Assignees carrying this many open issues get flagged in the status digest
OVERLOAD_THRESHOLD = 5

TRIAGE_SCHEMA = {
    "name": "triage_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "is_duplicate": {"type": "boolean"},
            "duplicate_identifier": {
                "type": ["string", "null"],
                "description": "Identifier of the matching open issue, e.g. 'ENG-123', if is_duplicate is true.",
            },
            "title": {"type": "string"},
            "description": {"type": "string"},
            "priority": {
                "type": "integer",
                "description": "0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low",
            },
        },
        "required": [
            "is_duplicate",
            "duplicate_identifier",
            "title",
            "description",
            "priority",
        ],
        "additionalProperties": False,
    },
}


def classify_and_dedupe(feedback_text, open_issues):
    """
    Given a raw Slack message and the currently open Linear issues, decide whether
    it's a duplicate of an existing issue or draft a new one.
    """
    issue_summaries = "\n".join(
        f"- {issue['identifier']}: {issue['title']}" for issue in open_issues
    ) or "(none)"

    response = _get_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You triage incoming bug reports and feedback for an engineering team. "
                    "Given a raw message and the list of currently open issues, decide whether "
                    "it describes the same problem as an existing issue. If so, return that "
                    "issue's identifier as the duplicate. Otherwise draft a new issue: a concise "
                    "title, and a structured description covering what happened, expected vs "
                    "actual behavior, and any repro details present in the message."
                ),
            },
            {
                "role": "user",
                "content": f"Open issues:\n{issue_summaries}\n\nIncoming message:\n{feedback_text}",
            },
        ],
        response_format={"type": "json_schema", "json_schema": TRIAGE_SCHEMA},
    )

    return json.loads(response.choices[0].message.content)


def _parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _bucket_issues(open_issues, stale_days):
    now = datetime.now(timezone.utc)
    overdue, stale = [], []
    workload = defaultdict(int)

    for issue in open_issues:
        assignee = issue.get("assignee")
        if assignee:
            workload[assignee["name"]] += 1

        due_date = issue.get("dueDate")
        if due_date and _parse_iso(due_date) < now:
            overdue.append(issue)

        updated_at = issue.get("updatedAt")
        if updated_at and (now - _parse_iso(updated_at)).days >= stale_days:
            stale.append(issue)

    overloaded = {
        name: count
        for name, count in workload.items()
        if count >= OVERLOAD_THRESHOLD
    }

    return overdue, stale, overloaded


def generate_status_digest(open_issues, stale_days=STALE_ISSUE_DAYS):
    """
    Buckets issues deterministically (overdue / stale / overloaded assignees) in Python,
    then asks the model to turn those facts into a short, readable digest — the model
    never invents the numbers, only the prose.
    """
    overdue, stale, overloaded = _bucket_issues(open_issues, stale_days)

    facts = {
        "total_open": len(open_issues),
        "overdue": [
            {"identifier": i["identifier"], "title": i["title"], "dueDate": i["dueDate"]}
            for i in overdue
        ],
        "stale": [
            {"identifier": i["identifier"], "title": i["title"], "updatedAt": i["updatedAt"]}
            for i in stale
        ],
        "overloaded_assignees": overloaded,
    }

    response = _get_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You write a short weekly status digest for a project manager, formatted "
                    "for Slack (use *bold* and bullet points, no headers). Only report the facts "
                    "given to you — do not invent issue names, counts, or dates. If a category is "
                    "empty, say so briefly rather than omitting it."
                ),
            },
            {"role": "user", "content": json.dumps(facts)},
        ],
    )

    return response.choices[0].message.content


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_open_issues",
            "description": "List currently open (not completed/canceled) issues in the project.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_issue",
            "description": "Look up a single issue by its identifier, e.g. 'ENG-123'.",
            "parameters": {
                "type": "object",
                "properties": {"identifier": {"type": "string"}},
                "required": ["identifier"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_issue",
            "description": (
                "File a brand-new issue for a problem that doesn't exist yet. Do NOT call this "
                "if the user's message references an existing issue identifier (e.g. 'SPDEV-72') "
                "or is asking to update/assign/reprioritize/comment on an issue — use update_issue "
                "or add_comment for those instead, and never call create_issue in the same turn as "
                "update_issue."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "integer"},
                },
                "required": ["title", "description"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_comment",
            "description": "Add a comment to an existing issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["issue_id", "body"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_issue",
            "description": (
                "Change the assignee, priority, and/or status of an EXISTING issue. Use this "
                "instead of create_issue whenever the user is referring to an issue that already "
                "exists (by identifier, or by name/description that matches a search result)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "e.g. 'ENG-123'"},
                    "assignee_name": {
                        "type": "string",
                        "description": "Name of the person to assign the issue to.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low",
                    },
                    "state_name": {
                        "type": "string",
                        "description": "e.g. 'Todo', 'In Progress', 'QA', 'In Review', 'Done'",
                    },
                },
                "required": ["identifier"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_team_members",
            "description": "List the team's members (name/email) — use this to confirm who to assign an issue to before calling update_issue, especially if a name looks misspelled or ambiguous.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]

AGENT_SYSTEM_PROMPT = (
    "You are a Linear assistant available to the team in Slack. Use the available tools to "
    "answer questions about issues or take actions the user asks for (creating issues, "
    "assigning/updating existing issues, commenting, checking status). Keep replies short and "
    "Slack-friendly. Never fabricate issue identifiers, titles, statuses, or usernames — always "
    "look them up with a tool first.\n\n"
    "Only call create_issue when the user is reporting a brand-new problem that doesn't already "
    "exist. If the message mentions an existing issue identifier (e.g. 'SPDEV-72') or asks to "
    "assign/update/reprioritize/comment on an issue, that is NEVER a create_issue request — use "
    "update_issue or add_comment instead, and do not also call create_issue in the same turn. If "
    "an assignee name doesn't clearly match anyone (check with list_team_members), or you can't "
    "tell which issue the user means, ask a short clarifying question in plain text instead of "
    "guessing or creating a placeholder issue."
)


def run_agent(user_message, tool_executors, history=None):
    """
    Runs one user turn of the NL agent to completion, calling tools as needed.

    tool_executors: dict mapping tool name -> callable(**kwargs) -> JSON-serializable result
    history: prior [{"role", "content"}, ...] messages for this conversation, excluding the
             system prompt
    Returns (reply_text, updated_history).
    """
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_message})

    while True:
        response = _get_client().chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=AGENT_TOOLS,
        )
        choice = response.choices[0]
        messages.append(choice.message.model_dump(exclude_none=True))

        if not choice.message.tool_calls:
            updated_history = messages[1:]
            return choice.message.content, updated_history

        for tool_call in choice.message.tool_calls:
            executor = tool_executors.get(tool_call.function.name)
            args = json.loads(tool_call.function.arguments or "{}")

            if executor is None:
                result = {"error": f"Unknown tool: {tool_call.function.name}"}
            else:
                result = executor(**args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )
