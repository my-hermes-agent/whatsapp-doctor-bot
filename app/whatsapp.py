"""
WhatsApp Doctor Bot — Conversation State Machine & Webhook Handler

Flow: Start → Select Specialization → Select Doctor → Hospital Info
      → Select Date → Select Time → Confirm → ✅ Booked

Each state produces a clean, scannable WhatsApp message with numbered options.
"""

import re
import json
from datetime import datetime, date, timedelta, time as dtime
from flask import Blueprint, request, current_app
from app import db
from app.models import Doctor, Patient, Appointment, FollowUp, ConversationSession

whatsapp_bp = Blueprint("whatsapp", __name__)


# ─── State Constants ───

STATE_START = "start"
STATE_REGISTER = "register"
STATE_MENU = "menu"
STATE_SELECT_SPEC = "select_specialization"
STATE_SELECT_DOCTOR = "select_doctor"
STATE_HOSPITAL_INFO = "hospital_info"
STATE_SELECT_DATE = "select_date"
STATE_SELECT_TIME = "select_time"
STATE_CONFIRM = "confirm_booking"
STATE_BOOKED = "booked"
STATE_MY_APPOINTMENTS = "my_appointments"
STATE_FOLLOWUP_RATING = "followup_rating"
STATE_FOLLOWUP_SYMPTOMS = "followup_symptoms"

# ─── Helper Functions ───

def _get_or_create_session(phone):
    """Get existing conversation session or create a new one."""
    session = ConversationSession.query.filter_by(patient_phone=phone).first()
    if not session:
        session = ConversationSession(patient_phone=phone, state=STATE_START, context="{}")
        db.session.add(session)
        db.session.commit()
    return session


def _get_or_create_patient(phone, name=None):
    """Get existing patient or create new one."""
    patient = Patient.query.filter_by(phone=phone).first()
    if not patient and name:
        patient = Patient(phone=phone, name=name)
        db.session.add(patient)
        db.session.commit()
    return patient


def _normalize_input(text):
    """Clean and normalize user input."""
    return text.strip().lower()


def _get_available_specializations():
    """Get distinct active specializations with doctor counts."""
    results = db.session.query(
        Doctor.specialization,
        db.func.count(Doctor.id).label("count")
    ).filter(
        Doctor.is_active == True
    ).group_by(
        Doctor.specialization
    ).order_by(
        Doctor.specialization
    ).all()
    return [(r.specialization, r.count) for r in results]


def _get_doctors_by_spec(specialization):
    """Get active doctors for a given specialization."""
    return Doctor.query.filter_by(
        specialization=specialization, is_active=True
    ).order_by(Doctor.experience.desc()).all()


def _get_next_weekdays(num_days=5):
    """Get next N weekdays starting from tomorrow (skip Sundays)."""
    days = []
    today = date.today()
    d = today + timedelta(days=1)
    while len(days) < num_days:
        if d.weekday() != 6:  # Skip Sunday
            days.append(d)
        d += timedelta(days=1)
    return days


def _get_time_slots():
    """Generate available time slots (30-min intervals)."""
    slots = []
    for hour in range(9, 17):  # 9 AM to 5 PM
        slots.append(dtime(hour, 0))
        slots.append(dtime(hour, 30))
    return slots


def _format_date(d):
    """Format date as 'Mon, Jun 2'."""
    return d.strftime("%a, %b %d")


def _format_time(t):
    """Format time as '9:00 AM'."""
    return t.strftime("%I:%M %p").lstrip("0")


# ─── Message Builders (Clean WhatsApp UI) ───

def _msg_welcome():
    return (
        "🏥 *Nellore Doctor Bot*\n\n"
        "Your health companion in Nellore!\n"
        "Book appointments with top doctors — right here on WhatsApp.\n\n"
        "👇 *What would you like to do?*\n\n"
        "1️⃣ Book Appointment\n"
        "2️⃣ My Appointments\n"
        "3️⃣ My Profile\n"
        "4️⃣ Help\n\n"
        "_Reply with a number (1-4)_"
    )


def _msg_register():
    return (
        "👋 *Welcome to Nellore Doctor Bot!*\n\n"
        "Let's get you registered first.\n\n"
        "📝 _Please reply with your full name_"
    )


