import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("LINEAR_API_KEY")

url = "https://api.linear.app/graphql"

headers = {
    "Authorization": API_KEY,
    "Content-Type": "application/json"
}

PROJECT_ID = "b29edd1b-8d88-484a-bf1b-b6b14621c6ea"

query = """
query ($projectId: String!) {
  project(id: $projectId) {
    name
    issues(first: 100) {
      nodes {
        id
        identifier
        title
        description
        priority
        state {
          name
        }
        assignee {
          name
        }
      }
    }
  }
}
"""

response = requests.post(
    url,
    headers=headers,
    json={
        "query": query,
        "variables": {
            "projectId": PROJECT_ID
        }
    }
)

print(response.json())