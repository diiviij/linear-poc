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

query = """
query {
  projects(first: 100) {
    nodes {
      id
      name
      state
      teams {
        nodes {
          key
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
    json={"query": query}
)

print(response.json())