def _msg_select_specialization():
    specs = _get_available_specializations()
    if not specs:
        return "⚠️ No specializations available at the moment. Please try later."

    emoji_map = {
        "Cardiology": "❤️", "Orthopaedics": "🦴", "Neurology": "🧠",
        "Gynaecology": "🤱", "Pediatrics": "👶", "General Medicine": "💊",
        "Gastroenterology": "🫁", "Urology": "🩺", "Dermatology": "🧴",
        "Pulmonology": "🫁", "Oncology": "🎗️", "Endocrinology": "🦋",
        "Rheumatology": "🦴", "Neurosurgery": "🧠", "General Surgery": "🔪",
        "Microbiology": "🔬", "Family Medicine": "👨‍⚕️",
    }

    lines = [
        "🔍 *Select a Specialization*\n",
    ]
    for i, (spec, count) in enumerate(specs, 1):
        emoji = emoji_map.get(spec, "🏥")
        lines.append(f"{i}️⃣ {emoji} {spec} ({count} doctor{'s' if count > 1 else ''})")

    lines.append(f"\n_Reply with a number (1-{len(specs)})_")
    lines.append("_Type 0 to go back to menu_")
    return "\n".join(lines)


def _msg_select_doctor(specialization):
    doctors = _get_doctors_by_spec(specialization)
    if not doctors:
        return f"⚠️ No doctors available for {specialization}. Type 0 to go back."

    lines = [
        f"👨‍⚕️ *{specialization} Doctors in Nellore*\n",
    ]
    for i, doc in enumerate(doctors, 1):
        sub = f" ({doc.sub_specialization})" if doc.sub_specialization else ""
        lines.append(f"{i}️⃣ *{doc.name}*")
        lines.append(f"    {doc.specialization}{sub}")
        lines.append(f"    🏥 {doc.display_hospital}")
        lines.append(f"    ⏰ {doc.timings}")
        lines.append(f"    🏅 {doc.experience} yrs exp\n")

    lines.append(f"_Reply with a number (1-{len(doctors)})_")
    lines.append("_Type 0 to change specialization_")
    return "\n".join(lines)


def _msg_hospital_info(doctor):
    return (
        f"🏥 *{doctor.display_hospital}*\n\n"
        f"👨‍⚕️ *{doctor.name}*\n"
        f"📋 {doctor.display_specialization}\n"
        f"⏰ {doctor.timings}\n"
        f"🏅 {doctor.experience} years experience\n\n"
        "👇 *Next: Pick a date for your appointment*\n\n"
        "_Type NEXT to select a date_\n"
        "_Type 0 to pick a different doctor_"
    )


def _msg_select_date():
    days = _get_next_weekdays(5)
    lines = [
        "📅 *Select a Date*\n",
    ]
    for i, d in enumerate(days, 1):
        day_label = _format_date(d)
        lines.append(f"{i}️⃣ {day_label}")

    lines.append(f"\n_Reply with a number (1-{len(days)})_")
    lines.append("_Type 0 to go back_")
    return "\n".join(lines)


def _msg_select_time(doctor):
    slots = _get_time_slots()
    lines = [
        "🕐 *Select a Time Slot*\n",
    ]
    for i, t in enumerate(slots, 1):
        lines.append(f"{i}️⃣ {_format_time(t)}")

    lines.append(f"\n_Reply with a number (1-{len(slots)})_")
    lines.append("_Type 0 to change date_")
    return "\n".join(lines)


def _msg_confirm(doctor, appointment_date, appointment_time, patient):
    date_str = _format_date(appointment_date)
    time_str = _format_time(appointment_time)
    return (
        "✅ *Confirm Your Appointment*\n\n"
        f"👨‍⚕️ *{doctor.name}*\n"
        f"📋 {doctor.display_specialization}\n"
        f"🏥 {doctor.display_hospital}\n"
        f"📅 {date_str}\n"
        f"🕐 {time_str}\n"
        f"⏰ OPD: {doctor.timings}\n"
        f"👤 Patient: {patient.name}\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "_Reply *YES* to confirm_\n"
        "_Reply *NO* to cancel and start over_"
    )


