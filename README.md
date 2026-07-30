# Linear Automation POC

Demonstrates how AI + automation can remove repetitive manual work from a
Jira → Linear migration, across Engineering, QA, DevOps, Product, and PM.
Three pieces, all backed by the same Linear GraphQL client and an OpenAI model:

1. **AI intake triage** — messages posted in a Slack "feed" channel (bug
   reports, customer feedback) are classified, deduped against currently open
   Linear issues, and either filed as a new issue or attached as a comment on
   the existing duplicate.
2. **AI status digest** — a script that buckets open issues (overdue, stale,
   overloaded assignees) and has the model turn those facts into a short
   Slack-ready weekly digest for PM.
3. **Natural-language Linear agent** — mention the bot or DM it in Slack to
   query or act on Linear issues in plain English (search, look up, create,
   update/assign, comment), via OpenAI tool-calling.
4. **GitHub PR sync** — polls open/merged PRs, extracts a linked Linear issue
   identifier (e.g. `SPDEV-72`) from the PR title/body/branch name, and moves
   the issue to "In Review" on open or "QA" on merge, with a comment linking
   the PR.
5. **Jenkins CI sync** — polls a Jenkins job's build history, extracts the
   linked issue identifier from build parameters, and comments pass/fail on
   the issue — reopening it to "In Progress" if CI fails on an issue that had
   already moved past active development (a caught regression).
6. **QA gate** — polls all issues; anything that enters "QA" gets an
   auto-created verification sub-issue, and anything marked "Done" while a
   sub-issue is still open gets reverted back to "QA" with an explanatory
   comment — enforcing that QA sign-off actually happens.

Pieces 4-6 are polling-based (no public webhook endpoint needed) — each is a
one-shot script meant to be run on an interval via cron.

## Setup

```bash
cd linear-poc
source venv/bin/activate
pip install -r requirements.txt
```

Fill in `.env`:

```
LINEAR_API_KEY=...        # already set
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o       # default, override if desired
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...  # Socket Mode app-level token, needs connections:write
SLACK_FEED_CHANNEL_ID=... # channel raw bug reports/feedback get posted into
SLACK_DIGEST_CHANNEL_ID=...
STALE_ISSUE_DAYS=3        # issues untouched this many days count as "at risk"

GITHUB_TOKEN=...          # PAT with repo read access
GITHUB_REPO=owner/repo

JENKINS_URL=https://...
JENKINS_USER=...
JENKINS_API_TOKEN=...
JENKINS_JOB_NAME=...      # job whose build history gets polled
```

### Slack app configuration

- Enable **Socket Mode** and generate an app-level token (`SLACK_APP_TOKEN`,
  scope `connections:write`).
- Bot token scopes: `chat:write`, `app_mentions:read`, `channels:history`
  (or `groups:history` if the feed channel is private), `im:history`,
  `im:write`.
- Subscribe to bot events: `message.channels`, `message.im`, `app_mention`.
- Invite the bot to the feed channel.

## Running each piece

```bash
cd src

# Triage + NL agent (long-running, Socket Mode)
python run_slack_bot.py

# Status digest (run once, e.g. via cron for a weekly post)
python run_status_digest.py

# GitHub PR sync, Jenkins CI sync, QA gate — each a one-shot poll, run on an
# interval via cron (e.g. every 2-5 minutes)
python run_github_poll.py
python run_jenkins_poll.py
python run_qa_gate.py

# Original basic CRUD example
python main.py
```

Poll state for pieces 4-5 is tracked in `state/` (already-handled PRs/builds
aren't reprocessed) — safe to delete to reprocess everything, e.g. when testing.

## Layout

- `client.py` — thin GraphQL client wrapper around Linear's API.
- `graphql/` — raw GraphQL query/mutation strings.
- `services/issue_service.py`, `services/project_service.py` — typed
  operations against Linear (create/update issues, fetch open issues, look
  up by identifier).
- `services/ai_service.py` — all OpenAI calls: triage classification/dedupe,
  digest summarization, and the agent's tool-calling loop. Deterministic
  facts (overdue/stale/workload counts) are computed in Python; the model
  only turns them into prose or decides which tool to call next — it never
  invents issue data.
- `workflows/slack_workflow.py` — Slack Bolt app wiring the feed-channel
  listener and the NL agent to the services above.
- `workflows/github_workflow.py`, `workflows/jenkins_workflow.py`,
  `workflows/qa_gate.py` — the three polling-based automations, each a plain
  `poll()`/`run()` function called by its entrypoint script.
- `run_slack_bot.py`, `run_status_digest.py`, `run_github_poll.py`,
  `run_jenkins_poll.py`, `run_qa_gate.py` — entrypoints.
.
