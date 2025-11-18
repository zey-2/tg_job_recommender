<!-- Copilot / AI agent instructions for contributors and automation -->

# Repository Intent

This repository is a small Telegram Job Recommendation Bot that learns user preferences from likes/dislikes, expands keywords via an LLM (OpenAI), ranks jobs from Adzuna, and sends daily digests.

# Quick Architecture Summary

- Entry point: `main.py` — supports `polling` (default), `webhook <port>`, and `digest` commands.
- Telegram handlers: `bot.py` — defines `JobBot`, command handlers, and application construction (`create_application`).
- Keyword & ranking: `keyword_manager.py` — tokenization, job scoring, ranking, and feedback-driven keyword updates.
- LLM integration: `llm_service.py` — `LLMKeywordService` uses OpenAI (`gpt-4o-mini`) to suggest keywords and explain recommendations.
- Job source: `adzuna_client.py` — wraps Adzuna REST API calls (`search_jobs`, `search_by_keywords`, `get_recent_jobs`).
- Persistence: `database.py` — lightweight SQLite DB, table schemas and helper methods (users, user_keywords, jobs, interactions).
- Scheduler: `scheduler.py` — builds and sends the daily digest; `run_digest()` is used by `main.py digest` and cloud cron endpoints.
- Config: `config.py` — environment-driven constants (TOP_K, DECAY, LIKE_BOOST, NEGATIVE_PROMOTE_AT, TELEGRAM_BOT_TOKEN, ADZUNA creds, OPENAI_API_KEY).

# Primary developer workflows (how to run & debug)

- Local dev (polling): `python main.py` — starts the bot in polling mode.
- Webhook (cloud run / production): `python main.py webhook 8080` — requires `WEBHOOK_BASE_URL` (or `RENDER_EXTERNAL_URL`) to be set.
- Digest run (manual/test): `python main.py digest` — runs the one-off digest job using `scheduler.run_digest()`.
- Install: `pip install -r requirements.txt` and create `.env` from `.env.example`.

# Important conventions & patterns (project-specific)

- Single global instances: many modules expose a module-level getter that returns a singleton (e.g., `get_db()`, `get_adzuna_client()`, `get_keyword_manager()`, `get_llm_service()`, `get_bot()`). Prefer to call those instead of instantiating new ones.
- Database-first caching: jobs are cached with `db.upsert_job(job)` before logging interactions.
- Keyword polarity: keywords have `weight` and `is_negative` flags. Negative keywords are treated specially — there is a `NEGATIVE_PROMOTE_AT` threshold in `config.py` that flips polarity behavior.
- Weight lifecycle: feedback updates (likes/dislikes) adjust weights then `DECAY` is applied and `_prune_keywords` keeps only top positives and active negatives.
- LLM output: `llm_service.expand_keywords()` expects a JSON array response and the code attempts robust parsing (searches for JSON in response). When updating prompts or models, keep JSON-only response requirement intact.

# Files to inspect when making changes

- `bot.py`: add new command handlers here. Use `create_application()` and add handlers to the returned `Application`.
- `keyword_manager.py`: contains ranking and update logic — changes here affect production recommendations heavily.
- `llm_service.py`: contains prompt + model selection; tests should validate returned JSON parsing.
- `database.py`: schema and utility functions — if adding fields, update table creation and `upsert` patterns.
- `adzuna_client.py`: API request format; keep `results_per_page` under 50 and watch `what`/`where` parameters.

# Config & secrets

- All runtime configuration comes from environment variables read in `config.py`. Sensitive values: `TELEGRAM_BOT_TOKEN`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `OPENAI_API_KEY`.
- To change behavior: update `config.py` values or set environment variables. Typical values to tune: `TOP_K`, `DECAY`, `LIKE_BOOST`, `DISLIKE_PENALTY`, `NEGATIVE_PROMOTE_AT`.

# LLM & prompt guidelines (project-specific)

- The LLM is used to propose concrete, searchable keywords (skills, roles, tools). Keep prompts focused on returning "ONLY a valid JSON array" to simplify parsing.
- Model: default currently set to `gpt-4o-mini` in `llm_service.py`. If switching models, ensure parameters (`max_tokens`, `temperature`) and client API match the SDK in `openai` used here.

# Testing & debug guidance

- There are no unit tests in the repo. For quick verification:
  - Run `python main.py digest` to exercise the scheduler, Adzuna integration, ranking, and message formatting.
  - Use `python main.py` and interact with the bot on Telegram (polling) to exercise handlers.
  - Use local SQLite DB file (`DATABASE_PATH`, default `job_bot.db`) to inspect `user_keywords`, `jobs`, `interactions`.
- Logging: modules use Python `logging` — review logs in `bot.log` (main config in `main.py`) and console output.

# Small code examples (how to make common edits)

- Add a command handler in `bot.py`:
  1. Create an async method on `JobBot` (e.g., `async def new_command(self, update, context): ...`).
  2. Register it in `create_application()` with `application.add_handler(CommandHandler("name", self.new_command))`.

3.  Add a `BotCommand` entry in `set_commands()` to expose it in clients.

- Change keyword scoring behavior:
  - Edit `KeywordManager.score_job()` in `keyword_manager.py`. Tests/manual runs: run `main.py digest` or use `/more` in polling mode to verify effects.

# Integration points & external dependencies

- Adzuna REST API — network calls in `adzuna_client.py` (watch API key quotas and `results_per_page`).
- OpenAI — `openai.OpenAI` client used in `llm_service.py`. Ensure `OPENAI_API_KEY` has permissions and billing enabled.
- Telegram Bot API — `python-telegram-bot` is used (v20+ async Application). Webhook usage requires a reachable HTTPS `WEBHOOK_BASE_URL`.

# When editing prompts or LLM behavior

- Keep prompt deterministic as much as possible and continue to parse for a JSON array. If you change the prompt structure, update parsing logic in `llm_service.expand_keywords()` accordingly.

# What I should ask you if anything is unclear

- Which environment you use for deploy (Cloud Run, Render, local polling).
- If there are undocumented env variables or custom runtime changes you've made in your environment.
- Whether you want the instructions to be stricter about coding style, tests, or commit hooks.

---

If you'd like, I can open a PR with this file, adjust tone/length, or include short examples for common refactors. Any missing details you want added?
