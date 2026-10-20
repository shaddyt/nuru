"""Outbound SMS via Africa's Talking.

Defaults are safe for development:
  * AT_USERNAME=sandbox talks to the Africa's Talking sandbox (no real SMS);
  * NURU_SMS_DRY_RUN=true (default) does not call any API at all and only
    logs a redacted line, which is what the tests and simulator use.

Privacy: we log a salted hash of the phone number, never the number itself,
and never the message body.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol

from .config import Settings

log = logging.getLogger("nuru.sms")


def hash_phone(phone: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{phone}".encode()).hexdigest()[:16]


class SmsSender(Protocol):
    def send(self, to: str, message: str, link_id: Optional[str] = None) -> dict: ...


@dataclass
class DryRunSender:
    """Records messages in memory. Used by tests, the simulator and dry-run mode."""

    salt: str = "dev"
    outbox: list[tuple[str, str]] = field(default_factory=list)

    def send(self, to: str, message: str, link_id: Optional[str] = None) -> dict:
        self.outbox.append((to, message))
        log.info("dry-run sms to=%s chars=%d", hash_phone(to, self.salt), len(message))
        return {"status": "dry_run"}


class AfricasTalkingSender:
    """Sends replies with the official africastalking SDK.

    For a two-way shortcode the reply is sent from the shortcode (AT_SHORTCODE).
    Premium (subscription) shortcodes also need the inbound linkId, which we
    pass through when present.
    """

    def __init__(self, username: str, api_key: str, shortcode: str = "", salt: str = "dev"):
        import africastalking  # imported lazily so tests do not need network setup

        africastalking.initialize(username, api_key)
        self._sms = africastalking.SMS
        self.shortcode = shortcode or None
        self.salt = salt

    def send(self, to: str, message: str, link_id: Optional[str] = None) -> dict:
        try:
            if link_id and self.shortcode:
                resp = self._sms.send_premium(message, self.shortcode, [to], link_id=link_id)
            else:
                resp = self._sms.send(message, [to], self.shortcode)
            log.info("sms sent to=%s chars=%d", hash_phone(to, self.salt), len(message))
            return resp
        except Exception as exc:  # pragma: no cover - network path
            log.error("sms send failed to=%s error=%s", hash_phone(to, self.salt), type(exc).__name__)
            return {"status": "error", "error": type(exc).__name__}


def build_sender(settings: Settings) -> SmsSender:
    if settings.sms_dry_run or not settings.at_api_key:
        return DryRunSender(salt=settings.phone_hash_salt)
    return AfricasTalkingSender(
        settings.at_username, settings.at_api_key, settings.at_shortcode, settings.phone_hash_salt
    )
