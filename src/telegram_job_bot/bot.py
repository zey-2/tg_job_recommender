"""Telegram bot application wiring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes)

from .adzuna_client import AdzunaClient
from .config import Settings
from .database import Interaction, Job, User, create_session_factory, session_scope, upsert_user
from .keywords import KeywordManager
from .recommender import JobRecommender, ScoredJob


@dataclass(slots=True)
class BotDependencies:
    settings: Settings
    session_factory: callable
    adzuna: AdzunaClient
    recommender: JobRecommender
    keyword_manager: KeywordManager


@dataclass(slots=True)
class SearchKeyword:
    """Lightweight keyword representation used for ad-hoc search scoring."""

    keyword: str
    weight: float = 1.0
    is_negative: bool = False


def create_application(settings: Settings) -> Application:
    SessionFactory = create_session_factory(settings)
    deps = BotDependencies(
        settings=settings,
        session_factory=SessionFactory,
        adzuna=AdzunaClient(settings),
        recommender=JobRecommender(),
        keyword_manager=KeywordManager(
            like_boost=settings.like_boost,
            dislike_penalty=settings.dislike_penalty,
            weight_decay=settings.weight_decay,
            max_keywords=settings.max_keywords,
            negative_promote_at=settings.negative_promote_at,
        ),
    )

    application = (
        Application.builder()
        .token(settings.telegram_token)
        .build()
    )
    application.bot_data["deps"] = deps

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("keywords", show_keywords))
    application.add_handler(CommandHandler("more", more))
    application.add_handler(CommandHandler("search", search_jobs))
    application.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^(like|dislike):"))

    return application


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    deps = context.application.bot_data["deps"]
    with session_scope(deps.session_factory) as session:
        upsert_user(session, user_id=user.id, username=user.username)
    chat = update.effective_chat
    await chat.send_message(
        "👋 Welcome! Use /more to get fresh job leads or /keywords to review your adaptive profile."
    )


async def show_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps = context.application.bot_data["deps"]
    chat = update.effective_chat
    with session_scope(deps.session_factory) as session:
        user = session.get(User, update.effective_user.id)
        if not user or not user.keywords:
            await chat.send_message("No keywords yet. Interact with jobs to teach the bot!")
            return
        lines = ["<b>Top keywords</b>"]
        for keyword in sorted(user.keywords, key=lambda kw: kw.weight, reverse=True):
            prefix = "🚫" if keyword.is_negative else "✅"
            lines.append(f"{prefix} <b>{keyword.keyword}</b> ({keyword.weight:.2f})")
            if keyword.rationale:
                lines.append(f" └ {keyword.rationale}")
    await chat.send_message("\n".join(lines), parse_mode=ParseMode.HTML)


async def more(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: BotDependencies = context.application.bot_data["deps"]
    settings = deps.settings
    user_id = update.effective_user.id

    chat = update.effective_chat
    with session_scope(deps.session_factory) as session:
        user = upsert_user(session, user_id=user_id, username=update.effective_user.username)
        deps.keyword_manager.decay(user.keywords)
        keywords = [kw.keyword for kw in user.keywords if not kw.is_negative][: settings.max_keywords]
        if not keywords:
            keywords = ["software", "engineer"]

        postings = deps.adzuna.search(keywords)
        scored = deps.recommender.score_jobs(postings, user.keywords)

        if not scored:
            await chat.send_message("No matching jobs right now. Try again later!")
            return

        top = scored[: settings.realtime_max_count]
        for item in top:
            job_card = format_job_card(item.job, item.score, item.matched_keywords)
            await chat.send_message(
                job_card,
                reply_markup=_feedback_keyboard(item.job.job_id, item.job.url),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )

        store_jobs(session, [item.job for item in top])


async def search_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat:
        return

    query = " ".join(context.args).strip()
    if not query:
        await chat.send_message("Usage: /search <keywords>")
        return

    deps: BotDependencies = context.application.bot_data["deps"]
    settings = deps.settings
    terms = [term for term in context.args if term.strip()]

    try:
        postings = deps.adzuna.search(terms)
    except Exception:
        await chat.send_message("Search is unavailable right now. Please try again later.")
        return

    if not postings:
        await chat.send_message(f'No jobs found for "{query}".')
        return

    search_keywords = _build_search_keywords(terms)
    with session_scope(deps.session_factory) as session:
        upsert_user(session, user_id=update.effective_user.id, username=update.effective_user.username)
        scored = deps.recommender.score_jobs(postings, search_keywords)
        if not scored:
            scored = [ScoredJob(job=posting, score=0.0, matched_keywords=[]) for posting in postings]

        top = scored[: settings.realtime_max_count]
        if not top:
            await chat.send_message(f'No jobs found for "{query}".')
            return

        await chat.send_message(f'Top matches for "{query}":')
        for item in top:
            job_card = format_job_card(item.job, item.score, item.matched_keywords)
            await chat.send_message(
                job_card,
                reply_markup=_feedback_keyboard(item.job.job_id, item.job.url),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )

        store_jobs(session, [item.job for item in top])


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        return
    await update.callback_query.answer()
    deps: BotDependencies = context.application.bot_data["deps"]
    action, job_id = update.callback_query.data.split(":", 1)
    liked = action == "like"
    user_id = update.effective_user.id

    with session_scope(deps.session_factory) as session:
        user = upsert_user(session, user_id=user_id, username=update.effective_user.username)
        job = session.get(Job, job_id)
        if not job:
            await update.callback_query.edit_message_text("Job context expired. Try /more again for fresh listings.")
            return

        tokens = getattr(job, "desc", "").split() if getattr(job, "desc", None) else job.title.split()
        deps.keyword_manager.apply_feedback(user.keywords, tokens, liked)

        interaction = Interaction(user_id=user_id, job_id=job_id, action="like" if liked else "dislike")
        session.add(interaction)

        message = "Thanks for the feedback!" if liked else "Got it. We'll tune your matches."
        await update.callback_query.edit_message_text(message)


def format_job_card(job: Job | JobPosting, score: float, matched_keywords: Sequence[str]) -> str:
    company = f"<b>{job.company}</b>" if getattr(job, "company", None) else ""
    location = getattr(job, "loc", None) or getattr(job, "location", "")
    parts = [f"<b>{job.title}</b>"]
    if company:
        parts.append(company)
    if location:
        parts.append(location)

    summary = (getattr(job, "desc", None) or getattr(job, "description", "") or "")[:280]
    matched = ", ".join(matched_keywords)
    body = "\n".join(filter(None, parts))
    extras = []
    if matched:
        extras.append(f"🎯 {matched}")
    extras.append(f"⭐ Score: {score:.2f}")
    return f"{body}\n\n{summary}\n\n" + "\n".join(extras)


def store_jobs(session, postings: Iterable[JobPosting]) -> None:
    for posting in postings:
        if session.get(Job, posting.job_id):
            continue
        job = Job(
            job_id=posting.job_id,
            title=posting.title,
            company=posting.company,
            loc=posting.location,
            desc=posting.description,
            url=posting.url,
            posted_at=_parse_posted_at(posting.created),
        )
        session.add(job)


def _parse_posted_at(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _feedback_keyboard(job_id: str, url: str | None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\U0001f44d Like", callback_data=f"like:{job_id}"),
                InlineKeyboardButton("\U0001f44e Dislike", callback_data=f"dislike:{job_id}"),
                InlineKeyboardButton("\U0001f517 View", url=url or ""),
            ]
        ]
    )


def _build_search_keywords(terms: Sequence[str]) -> list[SearchKeyword]:
    seen = set()
    keywords: list[SearchKeyword] = []
    for term in terms:
        cleaned = term.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        keywords.append(SearchKeyword(keyword=cleaned))
    return keywords
