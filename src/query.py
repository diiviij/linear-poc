import os
import requests
from dotenv import load_dotenv
from pathlib import Path
from dotenv import load_dotenv
import os

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("LINEAR_API_KEY")

print("API Key Loaded:", API_KEY is not None)
print("Key Prefix:", API_KEY[:8] if API_KEY else "None")
# Load environment variables
load_dotenv()

API_KEY = os.getenv("LINEAR_API_KEY")

url = "https://api.linear.app/graphql"

headers = {
    "Authorization": API_KEY,
    "Content-Type": "application/json"
}

query = """
query {
  teams {
    nodes {
      id
      key
      name
    }
  }
}
"""

response = requests.post(
    url,
    headers=headers,
    json={"query": query}
)

print("Status Code:", response.status_code)
print(response.json())