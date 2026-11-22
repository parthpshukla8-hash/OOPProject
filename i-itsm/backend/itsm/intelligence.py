"""Intelligent features built on cosine similarity (see similarity.py).

* suggest_category / suggest_service   - which label does this text look like?
* find_similar_incidents               - duplicates and related incidents
* suggest_resolutions                  - what fixed similar problems before?
* correlate_open_incidents             - clusters of open incidents pointing to one cause
* TechnicianAffinity                   - how close is a technician's past work to this incident?
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from .models import Category, FINISHED_STATUSES, Incident, OPEN_STATUSES, Service, User
from .similarity import CentroidClassifier, SimilarityIndex, SparseVector, TfidfModel

DUPLICATE_THRESHOLD = 0.5
RELATED_THRESHOLD = 0.28
SAME_SERVICE_BOOST = 0.1
EXACT_REPEAT_THRESHOLD = 0.85
MIN_LABEL_CONFIDENCE = 0.12
CORPUS_LIMIT = 1500
HISTORY_LIMIT = 300


@dataclass(frozen=True)
class IncidentMatch:
    incident: Incident
    score: float
    text_score: float
    shared_terms: tuple[str, ...]

    @property
    def level(self) -> str:
        return "likely_duplicate" if self.score >= DUPLICATE_THRESHOLD else "related"


def _history_texts(**filters) -> list[str]:
    return [i.search_text for i in
            Incident.objects.filter(**filters).select_related("service").order_by("-id")[:HISTORY_LIMIT]]


def _label_examples(label_text: str, history: list[str]) -> list[str]:
    return [label_text, label_text] + history


def suggest_category(text: str, limit: int = 3) -> list[dict]:
    examples = {}
    for category in Category.objects.all():
        keyword_doc = f"{category.name} {category.description} {category.keywords}"
        history = _history_texts(category=category)
        examples[category.pk] = _label_examples(keyword_doc, history)
    names = {c.pk: c.name for c in Category.objects.all()}
    ranked = CentroidClassifier(examples).rank(text, limit) if examples else []
    return [{"id": pk, "name": names[pk], "score": score, "matched_terms": list(terms)}
            for pk, score, terms in ranked if score >= MIN_LABEL_CONFIDENCE]


def suggest_service(text: str, limit: int = 3) -> list[dict]:
    services = list(Service.objects.filter(is_active=True))
    examples = {}
    for service in services:
        keyword_doc = f"{service.name} {service.description} {service.keywords}"
        examples[service.pk] = _label_examples(keyword_doc, _history_texts(service=service))
    names = {s.pk: s.name for s in services}
    ranked = CentroidClassifier(examples).rank(text, limit) if examples else []
    return [{"id": pk, "name": names[pk], "score": score, "matched_terms": list(terms)}
            for pk, score, terms in ranked if score >= MIN_LABEL_CONFIDENCE]


def _index_for(candidates: list[Incident]) -> SimilarityIndex:
    return SimilarityIndex([(i, i.search_text) for i in candidates],
                           extra_corpus=_history_texts())


def find_similar_incidents(text: str, service=None, exclude_pk: int | None = None, only_open: bool = True,
                           within_days: int | None = None, limit: int = 5,
                           min_score: float = RELATED_THRESHOLD) -> list[IncidentMatch]:
    candidates = Incident.objects.select_related("service", "assignee", "reporter")
    if only_open:
        candidates = candidates.filter(status__in=OPEN_STATUSES)
    if exclude_pk:
        candidates = candidates.exclude(pk=exclude_pk)
    if within_days:
        candidates = candidates.filter(created_at__gte=timezone.now() - timedelta(days=within_days))
    candidates = list(candidates.order_by("-id")[:CORPUS_LIMIT])
    if not candidates or not (text or "").strip():
        return []
    query = f"{text} {service.name}" if service else text
    matches = []
    for match in _index_for(candidates).search(query, limit=len(candidates)):
        boost = SAME_SERVICE_BOOST if service and match.item.service_id == service.pk else 0.0
        combined = round(min(1.0, match.score + boost), 3)
        if combined >= min_score:
            matches.append(IncidentMatch(match.item, combined, match.score, match.shared_terms))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]


def detect_duplicates(incident: Incident, limit: int = 5) -> list[IncidentMatch]:
    return find_similar_incidents(f"{incident.title} {incident.description}", incident.service,
                                  exclude_pk=incident.pk, within_days=14, limit=limit)


def suggest_resolutions(text: str, exclude_pk: int | None = None, limit: int = 3) -> list[dict]:
    solved = (Incident.objects.filter(status__in=FINISHED_STATUSES).exclude(resolution="")
              .select_related("service", "assignee").order_by("-id")[:CORPUS_LIMIT])
    solved = [i for i in solved if i.pk != exclude_pk]
    if not solved or not (text or "").strip():
        return []
    index = SimilarityIndex([(i, i.search_text) for i in solved])
    suggestions, seen = [], set()
    for match in index.search(text, limit=limit * 3, threshold=0.2):
        key = match.item.resolution.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append({
            "incident_code": match.item.code, "incident_id": match.item.pk, "title": match.item.title,
            "resolution": match.item.resolution, "score": match.score, "matched_terms": list(match.shared_terms),
            "solved_by": match.item.assignee.display_name if match.item.assignee_id else None,
        })
    return suggestions[:limit]


def correlate_open_incidents(min_score: float = RELATED_THRESHOLD) -> list[dict]:
    """Group open incidents that look like the same underlying problem."""
    incidents = list(Incident.objects.filter(status__in=OPEN_STATUSES).select_related("service")
                     .order_by("-id")[:CORPUS_LIMIT])
    if len(incidents) < 2:
        return []
    index = _index_for(incidents)
    parent = list(range(len(incidents)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j, score in index.pairwise(0.15):
        same_service = incidents[i].service_id and incidents[i].service_id == incidents[j].service_id
        if score + (SAME_SERVICE_BOOST if same_service else 0) >= min_score:
            parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(len(incidents)):
        groups.setdefault(find(i), []).append(i)
    clusters = []
    for members in groups.values():
        if len(members) < 2:
            continue
        centroid = SparseVector.centroid(index.vector_at(i) for i in members)
        group = [incidents[i] for i in members]
        services = sorted({i.service.name for i in group if i.service_id})
        clusters.append({
            "incident_ids": [i.pk for i in group], "incident_codes": [i.code for i in group],
            "titles": [i.title for i in group], "size": len(group), "services": services,
            "top_terms": centroid.top_terms(3), "highest_priority": min(i.priority for i in group),
        })
    clusters.sort(key=lambda c: (c["highest_priority"], -c["size"]))
    return clusters


class TechnicianAffinity:
    """Cosine similarity between an incident's text and each technician's profile.

    A profile is the technician's skill categories plus the incidents they have resolved before.
    """

    def __init__(self, technicians: list[User]):
        examples = {}
        for technician in technicians:
            docs = [f"{c.name} {c.keywords}" for c in technician.skills.all()]
            docs += [i.search_text for i in Incident.objects.filter(
                assignee=technician, status__in=FINISHED_STATUSES).select_related("service")[:30]]
            if docs:
                examples[technician.pk] = docs
        self._classifier = CentroidClassifier(examples) if examples else None

    def scores_for(self, text: str) -> dict[int, float]:
        if not self._classifier or not (text or "").strip():
            return {}
        return {pk: score for pk, score, _ in self._classifier.rank(text, limit=1000)}
