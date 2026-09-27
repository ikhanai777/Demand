"""Tiny text utilities (no NLP dependencies)."""
from __future__ import annotations

import html
import re

STOPWORDS = set("""
a about above after again against all almost also am an and any are aren't as at be because been
before being below between both but by can can't cannot could couldn't did didn't do does doesn't
doing don't down during each else even ever every few for from further get gets getting got had
hadn't has hasn't have haven't having he her here hers herself him himself his how i i'd i'll i'm
i've if in into is isn't it it's its itself just let's like lot lots me more most much must my
myself no nor not now of off on once one only or other ought our ours ourselves out over own
really same she should shouldn't so some something such than that that's the their theirs them
themselves then there there's these they they're this those through to too under until up upon
us use used using very via was wasn't way we we're were weren't what what's when where which while
who whom why will with won't would wouldn't yes yet you you'd you'll you're you've your yours
yourself yourselves im ive dont doesnt cant didnt thats gonna want wants anyone someone thing
things people know think make made going go actually still anything everything since well new
way ways need needs good best better https http www com amp gt lt nbsp quot etc year years day days
time times back see say said looking look find work works working first last many may might
""".split())

_TAG = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://\S+")
_WORD = re.compile(r"[a-z][a-z0-9'+#-]{1,}")


def clean(text: str) -> str:
    text = html.unescape(_TAG.sub(" ", text or ""))
    text = _URL.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def stem(word: str) -> str:
    """Very light suffix stripping so 'invoices'/'invoicing'/'invoice' collide."""
    for suf in ("ations", "ation", "ings", "ing", "ies", "ers", "er", "es", "ed", "s"):
        min_len = 3 if suf == "s" else len(suf) + 3   # "dogs" -> "dog", but keep "gas", "less"
        if len(word) > min_len and word.endswith(suf) and not (suf == "s" and word.endswith("ss")):
            word = word[: -len(suf)] + ("y" if suf == "ies" else "")
            break
    if len(word) > 4 and word.endswith("e"):
        word = word[:-1]
    return word


def tokens(text: str, keep_stop: bool = False) -> list[str]:
    words = _WORD.findall(clean(text).lower())
    return [w.strip("'-") for w in words if keep_stop or (w not in STOPWORDS and len(w) > 2)]


def terms(text: str) -> list[str]:
    """Stemmed unigrams + bigrams used for clustering."""
    toks = [stem(t) for t in tokens(text)]
    return toks + [f"{a} {b}" for a, b in zip(toks, toks[1:]) if a != b]


def niche_keywords(niche: str) -> list[str]:
    toks = tokens(niche)
    return toks or [niche.lower().strip()]


def mentions_niche(text: str, keywords: list[str], min_hits: int | None = None) -> bool:
    """True if the text is about the niche.

    Matching is fuzzy (shared stem prefix: "prep" ~ "preparing", "dog" ~ "dogs"). Two- and
    three-word niches need every word ("dog training" must not match ML model training);
    longer niches need all but one.
    """
    if not keywords:
        return True
    body = {stem(t) for t in tokens(text)}
    hits = 0
    for k in keywords:
        ks = stem(k)[:5]
        if ks in body or (len(ks) >= 4 and any(b.startswith(ks) for b in body)):
            hits += 1
    need = min_hits if min_hits is not None else (len(keywords) if len(keywords) <= 3 else len(keywords) - 1)
    return hits >= min(need, len(keywords))


def snippet(text: str, n: int = 280) -> str:
    text = clean(text)
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def slugify(text: str, n: int = 50) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n] or "niche"
