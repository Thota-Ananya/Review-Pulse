"""
Insights engine: turns numbers into plain-English findings with a recommended action.

Method: compare the most recent 4 weeks with the 4 weeks before them and flag the
segments (topic x city, topic x platform) whose negative mentions grew the most.
An optional LLM (any OpenAI-compatible API, e.g. Gemini free tier) can rewrite the
findings as an executive summary; without an API key the rule-based text is used.
"""
import os
from datetime import timedelta

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import analytics

WINDOW_WEEKS = 4
MIN_RECENT = 8  # ignore tiny segments so we don't alarm on noise

ACTIONS = {
    "Delivery": "Check rider supply and peak-hour capacity in {seg}; consider temporary rider incentives.",
    "App Experience": "Escalate to engineering: investigate the latest {seg} release and consider a hotfix/rollback.",
    "Pricing": "Review the recent fee changes; A/B test a lower platform fee or targeted coupons.",
    "Food Quality": "Audit restaurant partners with the most complaints in {seg}.",
    "Packaging": "Mandate spill-proof packaging for gravy and drinks with partner restaurants.",
    "Customer Support": "Set a first-response SLA for support chats and review ticket-closure rules.",
    "Refunds": "Automate refunds for missing items and track time-to-refund.",
    "Other": "Read a sample of these reviews to find a new theme.",
}


def _pct(a, b):
    return (a - b) / b if b else None


def _windows(db: Session):
    last = analytics.as_date(db.execute(text("SELECT MAX(week_start) FROM reviews")).scalar())
    if last is None:
        return None
    recent_start = last - timedelta(weeks=WINDOW_WEEKS - 1)
    prior_start = recent_start - timedelta(weeks=WINDOW_WEEKS)
    return recent_start, prior_start


def _segment_spikes(db: Session, column: str, recent_start, prior_start) -> list[dict]:
    rows = db.execute(text(f"""
        SELECT t.topic, r.{column} AS segment,
               SUM(CASE WHEN r.week_start >= :recent THEN 1 ELSE 0 END) AS recent,
               SUM(CASE WHEN r.week_start <  :recent THEN 1 ELSE 0 END) AS prior
        FROM review_topics t JOIN reviews r ON r.id = t.review_id
        WHERE r.sentiment_label = 'negative' AND r.week_start >= :prior
        GROUP BY t.topic, r.{column}"""),
        {"recent": recent_start.isoformat(), "prior": prior_start.isoformat()})
    out = []
    for topic, seg, recent, prior in rows:
        if recent >= MIN_RECENT and recent > prior:
            out.append({"topic": topic, "segment": seg, "recent": int(recent), "prior": int(prior),
                        "increase": int(recent - prior), "growth": _pct(recent, prior)})
    return sorted(out, key=lambda x: x["increase"], reverse=True)


def _long_term_shift(db: Session, weeks: int = 8, min_gain: float = 0.05) -> list[dict]:
    """Share of negative reviews mentioning each topic: first N weeks vs last N weeks."""
    bounds = db.execute(text("SELECT MIN(week_start), MAX(week_start) FROM reviews")).one()
    first, last = analytics.as_date(bounds[0]), analytics.as_date(bounds[1])
    if not first or (last - first).days < weeks * 14:
        return []
    early_end = (first + timedelta(weeks=weeks)).isoformat()
    late_start = (last - timedelta(weeks=weeks - 1)).isoformat()
    neg = db.execute(text("""
        SELECT SUM(CASE WHEN week_start <  :early_end THEN 1 ELSE 0 END),
               SUM(CASE WHEN week_start >= :late_start THEN 1 ELSE 0 END)
        FROM reviews WHERE sentiment_label = 'negative'"""),
        {"early_end": early_end, "late_start": late_start}).one()
    if not neg[0] or not neg[1]:
        return []
    rows = db.execute(text("""
        SELECT t.topic,
               SUM(CASE WHEN r.week_start <  :early_end THEN 1 ELSE 0 END) AS early,
               SUM(CASE WHEN r.week_start >= :late_start THEN 1 ELSE 0 END) AS late
        FROM review_topics t JOIN reviews r ON r.id = t.review_id
        WHERE r.sentiment_label = 'negative' GROUP BY t.topic"""),
        {"early_end": early_end, "late_start": late_start})
    out = [{"topic": tp, "early": e / neg[0], "late": lt / neg[1]} for tp, e, lt in rows if tp != "Other"]
    out = [o for o in out if o["late"] - o["early"] >= min_gain]
    return sorted(out, key=lambda o: o["late"] - o["early"], reverse=True)[:2]


