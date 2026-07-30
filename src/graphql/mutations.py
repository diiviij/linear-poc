CREATE_ISSUE = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue {
      id
      identifier
      title
      url
      priority
      assignee {
        name
      }
    }
  }
}
"""
UPDATE_ISSUE = """
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(
    id: $id
    input: $input
  ) {
    success
    issue {
      identifier
      title
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
"""

CREATE_COMMENT = """
mutation CommentCreate($input: CommentCreateInput!) {
  commentCreate(input: $input) {
    success
    comment {
      id
      body
    }
  }
}
"""