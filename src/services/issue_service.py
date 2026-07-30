from client import LinearClient
from graphql.mutations import (
    CREATE_ISSUE,
    UPDATE_ISSUE,
    CREATE_COMMENT,
)
from graphql.queries import GET_ISSUE_BY_IDENTIFIER, GET_TEAM_MEMBERS, GET_TEAM_STATES
from config import TEAM_ID, PROJECT_ID


class IssueService:
    def __init__(self):
        self.client = LinearClient()

    def create_issue(self, title, description, priority=None, parent_id=None, assignee_id=None):
        input_data = {
            "teamId": TEAM_ID,
            "projectId": PROJECT_ID,
            "title": title,
            "description": description,
        }

        if priority is not None:
            input_data["priority"] = priority
        if parent_id is not None:
            input_data["parentId"] = parent_id
        if assignee_id is not None:
            input_data["assigneeId"] = assignee_id

        return self.client.execute(CREATE_ISSUE, {"input": input_data})

    def update_issue_state(self, issue_id, state_id):
        return self.update_issue(issue_id, state_id=state_id)

    def update_issue(self, issue_id, assignee_id=None, priority=None, state_id=None):
        input_data = {}

        if assignee_id is not None:
            input_data["assigneeId"] = assignee_id
        if priority is not None:
            input_data["priority"] = priority
        if state_id is not None:
            input_data["stateId"] = state_id

        return self.client.execute(
            UPDATE_ISSUE,
            {"id": issue_id, "input": input_data},
        )

    def list_team_members(self):
        data = self.client.execute(GET_TEAM_MEMBERS, {"teamId": TEAM_ID})
        return data["team"]["members"]["nodes"] if data else []

    def list_team_states(self):
        data = self.client.execute(GET_TEAM_STATES, {"teamId": TEAM_ID})
        return data["team"]["states"]["nodes"] if data else []

    def get_issue_by_identifier(self, identifier):
        data = self.client.execute(
            GET_ISSUE_BY_IDENTIFIER,
            {"id": identifier},
        )

        return data["issue"] if data else None

    def add_comment(self, issue_id, body):
        variables = {
            "input": {
                "issueId": issue_id,
                "body": body,
            }
        }

        return self.client.execute(
            CREATE_COMMENT,
            variables,
        )