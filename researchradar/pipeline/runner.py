"""Orchestrates collection, processing, Gemini, Telegram, and durable state."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..config import Settings
from ..db import Database
from ..delivery.telegram import TelegramDelivery
from ..models import CollectionResult, Digest, Record, SourceStatus
from ..processing.deduplicate import deduplicate
from ..processing.normalize import normalize_records
from ..processing.quality import filter_quality
from ..processing.ranking import rank_items
from ..sources.arxiv_source import ArxivSource
from ..sources.news_source import make_news_source
from ..sources.rss_source import RSSSource
from ..summarization.gemini_client import GeminiError, GeminiSummarizer

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    run_id: int
    items: list[Record] = field(default_factory=list)
    statuses: list[SourceStatus] = field(default_factory=list)
    digest: Digest | None = None
    delivery_status: str = "not_attempted"
    error: str | None = None
    dedup_warning: str | None = None


class PipelineRunner:
    def __init__(self, settings: Settings, database: Database | None = None,
                 summarizer: GeminiSummarizer | None = None,
                 delivery: TelegramDelivery | None = None):
        self.settings = settings
        self.database = database or Database(settings.sqlite_path)
        self.summarizer = summarizer or GeminiSummarizer(
            settings.gemini_api_key, settings.gemini_model, settings.gemini_max_input_chars,
            settings.max_retries,
        )
        self.delivery = delivery or TelegramDelivery(
            settings.telegram_bot_token, settings.telegram_chat_id, settings.request_timeout_seconds,
            settings.telegram_max_message_chars, settings.max_retries,
        )

    def run(self, topic: str) -> PipelineResult:
        run_id = self.database.start_run(topic)
        statuses: list[SourceStatus] = []
        collected: list[Record] = []
        sources = [
            ArxivSource(self.settings.request_timeout_seconds, self.settings.max_retries, self.settings.arxiv_max_results),
            make_news_source(self.settings.news_api_provider, self.settings.gnews_api_key,
                             timeout=self.settings.request_timeout_seconds, retries=self.settings.max_retries,
                             max_results=self.settings.news_max_results),
            RSSSource(self.settings.rss_feeds, self.settings.request_timeout_seconds,
                      self.settings.rss_max_results_per_feed),
        ]
        for source in sources:
            try:
                result = source.fetch(topic)
            except Exception as exc:
                source_type = getattr(source, "source_type", source.__class__.__name__.lower())
                source_name = getattr(source, "name", source.__class__.__name__)
                result = CollectionResult(
                    [],
                    SourceStatus(
                        source_type,
                        source_name,
                        success=False,
                        error=f"{type(exc).__name__}: {exc}",
                    ),
                )
            statuses.append(result.status)
            collected.extend(result.items)
        self.database.save_source_statuses(run_id, statuses)
        processed = filter_quality(normalize_records(collected), self.settings.min_text_length)
        deduped, warning = deduplicate(processed, self.settings.semantic_dedup_enabled,
                                        self.settings.semantic_dedup_threshold)
        ranked = rank_items(deduped, topic, self.settings.max_total_items)
        seen = self.database.seen_ids(ranked)
        self.database.upsert_items(ranked)
        selected = [item for item in ranked if not self.settings.only_new_items or item.id not in seen]
        self.database.save_run_items(run_id, ranked, included=False)
        self.database.save_run_items(run_id, selected, included=True)
        result = PipelineResult(run_id, selected, statuses, dedup_warning=warning)
        if not selected:
            result.error = "No usable new items were found." if self.settings.only_new_items else "No usable items were found."
            self.database.set_delivery(run_id, "not_attempted")
            self.database.finish_run(run_id, "no_items", 0, result.error)
            return result
        try:
            result.digest = self.summarizer.summarize(topic, selected)
        except Exception as exc:
            result.error = str(exc)
            self.database.set_delivery(run_id, "not_attempted", error=result.error)
            self.database.finish_run(run_id, "failed", len(selected), result.error)
            return result
        try:
            parts = self.delivery.send(result.digest.text)
            result.delivery_status = "sent"
            self.database.set_delivery(run_id, "sent", parts_sent=parts)
            self.database.finish_run(run_id, "delivered", len(selected))
        except Exception as exc:
            result.error = str(exc)
            result.delivery_status = "failed"
            self.database.set_delivery(run_id, "failed", error=result.error)
            self.database.finish_run(run_id, "failed", len(selected), result.error)
        return result
