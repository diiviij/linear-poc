from services.issue_service import IssueService


def main():

    service = IssueService()

    result = service.create_issue(
        title="Linear Automation POC",
        description="""
This issue was created automatically
using the GraphQL API.

POC #3
"""
    )

    if result is None:
        print("Issue creation failed.")
        return

    issue = result["issueCreate"]["issue"]

    print("\nIssue Created Successfully!\n")
    print("Identifier :", issue["identifier"])
    print("Title      :", issue["title"])
    print("URL        :", issue["url"])


if __name__ == "__main__":
    main()