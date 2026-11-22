"""Observer pattern: domain code publishes events; observers react.

The incident services never write audit rows or send notifications directly.
They publish a DomainEvent and every registered observer decides what to do.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DomainEvent:
    name: str                         # past tense, e.g. "IncidentReported"
    incident: Any = None
    actor: Any = None
    previous_state: str = ""
    new_state: str = ""
    description: str = ""
    payload: dict = field(default_factory=dict)


class EventObserver(ABC):
    @abstractmethod
    def handle(self, event: DomainEvent) -> None:
        """React to a published event."""


class EventBus:
    def __init__(self):
        self._observers: list[EventObserver] = []

    def subscribe(self, observer: EventObserver) -> None:
        if not any(type(existing) is type(observer) for existing in self._observers):
            self._observers.append(observer)

    def publish(self, event: DomainEvent) -> None:
        for observer in self._observers:
            try:
                observer.handle(event)
            except Exception:  # an observer must never break the business operation
                logger.exception("Observer %s failed on %s", type(observer).__name__, event.name)


event_bus = EventBus()
