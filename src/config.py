import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")

LINEAR_URL = "https://api.linear.app/graphql"

TEAM_ID = "8cb470fa-1103-4aeb-8ba5-6ce56bd21613"

PROJECT_ID = "b29edd1b-8d88-484a-bf1b-b6b14621c6ea"

PROJECT_NAME = "AllThingsTesting"
PROJECT_ID = "b29edd1b-8d88-484a-bf1b-b6b14621c6ea"

PROJECT_NAME = "AllThingsTesting"

WORKFLOW_STATES = {
    "BACKLOG": "7c4d3cac-f048-4b62-8f48-67c6b91b5b37",
    "TODO": "2298e9e6-33da-4823-a786-e0188ebbdd4b",
    "IN_PROGRESS": "285f12df-654d-409a-81c3-9cb9501337eb",
    "QA": "17d8ca42-c0d2-4251-a582-8355b1dcbcee",
    "IN_REVIEW": "01e3ddb3-a0d3-42c0-b407-c1bc15206e53",
    "DONE": "dc2f7b47-a4a1-4636-9df9-c25a012a4b0c",
}