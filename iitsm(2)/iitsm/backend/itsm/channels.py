"""Notification channels (Strategy + Factory). New channels = one subclass + one register() call."""
import logging
from abc import ABC, abstractmethod

from .models import Notification

log = logging.getLogger("itsm")


class NotificationChannel(ABC):
    name = ""

    @abstractmethod
    def send(self, recipient, incident, message): ...


class InAppChannel(NotificationChannel):
    name = "IN_APP"

    def send(self, recipient, incident, message):
        Notification.objects.create(recipient=recipient, incident=incident, channel=self.name, message=message)


class EmailChannel(NotificationChannel):          # simulated: logs to console + stores in outbox
    name = "EMAIL"

    def send(self, recipient, incident, message):
        log.info("[EMAIL -> %s <%s>] %s", recipient.username, recipient.email or "n/a", message)
        Notification.objects.create(recipient=recipient, incident=incident, channel=self.name, message=message)


class SMSChannel(NotificationChannel):            # simulated
    name = "SMS"

    def send(self, recipient, incident, message):
        log.info("[SMS -> %s] %s", recipient.username, message)
        Notification.objects.create(recipient=recipient, incident=incident, channel=self.name, message=message)


class ChannelFactory:
    _registry = {}

    @classmethod
    def register(cls, channel: NotificationChannel):
        cls._registry[channel.name] = channel

    @classmethod
    def get(cls, name) -> NotificationChannel:
        return cls._registry[name]


for _c in (InAppChannel(), EmailChannel(), SMSChannel()):
    ChannelFactory.register(_c)
