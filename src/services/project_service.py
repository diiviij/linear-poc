from client import LinearClient
from graphql.queries import GET_PROJECT_ISSUES, GET_OPEN_PROJECT_ISSUES
from config import PROJECT_ID


class ProjectService:

    def __init__(self):

        self.client = LinearClient()

    def get_project_issues(self):

        return self.client.execute(
            GET_PROJECT_ISSUES,
            {
                "projectId": PROJECT_ID
            }
        )

    def get_open_issues(self):
        """Issues not yet completed/canceled — used for dedupe checks and the status digest."""
        data = self.client.execute(
            GET_OPEN_PROJECT_ISSUES,
            {
                "projectId": PROJECT_ID
            }
        )

        if not data:
            return []

        return data["project"]["issues"]["nodes"]

    def get_all_issues(self):
        """All issues regardless of state, with sub-issue data — used by the QA gate."""
        data = self.client.execute(
            GET_PROJECT_ISSUES,
            {
                "projectId": PROJECT_ID
            }
        )

        if not data:
            return []

        return data["project"]["issues"]["nodes"]