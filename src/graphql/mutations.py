CREATE_ISSUE = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue {
      id
      identifier
      title
      url
    }
  }
}
"""
UPDATE_ISSUE_STATE = """
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(
    id: $id
    input: $input
  ) {
    success
    issue {
      identifier
      title
      state {
        name
      }
    }
  }
}
"""