from services.issue_service import IssueService
from config import WORKFLOW_STATES

service = IssueService()

result = service.update_issue_state(
    issue_id="YOUR_ISSUE_UUID",
    state_id=WORKFLOW_STATES["IN_PROGRESS"]
)

print(result)