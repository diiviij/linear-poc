from services.issue_service import IssueService

ISSUE_ID = "YOUR_LINEAR_ISSUE_UUID"


def main():
    service = IssueService()

    result = service.add_comment(
        ISSUE_ID,
        """
✅ Comment added from Python SDK

This proves our automation engine
can communicate back to Linear.
"""
    )

    print(result)


if __name__ == "__main__":
    main()