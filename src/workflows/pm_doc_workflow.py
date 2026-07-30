import difflib
import json
from pathlib import Path

from slack_sdk import WebClient

from config import SLACK_BOT_TOKEN, SLACK_DIGEST_CHANNEL_ID
from services import ai_service
from services.project_service import ProjectService

DOC_STATE_FILE = Path(__file__).resolve().parent.parent.parent / "state" / "pm_doc_state.json"
APPROVALS_FILE = Path(__file__).resolve().parent.parent.parent / "state" / "pm_approvals.json"

project_service = ProjectService()
slack_client = WebClient(token=SLACK_BOT_TOKEN)


def _load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def load_approvals():
    return _load_json(APPROVALS_FILE)


def save_approvals(approvals):
    _save_json(APPROVALS_FILE, approvals)


def _added_text(old_content, new_content):
    diff = difflib.unified_diff(
        (old_content or "").splitlines(),
        (new_content or "").splitlines(),
        lineterm="",
    )
    added_lines = [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")]
    return "\n".join(added_lines)


def poll():
    """Watches every Doc in the project for new content. The first time a Doc is seen, its
    content is just recorded as a baseline (no suggestions — otherwise every pre-existing Doc
    would flood approvals on first run). On later polls, newly-added text gets sent to the model
    to decide whether it describes actionable work; each suggestion becomes a yes/no approval
    request in Slack rather than being created automatically."""
    doc_state = _load_json(DOC_STATE_FILE)
    documents = project_service.get_documents()

    for doc in documents:
        doc_id = doc["id"]
        content = doc.get("content") or ""

        if doc_id not in doc_state:
            doc_state[doc_id] = content
            continue

        previous_content = doc_state[doc_id]
        if content == previous_content:
            continue

        added = _added_text(previous_content, content)
        doc_state[doc_id] = content

        if not added.strip():
            continue

        suggestions = ai_service.suggest_tickets_from_doc_update(doc["title"], added)
        for suggestion in suggestions:
            _post_approval_request(doc["title"], suggestion)

    _save_json(DOC_STATE_FILE, doc_state)


def _post_approval_request(doc_title, suggestion):
    text = (
        f"📄 New content in Doc *{doc_title}* suggests a ticket:\n"
        f"*{suggestion['title']}*\n{suggestion['description']}\n\n"
        "Reply `yes` in this thread to create it, or `no` to skip."
    )
    response = slack_client.chat_postMessage(channel=SLACK_DIGEST_CHANNEL_ID, text=text)

    approvals = load_approvals()
    approvals[response["ts"]] = {
        "doc_title": doc_title,
        "title": suggestion["title"],
        "description": suggestion["description"],
        "priority": suggestion["priority"],
        "channel": SLACK_DIGEST_CHANNEL_ID,
    }
    save_approvals(approvals)
