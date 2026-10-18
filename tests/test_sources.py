import json
from types import SimpleNamespace

from researchradar.sources.arxiv_source import ArxivSource
from researchradar.sources.news_source import GNewsSource
from researchradar.sources.rss_source import RSSSource


class Response:
    def __init__(self, body, status=200):
        self.text = body if isinstance(body, str) else ""
        self._body, self.status_code = body, status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(response=self)

    def json(self):
        return self._body


def test_arxiv_maps_atom_fields():
    xml = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <id>https://arxiv.org/abs/1</id><title> A paper </title>
      <summary>An abstract with enough useful content for a test.</summary>
      <published>2025-01-01T00:00:00Z</published>
      <author><name>Ada</name></author></entry></feed>"""
    result = ArxivSource(request=lambda *a, **k: Response(xml)).fetch("paper")
    assert result.status.success and result.items[0].authors == ["Ada"]


def test_gnews_success_and_invalid_response():
    good = {"articles": [{"title": "RAG update", "url": "https://example.com/a",
                          "description": "A useful description for this article.",
                          "source": {"name": "Example"}, "publishedAt": "2025-01-01T00:00:00Z"}]}
    result = GNewsSource("secret", request=lambda *a, **k: Response(good)).fetch("RAG")
    assert result.status.success and result.items[0].source_name == "Example"
    bad = GNewsSource("secret", request=lambda *a, **k: Response({"wrong": []})).fetch("RAG")
    assert not bad.status.success and not bad.items


def test_rss_continues_after_bad_feed():
    good = SimpleNamespace(
        bozo=False,
        feed={"title": "Engineering"},
        entries=[{"title": "RAG post", "link": "https://example.com/r",
                  "summary": "A sufficiently long RSS summary for a valid test item."}],
    )
    def parse(url, **kwargs):
        if "bad" in url:
            raise OSError("offline")
        return good
    result = RSSSource(("https://bad.example", "https://good.example"), parser=parse).fetch("RAG")
    assert len(result.items) == 1 and result.status.error
