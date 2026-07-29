from client import LinearClient
from graphql.mutations import CREATE_ISSUE
from config import TEAM_ID


class IssueService:

    def __init__(self):
        self.client = LinearClient()

    def create_issue(self, title, description):

        variables = {
            "input": {
                "teamId": TEAM_ID,
                "title": title,
                "description": description
            }
        }

        return self.client.execute(CREATE_ISSUE, variables)

        from graphql.mutations import UPDATE_ISSUE_STATE


def update_issue_state(self, issue_id, state_id):

    variables = {
        "id": issue_id,
        "input": {
            "stateId": state_id
        }
    }

    return self.client.execute(
        UPDATE_ISSUE_STATE,
        variables
    )

    def get_issue_by_identifier(self, identifier):
    ...