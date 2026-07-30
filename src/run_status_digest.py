from slack_sdk import WebClient

from config import SLACK_BOT_TOKEN, SLACK_DIGEST_CHANNEL_ID
from services.project_service import ProjectService
from services import ai_service


def main():
    project_service = ProjectService()
    open_issues = project_service.get_open_issues()

    digest = ai_service.generate_status_digest(open_issues)
    print(digest)

    client = WebClient(token=SLACK_BOT_TOKEN)
    client.chat_postMessage(channel=SLACK_DIGEST_CHANNEL_ID, text=digest)


if __name__ == "__main__":
    main()
