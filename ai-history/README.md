# AI build history

This folder is the "AI build history" attachment required by the challenge brief — the coding-agent conversations used to build FINN, submitted unedited.

## Main build session

- **`finn-build-session.json`** — the complete opencode session export (raw, unmodified): 427 messages, 425 tool calls, 192 text parts. Contains every user prompt, agent response, reasoning block and tool invocation (shell commands, file edits, probes, test runs) from the first `mkdir finn` to the deploy prep.
- **`finn-build-session.md`** — the same session rendered for reading: user prompts and agent answers in full, tool calls summarised as one-liners with outputs sized.

Session facts: opencode v1.19.5 · model GLM (`hyde/glm-5.3-flash`) · ~1.35M input / 149k output tokens (74M cached-read tokens — caching did its job here too) · single continuous session.

### Why it is filed as a "global" session

The conversation that built FINN **started before the repository existed**. The shell's working directory was `C:\Windows\system32` (`/mnt/c/WINDOWS/system32` under WSL) — the default of the Windows terminal it was launched from — and `~/projects/finn` was created *by the agent* inside that same conversation. opencode therefore filed the session under its global (project-agnostic) store instead of a repo-scoped one. The export was produced with opencode's session export and copied into this folder manually at submission time.

To re-export or inspect other sessions: `opencode export <session-id>` (see `opencode --help`); sessions live under `~/.local/share/opencode/`.

## What the session shows

The full arc, in one conversation: challenge-brief ingestion and source probing (NSE 403 → `curl_cffi` bypass), plan negotiation with the user, backend build step-by-step with live data verification, three user review rounds (17/18 test suites, cheap-first routing, citation discipline), the frontend design critique from screenshots, and deploy preparation — including every course-correction the user made, with the raw outputs that justified them.

## Hygiene note

Secrets were never entered in chat: API keys live only in `backend/.env` (gitignored) and were provided by the user out-of-band. Both files in this folder were scanned for key material before committing (patterns: Gemini `AIza…`, Tavily `tvly-…`, generic `sk-`/Bearer tokens, `.env` dumps) — see the scan results recorded in `docs/PROGRESS.md`.
