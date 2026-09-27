"""Write scan results as JSON (for agents), Markdown (for humans), HTML (dashboard) and build briefs."""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from .scanner import ScanResult
from .scoring import WEIGHTS, grade
from .solutions import build_brief
from .text import slugify, snippet


def write_all(result: ScanResult, out_dir: str | Path = "reports", top: int = 25, briefs: int = 10) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    folder = Path(out_dir) / f"{slugify(result.niche)}-{stamp}"
    (folder / "briefs").mkdir(parents=True, exist_ok=True)
    data = result.to_dict(top=top)
    (folder / "report.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (folder / "report.md").write_text(to_markdown(result, top), encoding="utf-8")
    (folder / "report.html").write_text(to_html(result, top), encoding="utf-8")
    for rank, p in enumerate(result.points[:briefs], 1):
        name = p.llm.get("name") or p.label
        brief = folder / "briefs" / f"{rank:02d}-{slugify(name, 40)}.md"
        brief.write_text(build_brief(p, result.niche, rank), encoding="utf-8")
    return folder


# ---------------------------------------------------------------------------- markdown
def to_markdown(r: ScanResult, top: int = 25) -> str:
    s = r.summary
    lines = [
        f"# Demand scan: {r.niche}",
        "",
        f"**Niche demand score: {s['score']}/100 ({s['grade']})** · generated {r.generated_at}",
        "",
        f"- Signals collected: {s['signals_total']} ({s['signals_with_pain']} contain pain language)",
        f"- Willingness-to-pay signals: {s['wtp_signals']}",
        f"- Pain points found: {s['pain_points']}",
        f"- Google Trends momentum: {_fmt_momentum(r.trend.get('momentum'))}",
        "",
    ]
    if r.llm.get("niche_summary"):
        lines += ["## Summary", "", r.llm["niche_summary"], ""]
    lines += ["## Top pain points", "", "| # | Pain point | Score | Signals | Sources | Best-fit solution |",
              "|---|---|---|---|---|---|"]
    for i, p in enumerate(r.points[:top], 1):
        name = (p.llm.get("name") or p.label).replace("|", "/")
        best = p.solutions[0]["type"] if p.solutions else "-"
        lines.append(f"| {i} | {name} | **{p.score:.0f}** {grade(p.score)} | {len(p.signals)} | "
                     f"{', '.join(p.sources)} | {best} |")
    lines.append("")
    for i, p in enumerate(r.points[: min(top, 12)], 1):
        name = p.llm.get("name") or p.label
        lines += [f"### {i}. {name} — {p.score:.0f}/100", ""]
        if p.llm.get("problem_statement"):
            lines += [p.llm["problem_statement"], "", f"*Who:* {p.llm.get('who', '')}", ""]
        c = p.components
        lines.append("Breakdown: " + " · ".join(f"{k} {c.get(k, 0):.2f}" for k in WEIGHTS))
        lines.append("")
        lines.append("Pain types: " + (", ".join(f"{k} ({v})" for k, v in p.tags.items()) or "-"))
        lines += ["", "Evidence:"]
        for q in p.top_quotes(5):
            lines.append(f"- *{q.source}* — \"{snippet(q.body, 220)}\" ({int(q.score)} pts) [link]({q.url})")
        sols = p.llm.get("solutions") or []
        if sols:
            lines += ["", "Solution ideas:"]
            for x in sols:
                lines.append(f"- **{x.get('name')}** ({x.get('type')}, {x.get('build_effort', '')}): "
                             f"{x.get('one_liner')} — *{x.get('monetization')}*")
        else:
            lines += ["", "Solution fit: " + ", ".join(f"{x['type']} ({x['fit']})" for x in p.solutions)]
        lines.append("")
    if r.queries:
        lines += ["## Search demand (autocomplete & Google Trends)", ""]
        qs = sorted(r.queries, key=lambda q: (q.pain, q.score), reverse=True)[:40]
        lines += [f"- {q.title}" + (f"  _({', '.join(q.pain_tags)})_" if q.pain_tags else "") for q in qs]
        lines.append("")
    lines += ["## Sources", "", "| Source | Status | Signals | Note |", "|---|---|---|---|"]
    for src in r.sources:
        st = "skipped" if src.skipped else ("ok" if src.ok else "failed")
        lines.append(f"| {src.name} | {st} | {len(src.signals)} | {src.error or src.extra.get('mode', '')} |")
    lines += ["", "Build briefs for the top pain points are in `briefs/` — hand one to Claude Code:",
              "", "```bash", "claude \"$(cat briefs/01-*.md)\"", "```", ""]
    return "\n".join(lines)


def _fmt_momentum(m) -> str:
    if m is None:
        return "n/a (low search volume)"
    arrow = "rising" if m > 0.05 else "falling" if m < -0.05 else "flat"
    return f"{m:+.0%} ({arrow})"


# ---------------------------------------------------------------------------- html
def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _spark(values: list[float]) -> str:
    if not values or len(values) < 2:
        return ""
    w, h = 320, 56
    mx = max(values) or 1
    step = w / (len(values) - 1)
    pts = " ".join(f"{i * step:.1f},{h - (v / mx) * (h - 6) - 3:.1f}" for i, v in enumerate(values))
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" '
            f'aria-label="Google Trends interest over 5 years"><polyline points="{pts}" /></svg>')


