# Application Agent

**English** · [Türkçe](README.tr.md)

A self-hosted job-hunting assistant. It finds postings that match your criteria, scores each one against
your profile, and prepares an **application package** for the good matches: a tailored CV (PDF), a cover
letter, ready answers to common application-form questions, and a fit analysis.

**You always apply manually.** The app never fills in or submits an application form for you.

Everything runs on your own computer. Your profile, your CV and your job data stay in a local SQLite
database. There is no hosted service, no account, and no API key: the language-model calls go through
the **Claude Code** or **Codex** CLI that you are already logged into.

## Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Using the app](#using-the-app)
- [Configuration](#configuration)
- [Job sources](#job-sources)
- [Using it from your phone](#using-it-from-your-phone)
- [Demo mode (no LLM needed)](#demo-mode-no-llm-needed)
- [Development and tests](#development-and-tests)
- [Project layout](#project-layout)
- [Privacy and safety](#privacy-and-safety)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Profile and projects in one place.** Upload an existing CV (PDF, DOCX, TXT or MD) and the LLM turns it
  into an editable profile. Projects can be added by hand or imported in bulk from JSON files.
- **Automatic job search.** Pulls postings from company career boards and public job boards, plus job-alert
  emails, on a daily schedule or on demand.
- **Cheap pre-filtering, then LLM scoring.** A free keyword/location/seniority filter removes obvious misses
  before anything is sent to the LLM. Role and location matching understands Turkish and English spellings.
- **Scores with reasons.** Every posting gets a 0–100 score and a short explanation, so you can see why it
  was ranked where it was.
- **Application package per posting.**
  - A CV tailored to the posting, rendered to PDF (Chromium via Playwright).
  - A cover letter written for that company and role.
  - Prepared answers to likely form questions. Unknowable items such as salary are left as templates to fill in.
  - A fit analysis: matched and missing skills, and which of your projects were highlighted.
- **Stays honest.** The tailoring step is built to use only facts from your own profile, and it filters out
  invented details. Still, always read the result before sending it (see [Privacy and safety](#privacy-and-safety)).
- **CV language follows the posting** (`auto`, `tr` or `en`).
- **Application tracking.** Each posting moves through `new`, `applied`, `skipped`, `interview`, `rejected`
  and `offer`.
- **Add a posting by link or pasted text.** If a page cannot be read (for example behind a login wall),
  paste the posting text instead.
- **Installable on your phone.** The UI is a PWA. Over Tailscale you can install it like a native app and
  use your own computer as the backend.

## How it works

```
┌──────────────────────┐   REST/JSON    ┌──────────────────────────────────────────┐
│  frontend (React)    │ ─────────────▶ │  backend (FastAPI)                       │
│  profile editor      │                │  ├─ api/        HTTP layer               │
│  job list            │ ◀───────────── │  ├─ sources/    job sources              │
│  application package │                │  ├─ llm/        scoring, tailoring       │
│  settings            │                │  ├─ render/     CV → PDF                 │
└──────────────────────┘                │  ├─ search/     pipeline + scheduler     │
                                        │  └─ db/         SQLite                   │
                                        └──────────────────────────────────────────┘
```

A search run goes through these steps:

1. **Collect** postings from every enabled source.
2. **Filter** them with the free pre-filter (roles, locations, seniority, excluded keywords, age).
3. **Score** the survivors in batches with the LLM (capped per run by `SEARCH_MAX_SCORED_PER_RUN`).
4. **Store** the results. Postings already seen are not scored again, so repeat runs are fast.
5. **Package** every posting at or above your minimum score, in the background.

The only contract between frontend and backend is the REST API. Example payloads live in
[`contracts/examples/`](contracts/examples) and are used by the mock mode and the tests.

## Tech stack

| Part | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLModel + SQLite, APScheduler, httpx, BeautifulSoup |
| Documents | pypdf and python-docx (reading CVs), Jinja2 + Playwright/Chromium (CV → PDF, JavaScript-rendered pages) |
| LLM | Claude Code CLI or Codex CLI, called as a subprocess with a JSON schema. No API key. |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query, React Router, vite-plugin-pwa |
| Tooling | [uv](https://docs.astral.sh/uv/) for Python, npm for the frontend, pytest and Node's built-in test runner |

## Requirements

| Tool | Why | Check |
|---|---|---|
| Git | clone the repo | `git --version` |
| [uv](https://docs.astral.sh/uv/) | installs Python and the backend | `uv --version` |
| Node.js 22 | build the frontend | `node --version` |
| Claude Code **or** Codex CLI, logged in | all LLM calls (uses your subscription) | `claude -p "hello"` or `codex exec "hello"` |
| Tailscale (optional) | use it from your phone | `tailscale status` |

macOS and Windows are the tested platforms. On Windows, Claude Code also needs Git for Windows (Git Bash)
and the commands below should be run in PowerShell. Linux has not been tested.

## Quick start

```bash
git clone git@github.com:yusufcetn/application-agent.git
cd application-agent

cd backend
uv sync
uv run playwright install chromium
cd ../frontend
npm ci
npm run build
cd ..
```

Copy `.env.example` to `.env` in the repository root and set at least:

```ini
# claude or codex, whichever CLI you are logged into
LLM_PROVIDER=claude
# Empty = the CLI's default model, or e.g. sonnet / opus for claude
LLM_MODEL=
# Only needed for phone access: a long random value (see below)
API_TOKEN=
```

Generate an `API_TOKEN` if you want phone access:

```bash
cd backend
uv run python -c "import secrets; print(secrets.token_urlsafe(24))"
```

Start the app:

```bash
cd backend
uv run uvicorn app.main:app --port 8000
```

Open <http://127.0.0.1:8000>. The backend serves both the API and the built UI. API docs are at
<http://127.0.0.1:8000/docs>.

After pulling new changes:

```bash
cd backend && uv sync
cd ../frontend && npm ci && npm run build
```

Then restart the backend.

Your data lives in `data/app.db` and `data/packages/`. This folder is git-ignored. Back it up from time to time.

## Using the app

The full first-run walkthrough, with a "what to check" list for each step, is in
[KURULUM.md](KURULUM.md) (Turkish). In short:

1. **Profile**: click *CV yükle* (upload CV), review the extracted draft, apply it, save.
2. **Projects**: add two or three projects with concrete bullets and technologies, or import JSON files
   shaped like [`contracts/examples/project.json`](contracts/examples/project.json). Importing the same file
   again updates existing projects instead of duplicating them.
3. **Add a posting by link** to test the package generation on a real posting. Greenhouse, Lever and
   company career pages work best. Check that the tailored CV contains nothing you did not actually do.
4. **Settings**: target roles, locations, seniority, minimum score (70 is a good start) and company
   short names for Greenhouse, Lever and Ashby. Save, then run **Şimdi tara** (scan now).
5. **Review the list**, open a posting, copy the cover letter and answers, open the PDF, and apply on
   the company's own site. Mark the posting as applied.

The interface is currently in Turkish.

## Configuration

Settings come from environment variables or the `.env` file in the repository root.
[`.env.example`](.env.example) lists the common ones.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `claude` | `claude` or `codex` |
| `LLM_MODEL` | empty | Model name passed to the CLI. Empty = the CLI default |
| `LLM_TIMEOUT_SECONDS` | `300` | Timeout for one LLM call |
| `LLM_MAX_CONCURRENCY` | `2` | Parallel LLM calls |
| `CLAUDE_BIN` / `CODEX_BIN` | `claude` / `codex` | Full path, if the CLI is not on `PATH` |
| `SEARCH_MAX_AGE_DAYS` | `30` | Ignore postings older than this |
| `SEARCH_MAX_SCORED_PER_RUN` | `40` | Postings sent to the LLM per run, to keep CLI usage in check |
| `SCHEDULER_ENABLED` | `true` | Run the daily scan while the backend is up |
| `API_TOKEN` | empty | Required for access from other devices. Empty = this computer only |
| `IMAP_HOST` / `IMAP_PORT` | `imap.gmail.com` / `993` | Mailbox for job-alert emails |
| `IMAP_USER` / `IMAP_PASSWORD` | empty | Mailbox login. For Gmail use an [app password](https://myaccount.google.com/apppasswords) |
| `IMAP_FOLDER` | `INBOX` | Folder to read |
| `EMAIL_LOOKBACK_DAYS` | `3` | How far back to read alert emails |
| `EMAIL_ALERT_SENDERS` | LinkedIn, Kariyer.net, Indeed, Glassdoor | Sender domains treated as job alerts (JSON list) |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` / `ADZUNA_COUNTRY` | empty / empty / `gb` | Adzuna API credentials and country |
| `DATA_DIR` / `DATABASE_URL` | `data/` / SQLite in `data/` | Where data is stored |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed origins (JSON list), for frontend development |

Search preferences (roles, locations, seniority, excluded keywords, minimum score, CV language, which sources
are on, and the schedule) are edited in the app's **Settings** page and stored in the database. The schedule
is a cron expression, `0 8 * * *` (every day at 08:00) by default.

## Job sources

| Source | Needs | Notes |
|---|---|---|
| Greenhouse | company short names in Settings | `job-boards.greenhouse.io/<name>` → `<name>` |
| Lever | company short names in Settings | `jobs.lever.co/<name>` → `<name>` |
| Ashby | company short names in Settings | `jobs.ashbyhq.com/<name>` → `<name>` |
| RemoteOK | nothing | on by default |
| Remotive | nothing | on by default |
| Arbeitnow | nothing | on by default |
| Adzuna | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | off by default |
| Job-alert emails | `IMAP_USER`, `IMAP_PASSWORD` | off by default. LinkedIn, Kariyer.net, Indeed, Glassdoor |

Company boards usually bring the most relevant postings, so add the short names of companies you care about.

**Job-alert emails.** The mailbox is opened **read-only**: nothing is marked as read, deleted or sent, and each
email is processed once. Alert emails only contain a short summary, so the full text is fetched from the
posting page when the package is prepared. If a site blocks that with a login wall, the package shows the
reason and you can paste the posting text and regenerate.

**The scheduler** runs only while the backend is running. If the computer was asleep at the scheduled time,
the scan runs once within 12 hours after it wakes up.

## Using it from your phone

Your phone connects to the backend on your own computer through [Tailscale](https://tailscale.com). The
backend is not exposed to the internet or to your home network, only to your own Tailscale devices.

1. Install Tailscale on the computer and the phone and sign in with the same account.
2. Put a long random `API_TOKEN` in `.env`, build the frontend and start the backend (see
   [Quick start](#quick-start)).
3. In another terminal, publish it over HTTPS inside your tailnet:
   ```bash
   tailscale serve --bg 8000
   ```
   It prints an address like `https://<your-computer>.<tailnet>.ts.net`. Check with `tailscale serve status`;
   turn it off with `tailscale serve --https=443 off`.
4. On the phone, open that address in Chrome with Tailscale on, enter the `API_TOKEN` once, then use
   *Install app* (or *Add to Home screen*) from the Chrome menu. It opens full-screen like a native app.

**Do not use `tailscale funnel`.** Funnel makes the address public to everyone. `serve` keeps it private.
When `API_TOKEN` is empty, requests that arrive through Tailscale are rejected (HTTP 403), so the data stays
closed even if you forget to set it. The phone works only while the computer is on, awake and the backend is running.

## Demo mode (no LLM needed)

To try the interface without an LLM or your real data, seed a separate demo database. It creates a profile,
projects, settings, one search run and seven postings in different states (package ready with a real PDF,
failed package, no package, applied, interview, manual).

macOS / Linux:

```bash
cd backend
export DATA_DIR=../data-demo DATABASE_URL=sqlite:///../data-demo/app.db
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --reload --port 8000
```

Windows (PowerShell):

```powershell
cd backend
$env:DATA_DIR="../data-demo"; $env:DATABASE_URL="sqlite:///../data-demo/app.db"
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --reload --port 8000
```

The frontend also has a **mock mode** that needs no backend at all. Put `VITE_USE_MOCK=true` in
`frontend/.env.development.local` and restart Vite. See [frontend/README.md](frontend/README.md).

## Development and tests

Run the backend and the frontend dev server in two terminals:

```bash
# terminal 1
cd backend
uv run uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. Requests to `/api` are proxied to the backend on port 8000.

```bash
cd backend && uv run pytest        # backend tests
cd frontend && npm test            # frontend tests
cd frontend && npm run build       # type-check and production build
```

The backend tests never call a real CLI. They run against fake scripts. More detail:
[backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md),
[frontend/TESTING.md](frontend/TESTING.md) and the design notes in [frontend/DESIGN.md](frontend/DESIGN.md).
The original project plan and API contract are in [plan.md](plan.md) (Turkish).

## Project layout

| Path | Contents |
|---|---|
| `backend/app/api/` | HTTP endpoints (profile, projects, jobs, search, settings) |
| `backend/app/llm/` | LLM runner, CV import, posting extraction, scoring, tailoring |
| `backend/app/sources/` | Job sources and the source registry |
| `backend/app/search/` | Pre-filter, search pipeline, scheduler |
| `backend/app/jobs/` | Fetching and normalising posting pages |
| `backend/app/render/` | CV HTML template and PDF rendering |
| `backend/app/services/` | Package generation flow |
| `backend/scripts/` | Demo data seeding |
| `backend/tests/` | Backend tests |
| `frontend/src/` | React pages, API client, mock API |
| `contracts/examples/` | Example JSON for the API contract |
| `profile.example/` | Example profile and project format |

## Privacy and safety

- **Your data stays local.** The database and generated files are in `data/`, which is git-ignored, as are
  `.env`, `profile/` and `profile*.zip`. Put your personal CV and project files in `profile/`.
- **What leaves your computer:** the text sent to the Claude or Codex CLI (your profile and the posting, to
  score and tailor), and ordinary web requests to the job sources and posting pages.
- **No API keys are stored.** LLM access is the CLI session you already have. The only secrets in `.env` are
  optional: the phone access token, a mailbox app password and Adzuna keys.
- **Review everything before you send it.** LLM output can be wrong. Check the CV, the cover letter and the
  answers against the truth, and fix anything that is off. You are responsible for what you submit.
- **Respect the job sites you use.** Check the terms of service of the sources you enable and keep the scan
  frequency reasonable.

Never commit your `.env`. If a token or password ever leaks, rotate it.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "command not found" for the CLI (HTTP 503) | The CLI is not installed or not on `PATH`. Set `CLAUDE_BIN` / `CODEX_BIN` in `.env` to its full path |
| "Failed to authenticate" (HTTP 502) | The CLI session expired. Run `claude`, then `/login` (or `codex login`) |
| Phone says remote access needs `API_TOKEN` | `API_TOKEN` is empty, or the backend was not restarted after you set it |
| Phone keeps asking for the key | `API_TOKEN` changed. Enter the new one |
| Phone shows HTTP 502 | The backend is stopped but Tailscale is still on. Start the backend |
| A package failed | The reason is shown under it. If the posting text could not be read, paste it and regenerate |
| Port 8000 is in use | Start with `--port 8001` and use `tailscale serve --bg 8001` |

## Contributing

Issues and pull requests are welcome. Before opening a pull request, run the backend tests, the frontend
tests and `npm run build`. Please never include personal data, CVs, `.env` files or tokens in a commit.

## License

[MIT](LICENSE)
