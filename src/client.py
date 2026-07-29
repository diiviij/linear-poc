import requests

from config import LINEAR_API_KEY
from config import LINEAR_URL


class LinearClient:

    def __init__(self):
        self.url = LINEAR_URL

        self.headers = {
            "Authorization": LINEAR_API_KEY,
            "Content-Type": "application/json"
        }

    def execute(self, query, variables=None):

        payload = {
            "query": query,
            "variables": variables or {}
        }

        response = requests.post(
            self.url,
            headers=self.headers,
            json=payload
        )

        if response.status_code != 200:
            print("\n========== HTTP ERROR ==========")
            print("Status:", response.status_code)
            print(response.text)
            print("================================\n")
            return None

        result = response.json()

        if "errors" in result:
            print("\n========== GRAPHQL ERRORS ==========")
            print(result["errors"])
            print("====================================\n")
            return None

        return result["data"]