def to_html(r: ScanResult, top: int = 25) -> str:
    s = r.summary
    cards = []
    for i, p in enumerate(r.points[:top], 1):
        name = p.llm.get("name") or p.label
        bars = "".join(
            f'<div class="bar"><span>{_e(k)}</span><i><b style="width:{p.components.get(k, 0) * 100:.0f}%"></b></i></div>'
            for k in WEIGHTS)
        quotes = "".join(
            f'<li><span class="src">{_e(q.source)}</span> {_e(snippet(q.body, 260))} '
            f'<a href="{_e(q.url)}" target="_blank" rel="noopener">{int(q.score)} pts ↗</a></li>'
            for q in p.top_quotes(5))
        sols = p.llm.get("solutions") or []
        if sols:
            sol_html = "".join(
                f'<div class="sol"><b>{_e(x.get("name"))}</b> <em>{_e(x.get("type"))} · {_e(x.get("build_effort", ""))}</em>'
                f'<p>{_e(x.get("one_liner"))}</p><small>{_e(x.get("monetization"))}</small></div>' for x in sols)
        else:
            sol_html = "".join(f'<span class="chip">{_e(x["type"])} · fit {x["fit"]}</span>' for x in p.solutions)
        problem = f'<p class="problem">{_e(p.llm["problem_statement"])}</p>' if p.llm.get("problem_statement") else ""
        tags = "".join(f'<span class="tag">{_e(k)} {v}</span>' for k, v in list(p.tags.items())[:6])
        cards.append(f"""
<article class="card">
  <header><span class="rank">#{i}</span><h3>{_e(name)}</h3>
  <div class="score g-{grade(p.score).lower()}">{p.score:.0f}<small>{grade(p.score)}</small></div></header>
  {problem}
  <div class="meta">{len(p.signals)} signals · {_e(', '.join(p.sources))}</div>
  <div class="tags">{tags}</div>
  <div class="bars">{bars}</div>
  <details><summary>Evidence</summary><ul class="quotes">{quotes}</ul></details>
  <div class="sols">{sol_html}</div>
</article>""")

    queries = "".join(
        f'<a class="chip {"pain" if q.pain else ""}" href="{_e(q.url)}" target="_blank" rel="noopener">{_e(q.title)}</a>'
        for q in sorted(r.queries, key=lambda q: (q.pain, q.score), reverse=True)[:60])
    src_rows = "".join(
        f'<tr><td>{_e(x.name)}</td><td class="{"ok" if x.ok and not x.skipped else "bad"}">'
        f'{"skipped" if x.skipped else "ok" if x.ok else "failed"}</td><td>{len(x.signals)}</td>'
        f'<td>{_e(x.error or x.extra.get("mode", ""))}</td></tr>' for x in r.sources)
    summary = f'<p class="lede">{_e(r.llm["niche_summary"])}</p>' if r.llm.get("niche_summary") else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Demand Scan: {_e(r.niche)}</title>
