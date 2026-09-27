"""Group signals into pain points with TF-IDF + greedy centroid clustering (pure Python)."""
from __future__ import annotations

import math
from collections import Counter

from .models import PainPoint, Signal
from .text import stem, terms, tokens

GENERIC = {stem(w) for w in """
app apps tool tools software thing problem issue help question anyone someone way use user users
feel want really post thread reddit comment edit update thank thanks lol yeah great nice love
awesome amazing bad basic dealing matter enough today star stars video videos don doesn won isn able
easily easy simple pretty kind sort literally honestly probably maybe definitely stuff guy guys
""".split()}


def _vectorize(docs: list[list[str]], exclude: set[str]) -> list[dict[str, float]]:
    df: Counter[str] = Counter()
    for d in docs:
        df.update(set(d))
    n = len(docs)
    vecs = []
    for d in docs:
        tf = Counter(t for t in d if t not in exclude and not set(t.split()) & exclude)
        # df<2 terms can't link two documents and only dilute similarity; near-universal terms are noise
        v = {t: (1 + math.log(c)) * math.log((1 + n) / (1 + df[t]))
             for t, c in tf.items() if df[t] >= 2 and (df[t] / n < 0.5 or n < 10)}
        norm = math.sqrt(sum(w * w for w in v.values())) or 1.0
        vecs.append({t: w / norm for t, w in v.items()})
    return vecs


def _cos(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b.get(t, 0.0) for t, w in a.items())


def _label(members: list[dict[str, float]], signals: list[Signal],
           common_aspects: set[str]) -> tuple[str, list[str]]:
    # Score terms by how many members share them (not just weight), so one long
    # post can't hijack the label.
    agg: Counter[str] = Counter()
    shared: Counter[str] = Counter()
    for v in members:
        for t, w in v.items():
            if not t.startswith("@"):
                agg[t] += w
                shared[t] += 1
    need = 2 if len(members) >= 3 else 1
    ranked = [t for t, _ in sorted(agg.items(), key=lambda x: -(x[1] * shared[x[0]])) if shared[t] >= need][:40]
    if not ranked:
        ranked = [t for t, _ in agg.most_common(40)]
    # prefer bigrams in the label, they read like a problem statement
    bigrams = [t for t in ranked if " " in t]
    unigrams = [t for t in ranked if " " not in t]
    keywords = (bigrams[:2] + [u for u in unigrams if not any(u in b.split() for b in bigrams[:2])])[:6]
    # map stems back to a real surface word for readability
    surface: dict[str, Counter[str]] = {}
    for s in signals:
        for tok in tokens(s.body):
            surface.setdefault(stem(tok), Counter())[tok] += 1

    def pretty(term: str) -> str:
        return " ".join(surface.get(p, Counter({p: 1})).most_common(1)[0][0] for p in term.split())

    kws = [pretty(k) for k in keywords]
    label = " / ".join(kws[:3]) if kws else "misc"
    asp = Counter(a for s in signals for a in s.meta.get("aspects", []) if a not in common_aspects)
    if asp:
        top, cnt = asp.most_common(1)[0]
        if cnt >= max(2, len(signals) * 0.5):
            label = f"{top.capitalize()}: {label}"
    return label, kws


def cluster(signals: list[Signal], niche_keywords: list[str], threshold: float = 0.2,
            max_clusters: int = 60) -> list[PainPoint]:
    """Cluster pain-bearing signals. Signals with zero pain are only used as supporting volume."""
    exclude = {stem(k) for k in niche_keywords} | GENERIC
    # title counts double; aspect tags act as heavy pseudo-terms so "loading forever" and
    # "crashes on save" can land together under reliability
    docs = [terms(s.title) + terms(s.body[:1500]) + [f"@{a}" for a in s.meta.get("aspects", [])] * 2
            for s in signals]
    vecs = _vectorize(docs, exclude)

    order = sorted(range(len(signals)),
                   key=lambda i: (signals[i].pain, math.log1p(max(0.0, signals[i].score) + signals[i].comments)),
                   reverse=True)
    centroids: list[dict[str, float]] = []
    members: list[list[int]] = []
    for i in order:
        v = vecs[i]
        if not v:
            continue
        best, best_sim = -1, 0.0
        for c, cen in enumerate(centroids):
            sim = _cos(v, cen)
            if sim > best_sim:
                best, best_sim = c, sim
        if best >= 0 and best_sim >= threshold:
            members[best].append(i)
            cen = centroids[best]
            k = len(members[best])
            for t, w in v.items():
                cen[t] = cen.get(t, 0.0) * (k - 1) / k + w / k
            for t in list(cen):
                if t not in v:
                    cen[t] *= (k - 1) / k
            # keep centroids small
            if len(cen) > 80:
                centroids[best] = dict(sorted(cen.items(), key=lambda x: -x[1])[:80])
        elif signals[i].pain > 0 and len(centroids) < max_clusters * 3:
            centroids.append(dict(v))
            members.append([i])

    # aspects present in most of the corpus describe the niche itself, not a specific pain
    asp_df = Counter(a for s in signals for a in s.meta.get("aspects", []))
    common = {a for a, c in asp_df.items() if c > len(signals) * 0.3}
    points: list[PainPoint] = []
    for idx, mem in enumerate(members):
        sigs = [signals[i] for i in mem]
        if not any(s.pain > 0 for s in sigs):
            continue
        label, kws = _label([vecs[i] for i in mem], sigs, common)
        points.append(PainPoint(id=idx, label=label, keywords=kws, signals=sigs))
    return points
