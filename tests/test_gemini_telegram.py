from types import SimpleNamespace

import pytest

from researchradar.delivery.telegram import TelegramDelivery, TelegramDeliveryError, split_message
from researchradar.models import Record
from researchradar.summarization.gemini_client import GeminiSummarizer, GeminiError


def record():
    return Record.create("RAG paper", "arxiv", "arXiv", "https://arxiv.org/abs/1",
                         "A useful abstract about retrieval augmented generation " * 2, "RAG")


def test_gemini_uses_only_evidence_and_rejects_bad_url():
    class Models:
        def generate_content(self, **kwargs):
            assert "https://arxiv.org/abs/1" in kwargs["contents"]
            assert "QUICK TAKE" in kwargs["contents"]
            assert "KEY UPDATES" in kwargs["contents"]
            assert "under 2500 characters" in kwargs["contents"]
            return SimpleNamespace(text="Summary based on evidence. Sources: https://arxiv.org/abs/1")
    result = GeminiSummarizer("key", "model", client=SimpleNamespace(models=Models())).summarize("RAG", [record()])
    assert "Summary" in result.text

    class BadModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(text="Made up https://evil.example/a")
    with pytest.raises(GeminiError):
        GeminiSummarizer("key", "model", retries=0, client=SimpleNamespace(models=BadModels())).summarize("RAG", [record()])


def test_gemini_empty_list_never_calls_client():
    with pytest.raises(GeminiError):
        GeminiSummarizer("key", "model", client=object()).summarize("RAG", [])


def test_telegram_splits_and_confirms_response():
    sent = []
    class Response:
        status_code = 200
        def json(self):
            return {"ok": True, "result": {"message_id": 1}}
    def post(url, **kwargs):
        assert "key" in url and kwargs["json"]["chat_id"] == "chat"
        sent.append(kwargs["json"]["text"])
        return Response()
    delivery = TelegramDelivery("key", "chat", max_chars=100, post=post)
    assert delivery.send("paragraph\n\n" + ("word " * 100)) > 1
    assert all(len(part) <= 100 for part in sent)


def test_telegram_api_error():
    class Response:
        status_code = 400
        def json(self):
            return {"ok": False, "description": "bad request"}
    with pytest.raises(TelegramDeliveryError):
        TelegramDelivery("key", "chat", post=lambda *a, **k: Response()).send("hello")