def generate_insights(db: Session) -> list[dict]:
    win = _windows(db)
    if not win:
        return []
    recent_start, prior_start = win
    insights: list[dict] = []

    # 1. Emerging problems: biggest spikes across city AND platform segments, one per topic
    #    (so a single root cause, e.g. an iOS bug, isn't reported again for every city).
    spikes = []
    for column, label in (("city", "in"), ("platform", "on")):
        spikes += [{**s, "column": column, "label": label}
                   for s in _segment_spikes(db, column, recent_start, prior_start)]
    spikes.sort(key=lambda s: s["increase"], reverse=True)
    seen_topics: set[str] = set()
    for s in spikes:
        if s["topic"] == "Other" or s["topic"] in seen_topics or s["increase"] < 8:
            continue
        seen_topics.add(s["topic"])
        growth = f"+{s['growth']:.0%}" if s["growth"] is not None else "new"
        insights.append({
            "severity": "high" if (s["growth"] or 9) >= 1 else "medium",
            "title": f"{s['topic']} complaints spiking {s['label']} {s['segment']}",
            "detail": (f"Negative {s['topic'].lower()} mentions {s['label']} {s['segment']} went from "
                       f"{s['prior']} to {s['recent']} ({growth}) in the last {WINDOW_WEEKS} weeks "
                       f"vs the {WINDOW_WEEKS} weeks before."),
            "action": ACTIONS.get(s["topic"], ACTIONS["Other"]).format(seg=s["segment"]),
            "metric": {"topic": s["topic"], s["column"]: s["segment"], "prior": s["prior"], "recent": s["recent"]},
        })
        if len(seen_topics) == 3:
            break

    # 2. Slow-building problems: topics whose share of negative reviews grew over the whole period
    for t in _long_term_shift(db):
        if t["topic"] in seen_topics:
            continue
        insights.append({
            "severity": "medium",
            "title": f"{t['topic']} complaints building up steadily",
            "detail": (f"{t['topic']} now appears in {t['late']:.0%} of negative reviews "
                       f"(last 8 weeks) vs {t['early']:.0%} in the first 8 weeks."),
            "action": ACTIONS.get(t["topic"], ACTIONS["Other"]).format(seg="affected cities"),
            "metric": {"topic": t["topic"], "early_share": t["early"], "late_share": t["late"]},
        })

    # 3. Top pain point overall
    topics = analytics.topic_breakdown(db)
    total_neg = db.execute(text("SELECT COUNT(*) FROM reviews WHERE sentiment_label='negative'")).scalar() or 0
    if topics and total_neg:
        top = topics[0]
        insights.append({
            "severity": "medium",
            "title": f"{top['topic']} is the #1 pain point overall",
            "detail": (f"{top['negative']} negative reviews mention {top['topic'].lower()} — "
                       f"{top['negative'] / total_neg:.0%} of all negative reviews."),
            "action": ACTIONS.get(top["topic"], ACTIONS["Other"]).format(seg="the worst-hit cities"),
            "metric": {"topic": top["topic"], "negative": top["negative"]},
        })

    # 4. Overall rating movement
    r = db.execute(text("""
        SELECT AVG(CASE WHEN week_start >= :recent THEN rating END),
               AVG(CASE WHEN week_start <  :recent AND week_start >= :prior THEN rating END)
        FROM reviews"""), {"recent": recent_start.isoformat(), "prior": prior_start.isoformat()}).one()
    if r[0] is not None and r[1] is not None:
        diff = float(r[0]) - float(r[1])
        if abs(diff) >= 0.05:
            insights.append({
                "severity": "high" if diff <= -0.2 else ("medium" if diff < 0 else "info"),
                "title": f"Average rating {'fell' if diff < 0 else 'rose'} to {float(r[0]):.2f}",
                "detail": f"Last {WINDOW_WEEKS} weeks: {float(r[0]):.2f} stars vs {float(r[1]):.2f} before ({diff:+.2f}).",
                "action": "Use the problems above to explain the change in the next business review." if diff < 0
                          else "Identify what improved and keep doing it.",
                "metric": {"recent": round(float(r[0]), 2), "prior": round(float(r[1]), 2)},
            })

    # 5. Best and worst cities (only cities with enough data)
    cities = [c for c in analytics.segment_breakdown(db, "city") if c["reviews"] >= 30]
    if len(cities) >= 2:
        best = max(cities, key=lambda c: c["csat"])
        worst = min(cities, key=lambda c: c["csat"])
        insights.append({
            "severity": "info",
            "title": f"{best['segment']} leads on satisfaction; {worst['segment']} trails",
            "detail": (f"CSAT (share of 4–5 star reviews) is {best['csat']:.0%} in {best['segment']} "
                       f"vs {worst['csat']:.0%} in {worst['segment']}."),
            "action": f"Study what works in {best['segment']} and apply it in {worst['segment']}.",
            "metric": {"best": best["segment"], "worst": worst["segment"]},
        })

    # 6. Hidden dissatisfaction
    k = analytics.kpis(db)
    if k["mismatches"]:
        insights.append({
            "severity": "info",
            "title": f"{k['mismatches']} reviews have stars that contradict their text",
            "detail": ("Some customers leave 4–5 stars but write complaints (or the reverse). "
                       "Tracking star ratings alone would miss this feedback."),
            "action": "Report text sentiment alongside star ratings in weekly dashboards.",
            "metric": {"mismatches": k["mismatches"]},
        })
    return insights


def llm_summary(insights: list[dict]) -> dict:
    """Executive summary via an OpenAI-compatible chat API, falling back to rule-based text."""
    top = [i for i in insights if i["severity"] in ("high", "medium")][:3]
    if top:
        rule_text = (f"{len(top)} issues need attention. " + " ".join(f"{i['title']}." for i in top)
                     + f" Most urgent action: {top[0]['action']}")
    else:
        rule_text = " ".join(f"{i['title']}." for i in insights[:3])
    key = os.getenv("LLM_API_KEY")
    if not key or not insights:
        return {"source": "rules", "summary": rule_text}

    base = os.getenv("LLM_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
    model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    facts = "\n".join(f"- {i['title']}: {i['detail']} Suggested action: {i['action']}" for i in insights)
    prompt = ("You are a business analyst at a food-delivery company. Using ONLY the facts below, "
              "write a 4-sentence executive summary for the operations head: the biggest problem, "
              "its likely business impact, and the top 2 actions. Do not invent numbers.\n\n" + facts)
    try:
        resp = httpx.post(f"{base}/chat/completions", timeout=20,
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "messages": [{"role": "user", "content": prompt}],
                                "temperature": 0.2})
        resp.raise_for_status()
        return {"source": f"llm:{model}", "summary": resp.json()["choices"][0]["message"]["content"].strip()}
    except Exception as exc:  # noqa: BLE001 - never break the dashboard because the LLM failed
        return {"source": "rules", "summary": rule_text, "llm_error": str(exc)[:200]}
