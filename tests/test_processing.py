from researchradar.models import Record
from researchradar.processing.deduplicate import deduplicate
from researchradar.processing.quality import filter_quality, is_relevant
from researchradar.processing.ranking import rank_items


def item(title, url, text="RAG retrieval augmented generation details and evaluation.",
         source="news", topic="RAG"):
    return Record.create(title, source, "Test", url, text, topic)


def test_quality_keeps_abstract_and_rejects_invalid():
    assert len(filter_quality([item("valid", "https://example.com/a", "RAG abstract " * 10)])) == 1
    assert not filter_quality([item("", "not-a-url", "RAG " * 20)])


def test_exact_dedup_keeps_related_url():
    records, warning = deduplicate([item("Same", "https://example.com/a"),
                                    item("Same", "https://example.com/a#part")], enabled=False)
    assert len(records) == 1 and warning is None


def test_semantic_duplicate_with_injected_embeddings():
    class Model:
        def encode(self, texts, normalize_embeddings=True):
            return [[1.0, 0.0] if "first" in text else [0.99, 0.01] for text in texts]
    records, _ = deduplicate([item("first", "https://one.example"),
                              item("second", "https://two.example")], embedding_model=Model(), threshold=.9)
    assert len(records) == 1 and records[0].related_urls == ["https://two.example"]


def test_unrelated_items_and_stable_ranking():
    records, _ = deduplicate([item("RAG", "https://one.example"),
                              item("RAG", "https://two.example", text="RAG " * 10)], enabled=False)
    ranked = rank_items(records, "RAG", max_total=1)
    assert len(ranked) == 1


def test_relevance_rejects_one_weak_body_mention():
    relevant = item("Horse welfare policy", "https://one.example",
                    "Horse welfare policy and horse safety are discussed in detail.",
                    topic="horse")
    unrelated = item("AI benchmark results", "https://two.example",
                     "This article discusses language models and evaluation. It mentions horse once.",
                     topic="horse")
    assert is_relevant(relevant)
    assert not is_relevant(unrelated)


def test_relevance_accepts_strong_partial_match_for_multiword_topic():
    record = item(
        "AI agents automate business workflows",
        "https://three.example",
        "Automation with AI agents is changing repetitive business processes.",
        topic="automation using ai agents",
    )
    assert is_relevant(record)
