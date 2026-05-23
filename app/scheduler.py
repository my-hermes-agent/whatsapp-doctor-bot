"""
WhatsApp Doctor Bot — Appointment Reminders & Follow-up Scheduler
Uses APScheduler for background task scheduling.
"""

import os
import logging
from datetime import datetime, date, timedelta
from app import db
from app.models import Appointment, FollowUp

logger = logging.getLogger(__name__)

scheduler = None


def init_scheduler(app):
    """Initialize APScheduler with the Flask app context."""
    global scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()

        # Check every 30 minutes for upcoming appointments
        scheduler.add_job(
            func=_check_reminders,
            args=[app],
            trigger="interval",
            minutes=30,
            id="appointment_reminders",
            name="Send appointment reminders",
        )

        # Check every hour for follow-ups to send
        scheduler.add_job(
            func=_check_followups,
            args=[app],
            trigger="interval",
            minutes=60,
            id="followup_sender",
            name="Send post-consultation follow-ups",
        )

        scheduler.start()
        logger.info("Scheduler started: reminders + follow-ups")
    except ImportError:
        logger.warning("APScheduler not installed. Reminders/follow-ups disabled.")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")


def _check_reminders(app):
    """Check for appointments needing reminders (24h and 1h before)."""
    with app.app_context():
        now = datetime.utcnow()
        today = now.date()

        # 24h reminder: appointments tomorrow
        tomorrow = today + timedelta(days=1)
        appointments_24h = Appointment.query.filter(
            Appointment.status.in_([Appointment.STATUS_BOOKED, Appointment.STATUS_CONFIRMED]),
            Appointment.appointment_date == tomorrow,
        ).all()

        # 1h reminder: appointments today within next hour
        one_hour_later = now + timedelta(hours=1)
        appointments_1h = Appointment.query.filter(
            Appointment.status.in_([Appointment.STATUS_BOOKED, Appointment.STATUS_CONFIRMED]),
            Appointment.appointment_date == today,
            Appointment.appointment_time <= one_hour_later.time(),
            Appointment.appointment_time > now.time(),
        ).all()

        from .messaging import send_appointment_reminder

        for apt in appointments_24h:
            try:
                send_appointment_reminder(apt, hours_before=24)
                logger.info(f"24h reminder sent: {apt.booking_id}")
            except Exception as e:
                logger.error(f"Failed to send 24h reminder for {apt.booking_id}: {e}")

        for apt in appointments_1h:
            try:
                send_appointment_reminder(apt, hours_before=1)
                logger.info(f"1h reminder sent: {apt.booking_id}")
            except Exception as e:
                logger.error(f"Failed to send 1h reminder for {apt.booking_id}: {e}")


def _check_followups(app):
    """Check for completed appointments that need follow-up messages."""
    with app.app_context():
        followup_delay_hours = app.config.get("FOLLOWUP_DELAY_HOURS", 24)
        cutoff = datetime.utcnow() - timedelta(hours=followup_delay_hours)

        # Find pending follow-ups where appointment was completed long enough ago
        pending = (
            db.session.query(FollowUp)
            .join(Appointment)
            .filter(
                FollowUp.status == FollowUp.STATUS_PENDING,
                Appointment.status == Appointment.STATUS_COMPLETED,
                Appointment.updated_at <= cutoff,
            )
            .all()
        )

        from .messaging import send_followup_message

        for fu in pending:
            try:
                send_followup_message(fu.appointment)
                fu.status = FollowUp.STATUS_SENT
                fu.sent_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Follow-up sent: appointment {fu.appointment_id}")
            except Exception as e:
                logger.error(f"Failed to send follow-up for appointment {fu.appointment_id}: {e}")
                db.session.rollback()