def _msg_booking_confirmed(appointment):
    return (
        "🎉 *Appointment Confirmed!*\n\n"
        f"🆔 Booking ID: *{appointment.booking_id}*\n"
        f"👨‍⚕️ {appointment.doctor.name}\n"
        f"📋 {appointment.doctor.display_specialization}\n"
        f"🏥 {appointment.doctor.display_hospital}\n"
        f"📅 {_format_date(appointment.appointment_date)}\n"
        f"🕐 {_format_time(appointment.appointment_time)}\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "💡 _Save your Booking ID for future reference_\n"
        "💡 _You'll get a reminder 24h and 1h before_\n\n"
        "_Type MENU to return to main menu_"
    )


def _msg_my_appointments(patient):
    appointments = Appointment.query.filter_by(
        patient_id=patient.id
    ).filter(
        Appointment.status.in_([Appointment.STATUS_BOOKED, Appointment.STATUS_CONFIRMED])
    ).order_by(
        Appointment.appointment_date, Appointment.appointment_time
    ).all()

    if not appointments:
        return (
            "📋 *My Appointments*\n\n"
            "You have no upcoming appointments.\n\n"
            "_Type MENU to book one_"
        )

    lines = ["📋 *Your Upcoming Appointments*\n"]
    for i, apt in enumerate(appointments, 1):
        lines.append(f"{i}️⃣ *{apt.booking_id}*")
        lines.append(f"   👨‍⚕️ {apt.doctor.name}")
        lines.append(f"   📋 {apt.doctor.display_specialization}")
        lines.append(f"   🏥 {apt.doctor.display_hospital}")
        lines.append(f"   📅 {_format_date(apt.appointment_date)}")
        lines.append(f"   🕐 {_format_time(apt.appointment_time)}\n")

    lines.append("_Type MENU to return_")
    lines.append("_Type CANCEL <Booking ID> to cancel_")
    return "\n".join(lines)


def _msg_profile(patient):
    total = Appointment.query.filter_by(patient_id=patient.id).count()
    upcoming = Appointment.query.filter_by(
        patient_id=patient.id, status=Appointment.STATUS_BOOKED
    ).count()
    completed = Appointment.query.filter_by(
        patient_id=patient.id, status=Appointment.STATUS_COMPLETED
    ).count()
    return (
        "👤 *Your Profile*\n\n"
        f"📱 {patient.phone}\n"
        f"📛 {patient.name}\n"
        f"📅 Member since: {patient.created_at.strftime('%b %d, %Y')}\n\n"
        f"📊 *Stats*\n"
        f"  Total appointments: {total}\n"
        f"  Upcoming: {upcoming}\n"
        f"  Completed: {completed}\n\n"
        "_Type MENU to return_"
    )


def _msg_help():
    return (
        "❓ *Help — How to Use This Bot*\n\n"
        "🔹 *Book Appointment*\n"
        "  Pick a specialization → doctor → date → time → confirm!\n\n"
        "🔹 *My Appointments*\n"
        "  View your upcoming bookings\n\n"
        "🔹 *Cancel Appointment*\n"
        "  Type CANCEL followed by your Booking ID\n"
        "  Example: CANCEL NEL-250523093000-42\n\n"
        "🔹 *Quick Commands*\n"
        "  MENU — Return to main menu\n"
        "  HELP — Show this message\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "🏥 *Nellore Doctor Bot*\n"
        "Hospitals: Apollo, Medicover, KIMS, Enel, Shine & more\n"
        "_Type MENU to return_"
    )


def _msg_followup_rating(appointment):
    return (
        f"👋 *How are you feeling?*\n\n"
        f"You visited *{appointment.doctor.name}* on "
        f"{_format_date(appointment.appointment_date)}.\n\n"
        "Rate your recovery (1 = Poor, 5 = Excellent):\n\n"
        "1️⃣ 😟 Very Poor\n"
        "2️⃣ 😕 Poor\n"
        "3️⃣ 😐 Okay\n"
        "4️⃣ 🙂 Good\n"
        "5️⃣ 😄 Excellent\n\n"
        "_Reply with a number (1-5)_"
    )


def _msg_followup_good():
    return (
        "😊 *Great to hear you're doing well!*\n\n"
        "Follow your doctor's advice and take your medications on time.\n\n"
        "💪 _Wishing you continued good health!_\n\n"
        "_Type MENU to return_"
    )


def _msg_followup_symptoms():
    return (
        "😟 *Sorry to hear that.*\n\n"
        "Please describe your symptoms briefly:\n\n"
        "_Type your symptoms and we'll alert your doctor_"
    )


