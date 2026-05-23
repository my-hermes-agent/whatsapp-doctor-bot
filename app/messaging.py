"""
WhatsApp Doctor Bot — Twilio Message Sender
Handles sending WhatsApp messages via Twilio API with dev-mode fallback.
"""

import os
import logging
from flask import current_app

logger = logging.getLogger(__name__)


def send_whatsapp_message(to_phone, body):
    """
    Send a WhatsApp message via Twilio.
    In TWILIO_DEV_MODE, just logs the message instead.
    """
    dev_mode = os.getenv("TWILIO_DEV_MODE", "0") == "1"

    if dev_mode:
        logger.info(f"[DEV MODE] To: {to_phone}\n{body}")
        return {"dev_mode": True, "to": to_phone, "body": body[:100]}

    account_sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    api_key_sid = current_app.config.get("TWILIO_API_KEY_SID")
    api_key_secret = current_app.config.get("TWILIO_API_KEY_SECRET")
    from_number = current_app.config.get("TWILIO_WHATSAPP_NUMBER")

    if not all([account_sid, api_key_sid, api_key_secret]):
        logger.error("Missing Twilio credentials. Set TWILIO_DEV_MODE=1 for local testing.")
        return {"error": "missing_credentials"}

    try:
        from twilio.rest import Client
        client = Client(api_key_sid, api_key_secret, account_sid)

        message = client.messages.create(
            from_=f"whatsapp:{from_number.replace('whatsapp:', '')}",
            to=f"whatsapp:{to_phone}",
            body=body,
        )
        logger.info(f"Message sent: SID={message.sid}, To={to_phone}")
        return {"sid": message.sid, "status": message.status}

    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}", exc_info=True)
        return {"error": str(e)}


def send_appointment_reminder(appointment, hours_before):
    """Send an appointment reminder to a patient."""
    from .models import Appointment

    time_str = appointment.appointment_time.strftime("%I:%M %p").lstrip("0")
    date_str = appointment.appointment_date.strftime("%a, %b %d")

    if hours_before <= 1:
        urgency = "🔔 *Reminder: Your appointment is in 1 HOUR!*\n\n"
    else:
        urgency = "📅 *Reminder: Your appointment is tomorrow!*\n\n"

    body = (
        f"{urgency}"
        f"👨‍⚕️ {appointment.doctor.name}\n"
        f"📋 {appointment.doctor.display_specialization}\n"
        f"🏥 {appointment.doctor.display_hospital}\n"
        f"📅 {date_str}\n"
        f"🕐 {time_str}\n"
        f"🆔 Booking: *{appointment.booking_id}*\n\n"
        "Type CANCEL <Booking ID> if you need to cancel."
    )

    return send_whatsapp_message(appointment.patient.phone, body)


def send_followup_message(appointment):
    """Send a post-consultation follow-up message."""
    body = (
        f"👋 *How are you feeling?*\n\n"
        f"You visited *{appointment.doctor.name}* on "
        f"{appointment.appointment_date.strftime('%a, %b %d')}.\n\n"
        "Rate your recovery (1 = Poor, 5 = Excellent):\n\n"
        "1️⃣ 😟 Very Poor\n"
        "2️⃣ 😕 Poor\n"
        "3️⃣ 😐 Okay\n"
        "4️⃣ 🙂 Good\n"
        "5️⃣ 😄 Excellent\n\n"
        "_Reply with a number (1-5)_"
    )

    return send_whatsapp_message(appointment.patient.phone, body)
