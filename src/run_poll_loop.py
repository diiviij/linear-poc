import time
import traceback
from datetime import datetime

from workflows import (
    github_workflow,
    jenkins_workflow,
    qa_gate,
    pm_doc_workflow,
    playwright_report_workflow,
)

INTERVAL_SECONDS = 60

TASKS = [
    ("GitHub PR/branch sync", github_workflow.poll),
    ("Jenkins CI sync", jenkins_workflow.poll),
    ("QA gate", qa_gate.run),
    ("PM doc watcher", pm_doc_workflow.poll),
    ("Playwright report analysis", playwright_report_workflow.poll),
]


def main():
    print(f"Starting poll loop, every {INTERVAL_SECONDS}s. Ctrl+C to stop.")
    while True:
        for name, task in TASKS:
            try:
                task()
                print(f"[{datetime.now().isoformat()}] {name}: ok")
            except Exception:
                print(f"[{datetime.now().isoformat()}] {name}: FAILED")
                traceback.print_exc()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