def _msg_followup_escalated(appointment):
    return (
        "✅ *Your symptoms have been reported to "
        f"{appointment.doctor.name}.*\n\n"
        "The doctor's team will reach out to you shortly.\n\n"
        "🆘 *If urgent, please visit the hospital immediately.*\n\n"
        "_Type MENU to return_"
    )


def _msg_error(msg="Something went wrong. Type MENU to start over."):
    return f"⚠️ {msg}"


def _msg_cancel_success(booking_id):
    return (
        f"❌ *Appointment Cancelled*\n\n"
        f"Booking ID: *{booking_id}*\n\n"
        "_Type MENU to return to main menu_"
    )


# ─── State Machine Handler ───

def handle_message(phone, body):
    """
    Core conversation engine. Takes phone + message text,
    returns the bot's reply string.
    """
    session = _get_or_create_session(phone)
    patient = Patient.query.filter_by(phone=phone).first()
    inp = _normalize_input(body)
    ctx = session.get_context()

    # ── Global commands (work from any state) ──
    if inp in ("menu", "main", "home"):
        if session.state != STATE_START and session.state != STATE_MENU:
            session.clear_context()
            session.state = STATE_MENU
            db.session.commit()
            if not patient:
                session.state = STATE_REGISTER
                db.session.commit()
                return _msg_register()
            return _msg_welcome()

    if inp == "help":
        return _msg_help()

    # Handle CANCEL command from any state — only when it looks like CANCEL <BOOKING_ID>
    # Booking IDs follow pattern: NEL-YYMMDDHHMMSS-NNN (starts with NEL-)
    if inp == "cancel" or inp.startswith("cancel nel-"):
        parts = inp.split()
        if len(parts) == 2 and parts[1].upper().startswith("NEL-"):
            booking_id = parts[1].upper()
            return _handle_cancel(patient, booking_id)
        return "⚠️ Usage: CANCEL <Booking ID>\nExample: CANCEL NEL-250523093000-42"

    # ── State Machine ──

    if session.state == STATE_START:
        return _handle_start(session, patient, phone, body)

    elif session.state == STATE_REGISTER:
        return _handle_register(session, phone, body)

    elif session.state == STATE_MENU:
        return _handle_menu(session, patient, phone, inp)

    elif session.state == STATE_SELECT_SPEC:
        return _handle_select_spec(session, inp)

    elif session.state == STATE_SELECT_DOCTOR:
        return _handle_select_doctor(session, inp, ctx)

    elif session.state == STATE_HOSPITAL_INFO:
        return _handle_hospital_info(session, inp, ctx)

    elif session.state == STATE_SELECT_DATE:
        return _handle_select_date(session, inp, ctx)

    elif session.state == STATE_SELECT_TIME:
        return _handle_select_time(session, inp, ctx, patient)

    elif session.state == STATE_CONFIRM:
        return _handle_confirm(session, inp, ctx, patient)

    elif session.state == STATE_BOOKED:
        session.state = STATE_MENU
        db.session.commit()
        return _msg_welcome()

    elif session.state == STATE_MY_APPOINTMENTS:
        session.state = STATE_MENU
        db.session.commit()
        return _msg_welcome()

    elif session.state == STATE_FOLLOWUP_RATING:
        return _handle_followup_rating(session, inp, ctx)

    elif session.state == STATE_FOLLOWUP_SYMPTOMS:
        return _handle_followup_symptoms(session, body, ctx)

    # Fallback
    session.clear_context()
    session.state = STATE_MENU
    db.session.commit()
    return _msg_welcome()


def _handle_start(session, patient, phone, body):
    """First interaction — register if new, else show menu."""
    if not patient:
        session.state = STATE_REGISTER
        db.session.commit()
        return _msg_register()
    session.state = STATE_MENU
    db.session.commit()
    return _msg_welcome()


def _handle_register(session, phone, body):
    """Register new patient with their name."""
    name = body.strip()
    if len(name) < 2:
        return "📝 _Please enter a valid name (at least 2 characters)_"

    patient = _get_or_create_patient(phone, name)
    session.state = STATE_MENU
    db.session.commit()
    return (
        f"✅ *Welcome, {name}!*\n\n"
        "You're all set to book appointments.\n\n"
        + _msg_welcome()
    )


