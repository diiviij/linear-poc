from client import LinearClient

client = LinearClient()

query = """
query {
  workflowStates(first: 100) {
    nodes {
      id
      name
      type
      team {
        key
      }
    }
  }
}
"""

data = client.execute(query)

for state in data["workflowStates"]["nodes"]:
    print(
        f"{state['team']['key']} | "
        f"{state['name']} | "
        f"{state['type']} | "
        f"{state['id']}"
    )