"""ResearchRadar command-line entry point."""
from __future__ import annotations

import sys

from researchradar.config import Settings
from researchradar.logging_config import configure_logging
from researchradar.pipeline.runner import PipelineRunner


def main() -> int:
    print("ResearchRadar\n-------------")
    try:
        settings = Settings.from_env()
    except (ValueError, OSError) as exc:
        print(f"Configuration error: {exc}")
        return 2
    topic = input("Enter a research topic: ").strip()
    if not topic:
        print("Please enter a non-empty research topic.")
        return 2
    configure_logging(settings.log_level)
    print("[1/6] Fetching arXiv papers...")
    print("[2/6] Fetching news...")
    print("[3/6] Fetching engineering blogs...")
    runner = PipelineRunner(settings)
    result = runner.run(topic)
    for status in result.statuses:
        if not status.success:
            print(f"Source warning ({status.source_name}): {status.error}")
        else:
            print(f"{status.source_name}: {status.item_count} items")
    print("[4/6] Filtering and deduplicating...")
    if result.error and result.digest is None:
        print(result.error)
        return 1
    print("[5/6] Generating digest with Gemini...")
    if result.delivery_status == "sent":
        print("[6/6] Sending digest to Telegram...")
        print(f"Research digest sent successfully ({len(result.items)} items).")
        return 0
    print("[6/6] Sending digest to Telegram...")
    print(f"Delivery failed: {result.error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
