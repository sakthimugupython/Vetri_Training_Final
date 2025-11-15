import json
import logging
import re
from typing import Mapping, Optional

from django.conf import settings

try:
    from twilio.rest import Client
except ImportError:  # pragma: no cover - Twilio optional during local dev/tests
    Client = None  # type: ignore

logger = logging.getLogger(__name__)


def _get_twilio_client() -> Optional["Client"]:
    if Client is None:
        logger.warning("Twilio SDK is not installed. Skipping WhatsApp notification.")
        return None
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
        logger.debug("Twilio credentials missing; WhatsApp notifications disabled.")
        return None
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def _normalise_number(raw: str) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("whatsapp:"):
        return raw

    digits = re.sub(r"[^0-9+]", "", raw)
    if not digits:
        return None

    if digits.startswith("+"):
        formatted = digits
    elif digits.startswith("00"):
        formatted = f"+{digits[2:]}"
    else:
        plain_digits = re.sub(r"\D", "", digits)
        if len(plain_digits) == 10:
            # Assume Indian mobile if 10 digits without country code
            formatted = f"+91{plain_digits}"
        elif len(plain_digits) == 12 and plain_digits.startswith("91"):
            formatted = f"+{plain_digits}"
        else:
            logger.debug("Unable to infer country code for phone number '%s'", raw)
            return None

    return f"whatsapp:{formatted}"


def _twilio_from_number() -> Optional[str]:
    number = getattr(settings, "TWILIO_WHATSAPP_NUMBER", "")
    formatted = _normalise_number(number)
    if not formatted:
        logger.debug("Twilio WhatsApp sender number is not configured correctly.")
    return formatted


def send_whatsapp_message(
    to_number: str,
    *,
    body: Optional[str] = None,
    template_sid: Optional[str] = None,
    template_variables: Optional[Mapping[str, str]] = None,
) -> bool:
    if not to_number:
        return False

    to = _normalise_number(to_number)
    if not to:
        logger.debug("Skipping WhatsApp send; invalid recipient number '%s'", to_number)
        return False

    client = _get_twilio_client()
    if not client:
        return False

    sender = _twilio_from_number()
    if not sender:
        return False

    payload = {"from_": sender, "to": to}

    if template_sid:
        payload["content_sid"] = template_sid
        if template_variables:
            payload["content_variables"] = json.dumps(template_variables)
    elif body:
        payload["body"] = body.strip()
    else:
        logger.debug("Neither body nor template provided for WhatsApp message to %s", to)
        return False

    try:
        message = client.messages.create(**payload)  # type: ignore[arg-type]
        logger.info("WhatsApp message %s queued for %s", message.sid, to)
        return True
    except Exception as exc:  # pragma: no cover - network failure
        logger.exception("Failed to send WhatsApp message to %s: %s", to, exc)
        return False


def _snippet(text: Optional[str], limit: int = 120) -> str:
    if not text:
        return ""
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}…"


def send_admin_announcement(phone: str, *, title: str, preview: Optional[str] = None) -> bool:
    message = (
        f"VTS Academy: New update from Admin – {title}. "
        f"{_snippet(preview or '')} Read more in your dashboard."
    ).strip()
    return send_whatsapp_message(phone, body=message)


def send_trainer_announcement(
    phone: str,
    *,
    trainer_name: str,
    title: str,
    preview: Optional[str] = None,
) -> bool:
    message = (
        f"Trainer {trainer_name} shared an announcement: {title}. "
        f"{_snippet(preview or '')} Check the portal for details."
    ).strip()
    return send_whatsapp_message(phone, body=message)


def send_attendance_update(
    phone: str,
    *,
    date_display: str,
    status: str,
    remarks: Optional[str] = None,
) -> bool:
    cleaned_status = status.replace("_", " ").title()
    info = f"Remarks: {remarks}" if remarks else "No remarks."
    message = (
        f"Attendance {date_display}: You were marked {cleaned_status}. {info} "
        "Contact your trainer if this is unexpected."
    )
    return send_whatsapp_message(phone, body=message)


def send_daily_task_update(
    phone: str,
    *,
    assigned_today: int,
    completed: int,
    remaining: int,
) -> bool:
    message = (
        "Daily tasks updated: "
        f"Assigned today {assigned_today} | Completed {completed} | Remaining {remaining}. "
        "Keep up the progress!"
    )
    return send_whatsapp_message(phone, body=message)
