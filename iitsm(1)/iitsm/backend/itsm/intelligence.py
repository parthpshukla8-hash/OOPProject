"""Intelligent features: duplicate detection, category suggestion, resolution suggestion, correlation."""
import re
from collections import defaultdict

from .models import DONE_STATUSES, Category, Incident

STOP = {"the", "a", "an", "is", "are", "to", "of", "and", "in", "on", "for", "my", "we", "i", "it", "this", "that",
        "with", "make", "not", "be", "cannot", "can", "unable", "since", "again", "please", "has", "have", "was"}
SYNONYMS = {w: "fail" for w in ("unavailable", "down", "failing", "failed", "fails", "failure", "error", "errors",
                                 "crash", "crashing", "crashed", "broken", "outage", "timeout", "timing")}
SYNONYMS.update({w: "payment" for w in ("payments", "pay", "paying", "transaction", "transactions", "checkout")})
SYNONYMS.update({w: "login" for w in ("signin", "logon", "password", "authentication", "sso")})
SYNONYMS.update({w: "slow" for w in ("slowness", "lag", "laggy", "latency", "sluggish")})


def tokens(text):
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {SYNONYMS.get(w, w) for w in words if w not in STOP and len(w) > 1}


def similarity(a, b):
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def find_similar(title, description, service_id=None, exclude_id=None, threshold=0.3, open_only=True):
    """Duplicate detection: Jaccard similarity on normalised tokens, +0.15 if same service."""
    qs = Incident.objects.select_related("service")
    if open_only:
        qs = qs.exclude(status__in=DONE_STATUSES)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    text = f"{title} {description}"
    hits = []
    for inc in qs[:500]:
        s = similarity(text, f"{inc.title} {inc.description}")
        if s and service_id and inc.service_id == service_id:
            s = min(s + 0.15, 1.0)
        if s >= threshold:
            hits.append((inc, round(s, 2)))
    return sorted(hits, key=lambda h: -h[1])[:5]


def suggest_category(text):
    """Keyword-based auto-categorisation; returns (Category|None, matched keywords)."""
    toks, best, best_hits = tokens(text), None, []
    raw = (text or "").lower()
    for cat in Category.objects.all():
        kws = [k.strip().lower() for k in cat.keywords.split(",") if k.strip()]
        hits = [k for k in kws if (k in raw if " " in k else SYNONYMS.get(k, k) in toks)]
        if len(hits) > len(best_hits):
            best, best_hits = cat, hits
    return best, best_hits


def suggest_resolutions(incident, limit=3):
    """Re-use resolutions of similar, already-resolved historical incidents."""
    out = []
    text = f"{incident.title} {incident.description}"
    for inc in Incident.objects.filter(status__in=DONE_STATUSES).exclude(pk=incident.pk).exclude(resolution=""):
        s = similarity(text, f"{inc.title} {inc.description}")
        if inc.service_id == incident.service_id:
            s += 0.15
        if s >= 0.25:
            out.append({"number": inc.number, "title": inc.title, "resolution": inc.resolution, "score": round(min(s, 1), 2)})
    return sorted(out, key=lambda r: -r["score"])[:limit]


def correlate(min_group=3):
    """Incident correlation: >=3 open incidents on one service hint at a common infrastructure cause."""
    groups = defaultdict(list)
    for inc in Incident.objects.exclude(status__in=DONE_STATUSES).select_related("service"):
        groups[inc.service.name].append(inc.number)
    return [{"service": s, "count": len(n), "incidents": n} for s, n in groups.items() if len(n) >= min_group]
