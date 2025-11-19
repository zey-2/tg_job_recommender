# Telegram Job Recommendation Bot (Adzuna + LLM + Adaptive Keywords)

## Overview

This Telegram bot delivers personalized job notifications based on user
preferences and feedback. It integrates the **Adzuna Job Search MCP**, a
lightweight **LLM keyword learning loop**, and adaptive scoring logic.

---

## Features

### 🧠 Adaptive User Profiling

- Each user is represented by their **Top 8 adaptive keywords**.
- Keywords are updated every time a job is liked or disliked.
- Positive keywords are reinforced; negatives are penalized and decay
  over time.

### 🤖 LLM Keyword Expansion

- Trigger: every explicit like/dislike sends the job title, company, short description, and the user’s current keyword list (with weights + polarity flags) to the LLM.
- Prompt contract: the model returns 8–10 suggestions, each tagged with `keyword`, `sentiment` (`positive`/`negative`), and an optional `rationale`.
- Merge logic:
  - Existing keyword → bump or penalize its weight (`LIKE_BOOST`/`DISLIKE_PENALTY`) and update the rationale history.
  - New keyword → insert with a seed weight proportional to the LLM confidence (e.g., 0.5 for neutral, 1.0 for strong positive) and polarity derived from the user reaction.
  - Conflicting polarity suggestions are resolved by comparing cumulative weights and demoting items below `NEGATIVE_PROMOTE_AT`.
- Ranking: re-normalize weights, keep the top `TOP_K` positive terms plus any active negatives, and persist both the scores and concise rationales for `/view_keywords`.

### 📈 Recommendation Logic

Jobs are scored with a hybrid pipeline:

- **Keyword Match Score:** tokenize job title + description, then compute a weighted sum of matched user keywords (cosine similarity optional for fuzzy matching); cap contributions from any single keyword to avoid dominance.
- **Negative Filter:** immediately reject jobs containing hard negatives (e.g., blocked companies); soft negatives subtract their weight.
- **Context Boosts:** optional boosts for recency, salary range, or location fit (using user prefs).
- **Decay + Diversity:** after each recommendation cycle, multiply all keyword weights by `DECAY` (≈0.98) and add a small penalty to jobs recently shown to avoid repeats.
- **Top-N Selection:** sort by final score, take top 2–3 for `/more` real-time pulls and top 5 for the daily digest, storing the scored list so dislike actions can reference the original context.

### 💬 Telegram UX

- Inline job cards: \[View\] \[👍 Like\] \[👎 Dislike\]
- `/start` or `/help` → register user (if new) or resend the quick-start menu
- `/more` → 2--3 instant recommendations
- `/search <keywords>` → ad-hoc query for jobs matching the supplied terms (ignores the adaptive profile)
- `/view_keywords` → shows current Top 8 keywords
- `/prefs` → user filter preferences (optional)
- `/set_time` → set preferred daily notification time in 30-minute slots (09:00, 09:30, …; default: 09:00 SGT)
- `/toggle_notifications` → toggle daily digest notifications on/off

---

## 🧱 System Architecture

```mermaid
graph TD
    A[User in Telegram] -->|/start, /more| B(Telegram Bot)
    B --> C[Job Fetcher (Adzuna API)]
    C --> D[Job Scorer]
    D --> E[Keyword Store (SQLite/Postgres)]
    E --> F[LLM Keyword Generator]
    F --> E
    D -->|Top Jobs| A
```

---

## ⏰ Notification Scheduling

- Each user persists `notification_time`, `timezone`, and a computed `next_digest_at`.
- `notification_time` is quantized to 30-minute slots (09:00, 09:30, …) so scheduler checks align with user expectations.
- A single Cloud Scheduler job hits a secured Cloud Run endpoint every 30 minutes.
- The handler loads users with `next_digest_at <= now`, sends their digest, then advances `next_digest_at` by 24 hours.
- Cloud Scheduler acts as the timer, so the service scales to zero between webhook/scheduler invocations; no APScheduler loop is required.
- Deploy a single Cloud Run service with two HTTP routes: one for Telegram webhooks (on-demand user interactions) and another `/digest-cron` route invoked by Cloud Scheduler.

---

## 🔗 Adzuna Integration

**Endpoint:** `https://api.adzuna.com/v1/api/jobs/sg/search/{page}`\
**Auth:** `app_id`, `app_key`\
**Params:** `what`, `where`, `results_per_page`, `salary_min`,
`sort_by=date`

Example function:

```python
def adzuna_search_sg(keywords, where="Singapore", page=1, per_page=25):
    params = {
        "app_id": os.environ["ADZUNA_APP_ID"],
        "app_key": os.environ["ADZUNA_APP_KEY"],
        "results_per_page": per_page,
        "what": " ".join(keywords),
        "where": where,
        "sort_by": "date",
    }
    url = "https://api.adzuna.com/v1/api/jobs/sg/search/{}".format(page)
    return requests.get(url, params=params).json()["results"]
```

---

## ⚙️ Configuration

Setting Description Default

---

`TOP_K` Max adaptive keywords 8
`REALTIME_MIN/MAX` Jobs per real-time push 2--3
`DAILY_COUNT` Jobs per daily digest 5
`DECAY` Weight decay per update 0.98
`LIKE_BOOST` Reinforcement for liked jobs +1.0
`DISLIKE_PENALTY` Penalty for disliked jobs -1.0
`NEGATIVE_PROMOTE_AT` Threshold to mark keyword negative -2.0
`DEFAULT_NOTIFICATIONS` Default notification setting true
`DEFAULT_NOTIFICATION_TIME` Default daily notification time (30 min slots) "09:00"

---

## 💾 Database Schema (SQLite)

---

Table Key Columns Description

---

**users** `user_id`, `tg_username`, Telegram users and
`prefs_json` preferences (e.g., {"notifications": true, "location": "Singapore", "notification_time": "09:00"})

**user_keywords** `user_id`, `keyword`, Adaptive keyword store
`weight`, `is_negative`

**jobs** `job_id`, `title`, Cached Adzuna jobs
`company`, `loc`, `desc`,  
 `url`, `posted_at`

**interactions** `user_id`, `job_id`, Feedback log
`action`, `ts`

---

---

## 🔄 Adaptive Learning Cycle

1.  Fetch top jobs from Adzuna.
2.  Rank by user keyword match.
3.  Send jobs via Telegram.
4.  User clicks 👍 / 👎.
5.  Update keyword weights.
6.  Regenerate Top 8 with LLM.
7.  Repeat daily.

---

## 🧰 Tech Stack

Component Technology

---

Bot `python-telegram-bot`
LLM `OpenAI`
Database `SQLite`
Scheduler `Cloud Scheduler + Cloud Run cron endpoint`
Deployment `Cloud Run`
Source Adzuna API (`jobs/sg/search`)

---

## 🧩 Future Upgrades

- Add embeddings (SentenceTransformers / Gemini Embedding API).
- Add multi-profile (e.g., "Data", "Engineering", "Radar" tracks).
- "Why this job?" explanation with highlighted matched keywords.
- Admin panel to monitor CTR / Like rate / Keyword drift.