def _handle_menu(session, patient, phone, inp):
    """Handle main menu selection."""
    if not patient:
        session.state = STATE_REGISTER
        db.session.commit()
        return _msg_register()

    if inp == "1":
        session.state = STATE_SELECT_SPEC
        session.clear_context()
        session.state = STATE_SELECT_SPEC
        db.session.commit()
        return _msg_select_specialization()

    elif inp == "2":
        session.state = STATE_MY_APPOINTMENTS
        db.session.commit()
        return _msg_my_appointments(patient)

    elif inp == "3":
        return _msg_profile(patient)

    elif inp == "4":
        return _msg_help()

    else:
        return (
            "❓ _Please reply with a number 1-4_\n\n"
            + _msg_welcome()
        )


def _handle_select_spec(session, inp):
    """User selects a specialization."""
    if inp == "0":
        session.state = STATE_MENU
        db.session.commit()
        return _msg_welcome()

    specs = _get_available_specializations()
    try:
        idx = int(inp) - 1
        if 0 <= idx < len(specs):
            selected_spec = specs[idx][0]
            session.update_context(selected_specialization=selected_spec)
            session.state = STATE_SELECT_DOCTOR
            db.session.commit()
            return _msg_select_doctor(selected_spec)
    except (ValueError, IndexError):
        pass

    return (
        f"❓ _Invalid choice. Reply with a number 1-{len(specs)}_\n\n"
        + _msg_select_specialization()
    )


def _handle_select_doctor(session, inp, ctx):
    """User selects a doctor from the specialization list."""
    if inp == "0":
        session.state = STATE_SELECT_SPEC
        db.session.commit()
        return _msg_select_specialization()

    spec = ctx.get("selected_specialization")
    doctors = _get_doctors_by_spec(spec)

    try:
        idx = int(inp) - 1
        if 0 <= idx < len(doctors):
            doctor = doctors[idx]
            session.update_context(
                selected_doctor_id=doctor.id,
                selected_hospital=doctor.display_hospital,
            )
            session.state = STATE_HOSPITAL_INFO
            db.session.commit()
            return _msg_hospital_info(doctor)
    except (ValueError, IndexError):
        pass

    return (
        f"❓ _Invalid choice. Reply with a number 1-{len(doctors)}_\n\n"
        + _msg_select_doctor(spec)
    )


def _handle_hospital_info(session, inp, ctx):
    """After seeing hospital info, user proceeds to date selection."""
    if inp == "0":
        spec = ctx.get("selected_specialization")
        session.state = STATE_SELECT_DOCTOR
        db.session.commit()
        return _msg_select_doctor(spec)

    if inp in ("next", "yes", "ok", "proceed", "continue"):
        session.state = STATE_SELECT_DATE
        db.session.commit()
        return _msg_select_date()

    return (
        "❓ _Type NEXT to pick a date, or 0 to go back_"
    )


def _handle_select_date(session, inp, ctx):
    """User selects a date."""
    if inp == "0":
        doctor_id = ctx.get("selected_doctor_id")
        doctor = Doctor.query.get(doctor_id)
        session.state = STATE_HOSPITAL_INFO
        db.session.commit()
        return _msg_hospital_info(doctor)

    days = _get_next_weekdays(5)
    try:
        idx = int(inp) - 1
        if 0 <= idx < len(days):
            selected_date = days[idx].isoformat()
            session.update_context(selected_date=selected_date)
            session.state = STATE_SELECT_TIME
            db.session.commit()
            doctor = Doctor.query.get(ctx.get("selected_doctor_id"))
            return _msg_select_time(doctor)
    except (ValueError, IndexError):
        pass

    return (
        f"❓ _Invalid choice. Reply with a number 1-{len(days)}_\n\n"
        + _msg_select_date()
    )


def _handle_select_time(session, inp, ctx, patient):
    """User selects a time slot."""
    if inp == "0":
        session.state = STATE_SELECT_DATE
        db.session.commit()
        return _msg_select_date()

    slots = _get_time_slots()
    try:
        idx = int(inp) - 1
        if 0 <= idx < len(slots):
            selected_time = slots[idx].strftime("%H:%M")
            session.update_context(selected_time=selected_time)
            session.state = STATE_CONFIRM
            db.session.commit()

            doctor = Doctor.query.get(ctx.get("selected_doctor_id"))
            apt_date = date.fromisoformat(ctx.get("selected_date"))
            apt_time = dtime.fromisoformat(ctx.get("selected_time"))
            return _msg_confirm(doctor, apt_date, apt_time, patient)
    except (ValueError, IndexError):
        pass

    return (
        f"❓ _Invalid choice. Reply with a number 1-{len(slots)}_\n\n"
        + _msg_select_time(Doctor.query.get(ctx.get("selected_doctor_id")))
    )


