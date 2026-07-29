from client import LinearClient
from graphql.queries import GET_PROJECT_ISSUES
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