<style>
:root{{--bg:#f7f7f5;--panel:#fff;--ink:#1c1c1a;--muted:#6b6b66;--line:#e4e4df;--accent:#2f6fde;
--hot:#d6452c;--strong:#e08a1e;--prom:#2f8f5b;--weak:#8a8a84;--track:#ececea}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#141413;--panel:#1d1d1b;--ink:#ecebe6;
--muted:#9c9b95;--line:#2e2e2b;--accent:#7aa7ff;--track:#2a2a27}}}}
:root[data-theme="dark"]{{--bg:#141413;--panel:#1d1d1b;--ink:#ecebe6;--muted:#9c9b95;--line:#2e2e2b;--accent:#7aa7ff;--track:#2a2a27}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:28px;margin:0 0 4px}}
.sub{{color:var(--muted);margin:0 0 20px}}.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}.kpi b{{display:block;font-size:24px}}
.kpi span{{color:var(--muted);font-size:13px}}.spark{{width:100%;height:56px}}.spark polyline{{fill:none;stroke:var(--accent);stroke-width:2}}
.lede{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;min-width:0}}
.card header{{display:flex;gap:10px;align-items:flex-start}}.card h3{{flex:1;margin:0;font-size:16px;overflow-wrap:anywhere}}
.rank{{color:var(--muted);font-weight:600}}.score{{font-size:22px;font-weight:700;text-align:right;line-height:1}}
.score small{{display:block;font-size:10px;letter-spacing:.08em;margin-top:3px}}.g-hot{{color:var(--hot)}}.g-strong{{color:var(--strong)}}
.g-promising{{color:var(--prom)}}.g-weak,.g-noise{{color:var(--weak)}}.problem{{margin:8px 0}}.meta{{color:var(--muted);font-size:13px;margin:6px 0}}
.bars{{display:grid;gap:3px;margin:10px 0}}.bar{{display:grid;grid-template-columns:90px 1fr;align-items:center;font-size:12px;color:var(--muted)}}
.bar i{{display:block;height:6px;background:var(--track);border-radius:3px}}.bar b{{display:block;height:6px;background:var(--accent);border-radius:3px}}
.tag,.chip{{display:inline-block;font-size:12px;border:1px solid var(--line);border-radius:999px;padding:2px 8px;margin:2px 4px 2px 0;color:var(--ink);text-decoration:none}}
.chip.pain{{border-color:var(--accent)}}.quotes{{padding-left:18px;font-size:13px}}.quotes li{{margin:6px 0;overflow-wrap:anywhere}}
.src{{font-weight:600;color:var(--muted)}}a{{color:var(--accent)}}summary{{cursor:pointer;color:var(--accent);font-size:13px}}
.sol{{border-top:1px solid var(--line);padding-top:8px;margin-top:8px}}.sol em{{color:var(--muted);font-size:12px}}.sol p{{margin:4px 0}}
.sol small{{color:var(--muted)}}table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--panel)}}
td,th{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}
.ok{{color:var(--prom)}}.bad{{color:var(--muted)}}h2{{margin:32px 0 12px;font-size:19px}}.tablewrap{{overflow-x:auto}}
</style></head><body><main>
<h1>Demand scan: {_e(r.niche)}</h1>
<p class="sub">Generated {_e(r.generated_at)} · keywords: {_e(', '.join(r.keywords))}</p>
<div class="kpis">
 <div class="kpi"><span>Niche demand</span><b class="g-{s['grade'].lower()}">{s['score']}</b><span>{s['grade']}</span></div>
 <div class="kpi"><span>Signals (with pain)</span><b>{s['signals_total']}</b><span>{s['signals_with_pain']} painful</span></div>
 <div class="kpi"><span>Willingness to pay</span><b>{s['wtp_signals']}</b><span>signals</span></div>
 <div class="kpi"><span>Trend momentum</span><b>{_e(_fmt_momentum(r.trend.get('momentum')).split(' ')[0])}</b>{_spark(r.trend.get('series') or [])}</div>
</div>
{summary}
<h2>Pain points, ranked by demand</h2>
<div class="grid">{''.join(cards) or '<p>No pain points found. Try a broader niche or --deep.</p>'}</div>
<h2>Search demand</h2><div>{queries or '<p class="sub">No autocomplete data.</p>'}</div>
<h2>Sources</h2><div class="tablewrap"><table><tr><th>Source</th><th>Status</th><th>Signals</th><th>Note</th></tr>{src_rows}</table></div>
</main></body></html>"""
