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