def _handle_confirm(session, inp, ctx, patient):
    """User confirms or cancels the booking."""
    if inp in ("yes", "y", "confirm", "ok", "1"):
        doctor = Doctor.query.get(ctx.get("selected_doctor_id"))
        apt_date = date.fromisoformat(ctx.get("selected_date"))
        apt_time = dtime.fromisoformat(ctx.get("selected_time"))

        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=apt_date,
            appointment_time=apt_time,
            status=Appointment.STATUS_CONFIRMED,
            booking_id=Appointment.generate_booking_id(),
        )
        db.session.add(appointment)
        session.clear_context()
        session.state = STATE_BOOKED
        db.session.commit()
        return _msg_booking_confirmed(appointment)

    elif inp in ("no", "n", "cancel", "0"):
        session.clear_context()
        session.state = STATE_MENU
        db.session.commit()
        return "❌ _Booking cancelled._\n\n" + _msg_welcome()

    return (
        "❓ _Please reply *YES* to confirm or *NO* to cancel_"
    )


def _handle_cancel(patient, booking_id):
    """Cancel an appointment by booking ID."""
    if not patient:
        return "⚠️ You need to register first. Type MENU to start."

    appointment = Appointment.query.filter_by(
        booking_id=booking_id, patient_id=patient.id
    ).first()

    if not appointment:
        return f"⚠️ No appointment found with ID: *{booking_id}*"

    if appointment.status in (Appointment.STATUS_CANCELLED, Appointment.STATUS_COMPLETED):
        return f"⚠️ Appointment *{booking_id}* is already {appointment.status}."

    appointment.status = Appointment.STATUS_CANCELLED
    db.session.commit()
    return _msg_cancel_success(booking_id)


def _handle_followup_rating(session, inp, ctx):
    """Handle follow-up wellness rating (1-5)."""
    try:
        rating = int(inp)
        if 1 <= rating <= 5:
            appointment_id = ctx.get("followup_appointment_id")
            followup = FollowUp.query.filter_by(
                appointment_id=appointment_id
            ).first()
            if followup:
                followup.rating = rating
                followup.responded_at = datetime.utcnow()
                db.session.commit()

            if rating <= 2:
                session.state = STATE_FOLLOWUP_SYMPTOMS
                db.session.commit()
                return _msg_followup_symptoms()
            else:
                followup.status = FollowUp.STATUS_RESPONDED
                session.clear_context()
                session.state = STATE_MENU
                db.session.commit()
                return _msg_followup_good()
    except ValueError:
        pass

    return "❓ _Please reply with a number 1-5_"


def _handle_followup_symptoms(session, body, ctx):
    """Handle follow-up symptom description for low-rating patients."""
    appointment_id = ctx.get("followup_appointment_id")
    followup = FollowUp.query.filter_by(
        appointment_id=appointment_id
    ).first()
    appointment = Appointment.query.get(appointment_id)

    if followup:
        followup.symptoms = body.strip()
        followup.status = FollowUp.STATUS_ESCALATED
        followup.responded_at = datetime.utcnow()
        db.session.commit()

    session.clear_context()
    session.state = STATE_MENU
    db.session.commit()
    return _msg_followup_escalated(appointment)


# ─── Webhook Route ───

@whatsapp_bp.route("/whatsapp/webhook", methods=["POST"])
def webhook():
    """Twilio WhatsApp webhook endpoint."""
    from_phone = request.form.get("From", "")
    body = request.form.get("Body", "")

    # Extract phone number (strip whatsapp: prefix)
    phone = from_phone.replace("whatsapp:", "").strip()

    if not phone or not body:
        return "", 204

    current_app.logger.info(f"WhatsApp webhook: phone={phone}, body={body[:50]}")

    try:
        reply = handle_message(phone, body)
    except Exception as e:
        current_app.logger.error(f"Error handling message: {e}", exc_info=True)
        reply = _msg_error("Something went wrong. Type MENU to start over.")

    # Send reply via Twilio
    from .messaging import send_whatsapp_message
    send_whatsapp_message(phone, reply)

    return "", 204
