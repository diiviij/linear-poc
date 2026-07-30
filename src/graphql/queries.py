GET_PROJECT_ISSUES = """
query ($projectId: String!) {
  project(id: $projectId) {
    name
    issues(first:100) {
      nodes {
        id
        identifier
        title
        description
        priority
        url
        dueDate
        updatedAt

        state {
          name
          type
        }

        assignee {
          name
        }

        children {
          nodes {
            id
            title
            state {
              type
            }
          }
        }
      }
    }
  }
}
"""

GET_OPEN_PROJECT_ISSUES = """
query ($projectId: String!) {
  project(id: $projectId) {
    name
    issues(
      first: 100
      filter: { state: { type: { nin: ["completed", "canceled"] } } }
    ) {
      nodes {
        id
        identifier
        title
        description
        priority
        url
        dueDate
        updatedAt

        state {
          name
          type
        }

        assignee {
          name
        }
      }
    }
  }
}
"""

GET_TEAM_MEMBERS = """
query ($teamId: String!) {
  team(id: $teamId) {
    members {
      nodes {
        id
        name
        email
      }
    }
  }
}
"""

GET_TEAM_STATES = """
query ($teamId: String!) {
  team(id: $teamId) {
    states {
      nodes {
        id
        name
        type
      }
    }
  }
}
"""

GET_ISSUE_BY_IDENTIFIER = """
query ($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    description
    priority
    url
    state {
      name
      type
    }
    assignee {
      name
    }
  }
}
"""