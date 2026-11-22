"""Text similarity engine: TF-IDF vectors compared with cosine similarity.

Pure Python on purpose: no ML dependency, easy to explain, and fast enough for
thousands of incidents. Everything that needs "how alike are these two pieces
of text" goes through this module:

* duplicate detection and incident correlation  (SimilarityIndex)
* category / service suggestion                  (CentroidClassifier)
* suggested resolutions                          (SimilarityIndex over resolved incidents)
* technician affinity and search ranking         (TfidfModel + SparseVector)
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Generic, Hashable, Iterable, Sequence, TypeVar

T = TypeVar("T")

STOPWORDS = frozenset(
    "a an and are as at be been but by can could did do does for from get got had has have he her his i if in "
    "into is it its me my no not of on or our she so that the their them there these they this those to too us "
    "was we were what when where which while who why will with would you your please hi hello kindly just since "
    "also all any some very being am im ive today now again still".split()
)

# Words that mean the same thing in an incident report. Mapped before stemming.
SYNONYMS = {
    "unavailable": "down", "outage": "down", "offline": "down", "unreachable": "down", "crashed": "down",
    "crash": "down", "dead": "down", "inaccessible": "down", "stopped": "down", "unresponsive": "down",
    "failing": "fail", "failed": "fail", "failure": "fail", "failures": "fail", "error": "fail",
    "errors": "fail", "broken": "fail", "declined": "fail",
    "unable": "cannot", "cant": "cannot", "couldnt": "cannot", "wont": "cannot", "cannot": "cannot",
    "transaction": "payment", "transactions": "payment", "checkout": "payment", "billing": "payment",
    "laptop": "device", "notebook": "device", "pc": "device", "desktop": "device", "computer": "device",
    "slow": "latency", "sluggish": "latency", "lag": "latency", "laggy": "latency", "timeout": "latency",
    "timeouts": "latency", "timing": "latency",
    "wifi": "network", "lan": "network", "internet": "network", "vpn": "network",
    "password": "credential", "passwords": "credential", "login": "signin", "logon": "signin",
    "mail": "email", "outlook": "email", "mailbox": "email",
    "db": "database", "sql": "database", "query": "database", "queries": "database",
}

_PHRASES = re.compile(
    r"\b(not working|doesnt work|isnt working|stopped working|wont load|not loading|not responding)\b"
)
_TOKEN = re.compile(r"[a-z0-9]+")


def stem(token: str) -> str:
    """Very light suffix stripping so 'payments', 'payment' and 'paying' line up."""
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("sses"):
        return token[:-2]
    for suffix in ("ing", "ed"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    if token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    cleaned = _PHRASES.sub(" down ", (text or "").lower().replace("'", ""))
    tokens: list[str] = []
    for raw in _TOKEN.findall(cleaned):
        if raw in STOPWORDS:
            continue
        mapped = SYNONYMS.get(raw)
        tokens.append(mapped if mapped else stem(raw))
    return tokens


def extract_terms(text: str) -> list[str]:
    """Unigrams plus adjacent-word bigrams (so 'payment down' outweighs 'payment' alone)."""
    tokens = tokenize(text)
    bigrams = [f"{a}_{b}" for a, b in zip(tokens, tokens[1:]) if a != b]
    return tokens + bigrams


class SparseVector:
    """Immutable term -> weight mapping with cosine similarity."""

    __slots__ = ("_weights", "_norm")

    def __init__(self, weights: dict[str, float]):
        self._weights = dict(weights)
        self._norm = math.sqrt(sum(w * w for w in self._weights.values()))

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    @property
    def is_empty(self) -> bool:
        return self._norm == 0.0

    def cosine_similarity(self, other: "SparseVector") -> float:
        if self.is_empty or other.is_empty:
            return 0.0
        small, large = (self._weights, other._weights) if len(self._weights) <= len(other._weights) \
            else (other._weights, self._weights)
        dot = sum(w * large[t] for t, w in small.items() if t in large)
        return max(0.0, min(1.0, dot / (self._norm * other._norm)))

    def shared_terms(self, other: "SparseVector", limit: int = 3) -> list[str]:
        """The terms contributing most to a match, for human-readable explanations."""
        contributions = {t: w * other._weights[t] for t, w in self._weights.items() if t in other._weights}
        ordered = sorted(contributions, key=contributions.get, reverse=True)
        readable = [t.replace("_", " ") for t in ordered]
        unigrams = [t for t in readable if " " not in t]
        return (unigrams or readable)[:limit]

    def top_terms(self, limit: int = 3) -> list[str]:
        ordered = sorted(self._weights, key=self._weights.get, reverse=True)
        return [t for t in ordered if "_" not in t][:limit]

    @classmethod
    def centroid(cls, vectors: Iterable["SparseVector"]) -> "SparseVector":
        total: Counter = Counter()
        for vector in vectors:
            if vector.is_empty:
                continue
            for term, weight in vector._weights.items():
                total[term] += weight / vector._norm
        return cls(dict(total))


def cosine_similarity(first: SparseVector, second: SparseVector) -> float:
    return first.cosine_similarity(second)


class TfidfModel:
    """Learns inverse document frequencies from a corpus and turns text into vectors."""

    def __init__(self, documents: Iterable[str]):
        self._document_count = 0
        self._document_frequency: Counter = Counter()
        for text in documents:
            self._document_frequency.update(set(extract_terms(text)))
            self._document_count += 1

    def inverse_document_frequency(self, term: str) -> float:
        return math.log((1 + self._document_count) / (1 + self._document_frequency.get(term, 0))) + 1.0

    def vectorize(self, text: str) -> SparseVector:
        counts = Counter(extract_terms(text))
        return SparseVector({
            term: (1.0 + math.log(count)) * self.inverse_document_frequency(term)
            for term, count in counts.items()
        })


@dataclass(frozen=True)
class SimilarMatch(Generic[T]):
    item: T
    score: float
    shared_terms: tuple[str, ...]


class SimilarityIndex(Generic[T]):
    """Find the items whose text is closest to a query."""

    def __init__(self, entries: Sequence[tuple[T, str]], extra_corpus: Iterable[str] = ()):
        self._entries = list(entries)
        self._model = TfidfModel([text for _, text in self._entries] + list(extra_corpus))
        self._vectors = [self._model.vectorize(text) for _, text in self._entries]

    @property
    def model(self) -> TfidfModel:
        return self._model

    def search(self, query: str, limit: int = 5, threshold: float = 0.0) -> list[SimilarMatch[T]]:
        query_vector = self._model.vectorize(query)
        matches = []
        for (item, _), vector in zip(self._entries, self._vectors):
            score = query_vector.cosine_similarity(vector)
            if score > 0 and score >= threshold:
                matches.append(SimilarMatch(item, round(score, 3), tuple(query_vector.shared_terms(vector))))
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:limit]

    def pairwise(self, threshold: float) -> list[tuple[int, int, float]]:
        """Index pairs (i, j) of entries whose similarity reaches the threshold."""
        pairs = []
        for i in range(len(self._vectors)):
            for j in range(i + 1, len(self._vectors)):
                score = self._vectors[i].cosine_similarity(self._vectors[j])
                if score >= threshold:
                    pairs.append((i, j, score))
        return pairs

    def vector_at(self, index: int) -> SparseVector:
        return self._vectors[index]


class CentroidClassifier:
    """Suggest a label by comparing text to the centroid of each label's example texts."""

    def __init__(self, examples: dict[Hashable, Sequence[str]], extra_corpus: Iterable[str] = ()):
        flat = [text for texts in examples.values() for text in texts]
        self._model = TfidfModel(flat + list(extra_corpus))
        self._centroids = {
            label: SparseVector.centroid(self._model.vectorize(t) for t in texts)
            for label, texts in examples.items()
        }

    def rank(self, text: str, limit: int = 3) -> list[tuple[Hashable, float, tuple[str, ...]]]:
        vector = self._model.vectorize(text)
        scored = []
        for label, centroid in self._centroids.items():
            score = vector.cosine_similarity(centroid)
            if score > 0:
                scored.append((label, round(score, 3), tuple(vector.shared_terms(centroid))))
        scored.sort(key=lambda row: row[1], reverse=True)
        return scored[:limit]
