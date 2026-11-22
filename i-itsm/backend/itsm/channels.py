"""Notification channels (Strategy for delivery, Factory for choosing them)."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from django.core.mail import send_mail

from .models import IncidentPriority, Notification

logger = logging.getLogger(__name__)


class NotificationChannel(ABC):
    name: str

    @abstractmethod
    def deliver(self, recipient, incident, subject: str, body: str) -> Notification:
        """Deliver the message and return the stored record."""

    def _record(self, recipient, incident, subject, body) -> Notification:
        return Notification.objects.create(recipient=recipient, incident=incident, channel=self.name,
                                           subject=subject, body=body)


class InAppChannel(NotificationChannel):
    name = Notification.Channel.IN_APP

    def deliver(self, recipient, incident, subject, body):
        return self._record(recipient, incident, subject, body)


class EmailChannel(NotificationChannel):
    """Simulated: printed by Django's console backend and kept in the outbox table."""
    name = Notification.Channel.EMAIL

    def deliver(self, recipient, incident, subject, body):
        if recipient.email:
            send_mail(f"[I-ITSM] {subject}", body, "itsm@example.org", [recipient.email], fail_silently=True)
        return self._record(recipient, incident, subject, body)


class SmsChannel(NotificationChannel):
    """Simulated: logged and kept in the outbox table."""
    name = Notification.Channel.SMS

    def deliver(self, recipient, incident, subject, body):
        logger.info("SMS to %s: %s", recipient.phone or recipient.username, subject)
        return self._record(recipient, incident, subject, body[:160])


class ChannelFactory:
    _channels = {channel.name: channel for channel in (InAppChannel(), EmailChannel(), SmsChannel())}
    EMAIL_EVENTS = {"TechnicianAssigned", "IncidentResolved", "IncidentClosed", "InformationRequested",
                    "SlaViolated", "IncidentEscalated"}
    SMS_EVENTS = {"SlaViolated", "IncidentEscalated"}

    @classmethod
    def create(cls, name: str) -> NotificationChannel:
        return cls._channels[name]

    @classmethod
    def for_event(cls, event_name: str, incident) -> list[NotificationChannel]:
        names = [Notification.Channel.IN_APP]
        if event_name in cls.EMAIL_EVENTS:
            names.append(Notification.Channel.EMAIL)
        critical = incident is not None and incident.priority == IncidentPriority.P1
        if event_name in cls.SMS_EVENTS or (critical and event_name == "TechnicianAssigned"):
            names.append(Notification.Channel.SMS)
        return [cls.create(name) for name in names]
