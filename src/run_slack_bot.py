from workflows.slack_workflow import start


def main():
    print("Starting Slack bot (Socket Mode)... Ctrl+C to stop.")
    start()


if __name__ == "__main__":
    main()
