"""Pain-signal detection.

Each pattern belongs to a category. A signal's pain score (0..1) combines how many
categories fire and how strong they are. Categories are also used downstream to
decide what kind of solution fits (e.g. `workaround` -> automation, `how_to` -> content).
"""
from __future__ import annotations

import re

from .models import Signal
from .text import clean

# category -> (weight, [regex patterns])
LEXICON: dict[str, tuple[float, list[str]]] = {
    "willingness_to_pay": (1.0, [
        r"\b(i|we)('d| would| will)? (happily |gladly )?pay\b", r"shut up and take my money",
        r"\bworth paying\b", r"\bpay (good )?money\b", r"\btake my money\b",
        r"\b(would|will) subscribe\b", r"\bpaid (tool|app|version|plan)\b.{0,40}\b(if|that)\b",
        r"\bhire (someone|a freelancer|an agency)\b", r"\bbudget (for|of)\b",
    ]),
    "tool_seeking": (0.85, [
        r"\bis there (a|an|any) (app|tool|software|service|website|site|plugin|extension|way)\b",
        r"\b(looking|searching) for (a|an|some)? ?(app|tool|software|service|solution|platform)\b",
        r"\b(any|what) (app|tool|software|service)s? (do you|would you|to|for|that)\b",
        r"\brecommend(ation)?s? (for )?(a|an|any)? ?(app|tool|software|service)\b",
        r"\bdoes (anyone|anybody) know (of )?(a|an|any)\b", r"\bwhat do you (all |guys )?use (for|to)\b",
        r"\bhow do you (all |guys )?(manage|handle|track|deal with|keep track)\b",
    ]),
    "alternative": (0.8, [
        r"\balternatives? (to|for)\b", r"\breplacement for\b", r"\bswitch(ing|ed)? (away )?from\b",
        r"\b(cheaper|better|simpler|free) (alternative|option|version)\b", r"\bmoving away from\b",
        r"\bvs\.? ", r"\bcancel(led|ling)? (my )?subscription\b",
    ]),
    "feature_gap": (0.75, [
        r"\bi wish (there (was|were)|it|they|i could|someone)\b", r"\bwish list\b",
        r"\b(doesn't|does not|don't|won't|can't|cannot) (support|let|allow|handle|integrate|sync|export)\b",
        r"\bno (way|option) to\b", r"\bmissing (feature|option|integration)\b",
        r"\bwhy (can't|doesn't|isn't|won't) (it|they|there)\b", r"\bfeature request\b",
        r"\bsomeone (should|needs to) (build|make|create)\b", r"\bif only\b",
        r"\bwould (love|kill for|be nice)\b",
    ]),
    "frustration": (0.7, [
        r"\b(so |really |incredibly |super )?(frustrat\w*|annoy\w*|infuriat\w*|maddening)\b",
        r"\bi hate\b", r"\bhate (it|that|how|when)\b", r"\bsucks?\b", r"\b(terrible|awful|horrible|garbage|useless|worst)\b",
        r"\bdriving me (crazy|nuts|insane)\b", r"\bfed up\b", r"\bsick (and tired )?of\b", r"\bnightmare\b",
        r"\bpain in the (ass|butt|neck)\b", r"\b(broken|buggy|unusable|clunky|confusing)\b",
        r"\bgave up\b", r"\bgiving up\b", r"\bstruggl\w+\b", r"\bpain ?point\b",
    ]),
    "workaround": (0.7, [
        r"\bspreadsheets?\b", r"\bexcel\b", r"\bgoogle sheets?\b", r"\bmanually\b", r"\bby hand\b",
        r"\bcopy(ing)?[- ](and[- ])?past(e|ing)\b", r"\bwork ?around\b", r"\b(hacky|duct tape|jury[- ]rig)\b",
        r"\bwrote (a|my own) script\b", r"\bsticky notes\b", r"\bpen and paper\b", r"\bnotebook\b",
    ]),
    "time_waste": (0.6, [
        r"\b(hours|days|weeks) (a|per|every) (day|week|month)\b", r"\b(waste|wasting|wasted) (so much |hours of )?(time|hours)\b",
        r"\btedious\b", r"\btime[- ]consuming\b", r"\brepetitive\b", r"\bevery (single )?(day|week|month|time)\b",
        r"\btakes (forever|ages|hours)\b",
    ]),
    "price": (0.6, [
        r"\btoo expensive\b", r"\boverpriced\b", r"\b(price|pricing) (hike|increase|went up)\b",
        r"\bcan't afford\b", r"\b(expensive|pricey|costly)\b", r"\bper (month|seat|user)\b.{0,30}\b(ridiculous|insane|crazy)\b",
        r"\bsubscription fatigue\b",
    ]),
    "how_to": (0.45, [
        r"^how (do|can|to|should)\b", r"\bhow (do|can) i\b", r"\bcan't figure (out)?\b", r"\bany (tips|advice)\b",
        r"\bbeginner\b", r"\bwhere (do|can) i (start|find|learn)\b", r"\bconfused (about|by)\b",
        r"^why (is|does|do|are|can't)\b", r"\bhelp( me)? (with|understand)\b", r"\bstep by step\b",
    ]),
}

