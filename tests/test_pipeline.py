"""Offline tests: no network. Run with `pytest -q`."""
from __future__ import annotations

import json
import time

from demand_scanner import pain
from demand_scanner.cluster import cluster
from demand_scanner.models import Signal
from demand_scanner.report import to_html, to_markdown, write_all
from demand_scanner.scanner import ScanResult
from demand_scanner.scoring import grade, niche_score, score_points
from demand_scanner.solutions import build_brief, recommend
from demand_scanner.sources.google_trends import momentum
from demand_scanner.sources.hackernews import HackerNews
from demand_scanner.sources.base import ScanContext
from demand_scanner.text import mentions_niche, niche_keywords, stem

NOW = time.time()


def sig(text, source="reddit", score=10, comments=2, kind="post", author=None, days=10, **meta):
    return Signal(source=source, kind=kind, title=text, text="", url=f"https://x/{hash(text)}",
                  score=score, comments=comments, created_utc=NOW - days * 86400,
                  author=author or f"u{abs(hash(text)) % 1000}", meta=meta)


def corpus():
    return [
        sig("I hate chasing late invoice payments from clients, is there a tool that sends reminders?"),
        sig("Chasing late payments from clients is so frustrating, I'd pay for automatic reminders", source="hackernews"),
        sig("Any app that automatically sends late payment reminders to clients? tired of chasing", source="bluesky"),
        sig("Late payments reminders for clients - manually emailing every week is tedious", source="stackexchange"),
        sig("FreshBooks is too expensive for a solo freelancer invoicing, looking for a cheaper alternative"),
        sig("Alternative to FreshBooks? pricing went up and it's overpriced for freelance invoicing", source="hackernews"),
        sig("Switching from FreshBooks, too expensive per month for simple freelance invoicing", source="bluesky"),
        sig("Great weather today for a walk", source="bluesky"),
    ]


def test_stem_collapses_variants():
    assert stem("invoicing") == stem("invoices") == stem("invoice")


def test_pain_detection_categories():
    score, tags = pain.detect("Is there an app for this? I would pay for it, the current one is so frustrating")
    assert score > 0.7
    assert {"tool_seeking", "willingness_to_pay", "frustration"} <= set(tags)
    assert pain.detect("Lovely sunny afternoon")[0] == 0


def test_query_hints():
    score, tags = pain.detect("invoice app alternative", kind="query")
    assert score > 0 and "alternative" in tags


def test_relevance_filter():
    kw = niche_keywords("freelance invoicing")
    assert mentions_niche("My freelance invoices are a mess", kw)
    assert not mentions_niche("Great weather today", kw)


def test_cluster_and_score():
    sigs = corpus()
    pain.annotate(sigs)
    points = cluster(sigs, niche_keywords("freelance invoicing"))
    points = [p for p in points if len(p.signals) >= 2]
    assert len(points) >= 2
    score_points(points, momentum=0.2, n_sources=4)
    assert points[0].score >= points[-1].score
    for p in points:
        assert 0 <= p.score <= 100
        assert set(p.components) >= {"volume", "wtp", "gap", "intensity"}
        p.solutions = recommend(p)
        assert p.solutions and p.solutions[0]["type"]
    labels = " ".join(p.label.lower() for p in points)
    assert "remind" in labels or "late" in labels or "chas" in labels
    assert "freshbook" in labels or "expensive" in labels or "pricing" in labels
    summary = niche_score(points, sigs, 0.2, 4)
    assert summary["grade"] == grade(summary["score"])


def test_momentum():
    assert momentum([50] * 39 + [100] * 13) == 1.0
    assert momentum([100] * 39 + [50] * 13) == -0.5
    assert momentum([0] * 40 + [100] * 12) is None   # low-volume spikes are ignored
    assert momentum([10] * 5) is None


class FakeHttp:
    def get(self, url, params=None, **kw):
        return {"hits": [{"objectID": "1", "title": "Ask HN: invoicing for freelancers is painful",
                          "story_text": "I wish there was a simpler tool", "points": 40, "num_comments": 12,
                          "created_at_i": int(NOW), "author": "pg"}]}


def test_hackernews_parsing():
    out = HackerNews(FakeHttp()).collect(ScanContext("freelance invoicing", ["freelance", "invoicing"]))
    assert out and out[0].url.endswith("id=1") and out[0].score == 40


def test_reports(tmp_path):
    sigs = corpus()
    pain.annotate(sigs)
    points = [p for p in cluster(sigs, niche_keywords("freelance invoicing")) if len(p.signals) >= 2]
    score_points(points, None, 4)
    for p in points:
        p.solutions = recommend(p)
    r = ScanResult(niche="freelance invoicing", keywords=["freelance", "invoicing"], generated_at="now",
                   summary=niche_score(points, sigs, None, 4), points=points, sources=[])
    assert "Demand scan" in to_markdown(r)
    assert "<html" in to_html(r)
    brief = build_brief(points[0], "freelance invoicing", 1)
    assert "Evidence" in brief and "Instructions for the coding agent" in brief
    folder = write_all(r, tmp_path)
    data = json.loads((folder / "report.json").read_text())
    assert data["pain_points"] and list((folder / "briefs").glob("01-*.md"))
