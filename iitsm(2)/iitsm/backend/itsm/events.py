"""Observer pattern: a tiny synchronous event bus. Domain code publishes events; observers react."""
import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("itsm")


@dataclass
class Event:
    type: str
    incident: Any
    actor: Any = None          # None = system
    description: str = ""
    previous_state: str = ""
    new_state: str = ""
    internal: bool = False     # internal comments are hidden from the reporter


class EventBus:
    def __init__(self):
        self._observers = []

    def subscribe(self, observer):
        if not any(type(o) is type(observer) for o in self._observers):
            self._observers.append(observer)

    def publish(self, event: Event):
        for obs in list(self._observers):
            try:
                obs.handle(event)
            except Exception:           # one faulty observer must never break the business flow
                log.exception("Observer %s failed on %s", type(obs).__name__, event.type)


bus = EventBus()
