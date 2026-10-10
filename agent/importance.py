"""Rule-based ranking of 'important' emails (fast, free, predictable)."""

import re

KEYWORDS = {
    "interview": 6,
    "offer": 5,
    "shortlisted": 5,
    "selected": 4,
    "assessment": 4,
    "coding test": 4,
    "urgent": 4,
    "action required": 4,
    "deadline": 4,
    "due": 2,
    "invoice": 3,
    "payment": 3,
    "security alert": 3,
    "verify": 2,
    "meeting": 2,
    "schedule": 2,
    "application": 3,
    "recruiter": 3,
    "hiring": 3,
    "position": 2,
    "opportunity": 2,
    "re:": 2,
}

AUTOMATED_SENDER = re.compile(
    r"no-?reply|do-?not-?reply|newsletter|notifications?@|mailer|marketing", re.I
)


def score_email(email: dict) -> tuple[int, list[str]]:
    text = f"{email.get('subject', '')} {email.get('snippet', '')}".lower()
    score, reasons = 0, []

    for keyword, weight in KEYWORDS.items():
        if keyword in text:
            score += weight
            reasons.append(f"mentions '{keyword}'")

    if AUTOMATED_SENDER.search(email.get("from", "")):
        score -= 3
        reasons.append("automated sender")

    labels = set(email.get("labels", []))
    adjustments = {
        "IMPORTANT": (3, "marked important by Gmail"),
        "STARRED": (2, "starred"),
        "CATEGORY_PROMOTIONS": (-4, "promotion"),
        "CATEGORY_SOCIAL": (-2, "social"),
        "CATEGORY_UPDATES": (-1, "automated update"),
    }
    for label, (delta, reason) in adjustments.items():
        if label in labels:
            score += delta
            reasons.append(reason)

    return score, reasons


def rank_emails(emails: list[dict], top_n: int = 10, min_score: int = 1) -> list[dict]:
    ranked = []
    for email in emails:
        score, reasons = score_email(email)
        if score >= min_score:
            ranked.append({**email, "score": score, "reasons": reasons})
    ranked.sort(key=lambda e: e["score"], reverse=True)
    return ranked[:top_n]


def format_ranked(ranked: list[dict]) -> str:
    if not ranked:
        return "No important unread emails found."
    lines = []
    for i, e in enumerate(ranked, 1):
        lines.append(f"{i}. [{e['score']:+d}] {e['subject']}")
        lines.append(f"   From: {e['from']}")
        lines.append(f"   Why:  {', '.join(e['reasons'])}")
        lines.append(f"   id:   {e['id']}")
    return "\n".join(lines)