_COMPILED = {cat: (w, [re.compile(p, re.I) for p in pats]) for cat, (w, pats) in LEXICON.items()}

# Search queries are terse, so a few modifiers carry the pain meaning on their own.
QUERY_HINTS = {
    "alternative": ("alternative", " vs ", "replacement", "cheaper"),
    "how_to": ("how to", "how do", "why is", "why does", "tutorial", "guide"),
    "feature_gap": ("without", "not working", "doesn't", "can't", "problem", "issue", "error"),
    "tool_seeking": (" app", " tool", "software", "tracker", "generator", "template", "planner"),
    "price": ("free", "cheap", "price", "cost"),
    "workaround": ("spreadsheet", "excel", "template"),
}


# Product aspects: *what* the pain is about. Used to group complaints that share no exact words
# ("loading forever" and "crashes on save" are both reliability).
ASPECTS: dict[str, str] = {
    "pricing": r"\b(pric\w*|expensive|overpriced|subscription|fees?|cost\w*|paywall|upgrade|free (plan|tier|version)|premium|afford\w*|refund)\b",
    "reliability": r"\b(crash\w*|bugs?|buggy|slow|loading|freez\w*|broken|glitch\w*|lost (my )?data|won'?t (open|load|work)|doesn'?t work|not working|error\w*|laggy)\b",
    "usability": r"\b(confus\w*|clunky|intuitive|complicated|hard to use|user interface|ui|ux|too many (steps|clicks)|cluttered|steep learning)\b",
    "integrations": r"\b(integrat\w*|sync\w*|export\w*|import\w*|api|connect\w*|zapier|csv|quickbooks|stripe|xero|shopify|google (sheets|calendar|drive))\b",
    "mobile": r"\b(mobile|phone|android|iphone|ios|tablet|on the go|offline)\b",
    "automation": r"\b(manual\w*|automat\w*|repetitive|reminders?|recurring|by hand|copy.?past\w*|spreadsheets?|excel)\b",
    "payments": r"\b(get(ting)? paid|late payments?|overdue|chas(e|ing)|unpaid|payment\w*|invoice\w*|billing)\b",
    "support": r"\b(customer (service|support)|support team|no response|never (replied|responded)|contact(ed)? support)\b",
    "learning": r"\b(how (do|to|can)|beginner\w*|tutorial\w*|learn\w*|guide|where to start|course|explain\w*)\b",
    "privacy": r"\b(privacy|data (sharing|collection)|security|secure|gdpr|sells? (my )?data)\b",
    "compliance": r"\b(tax\w*|vat|gst|legal\w*|complian\w*|regulat\w*|audit\w*|licen[cs]\w*|permit\w*)\b",
    "collaboration": r"\b(team\w*|shar(e|ing)|collaborat\w*|multi.?user|client portal|clients?|family|partner)\b",
    "discovery": r"\b(find(ing)?|search(ing)?|compar\w*|recommend\w*|which (one|app|tool)|best (app|tool|way))\b",
}
_ASPECTS = {k: re.compile(v, re.I) for k, v in ASPECTS.items()}


def aspects(text: str) -> list[str]:
    return [k for k, rx in _ASPECTS.items() if rx.search(text)]


def detect(text: str, kind: str = "post") -> tuple[float, list[str]]:
    text = clean(text)
    tags: list[str] = []
    weights: list[float] = []
    for cat, (w, pats) in _COMPILED.items():
        if any(p.search(text) for p in pats):
            tags.append(cat)
            weights.append(w)
    if kind == "query":
        low = f" {text.lower()} "
        for cat, hints in QUERY_HINTS.items():
            if cat not in tags and any(h in low for h in hints):
                tags.append(cat)
                weights.append(LEXICON[cat][0] * 0.6)
    if not weights:
        return 0.0, []
    weights.sort(reverse=True)
    # strongest category + diminishing contribution from the rest
    score = weights[0] * 0.7 + sum(weights[1:4]) * 0.15
    if text.count("?") and kind in ("post", "comment"):
        score += 0.05
    return min(1.0, round(score, 3)), tags


def annotate(signals: list[Signal]) -> None:
    for s in signals:
        s.pain, s.pain_tags = detect(s.body, s.kind)
        s.meta["aspects"] = aspects(clean(s.body))
        # Low-star reviews and unanswered questions are pain even without the phrasing.
        rating = s.meta.get("rating")
        if rating is not None and rating <= 2:
            s.pain = max(s.pain, 0.65)
            if "frustration" not in s.pain_tags:
                s.pain_tags.append("frustration")
        if s.meta.get("unanswered") and s.views > 500:
            s.pain = max(s.pain, 0.5)
            if "feature_gap" not in s.pain_tags:
                s.pain_tags.append("feature_gap")
