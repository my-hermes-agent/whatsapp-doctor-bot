"""
WhatsApp Doctor Bot — REST API Endpoints
Full CRUD for doctors, patients, appointments, follow-ups, and dashboard stats.
"""

from datetime import datetime, date
from flask import Blueprint, request, jsonify
from app import db
from app.models import Doctor, Patient, Appointment, FollowUp

api_bp = Blueprint("api", __name__)


# ─── Doctors ───

@api_bp.route("/doctors", methods=["GET"])
def list_doctors():
    """List all active doctors, filterable by specialization and hospital."""
    query = Doctor.query.filter_by(is_active=True)

    spec = request.args.get("specialization")
    if spec:
        query = query.filter_by(specialization=spec)

    hospital = request.args.get("hospital")
    if hospital:
        query = query.filter_by(hospital=hospital)

    doctors = query.order_by(Doctor.specialization, Doctor.name).all()
    return jsonify([d.to_dict() for d in doctors])


@api_bp.route("/doctors", methods=["POST"])
def create_doctor():
    """Create a new doctor."""
    data = request.get_json()
    if not data or not data.get("name") or not data.get("specialization"):
        return jsonify({"error": "name and specialization are required"}), 400

    doctor = Doctor(
        name=data["name"],
        specialization=data["specialization"],
        sub_specialization=data.get("sub_specialization", ""),
        hospital=data.get("hospital", "Nellore"),
        hospital_area=data.get("hospital_area", "Nellore"),
        timings=data.get("timings", "Contact hospital"),
        experience=data.get("experience", 0),
        is_active=data.get("is_active", True),
    )
    db.session.add(doctor)
    db.session.commit()
    return jsonify(doctor.to_dict()), 201


@api_bp.route("/doctors/<int:doctor_id>", methods=["GET"])
def get_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    return jsonify(doctor.to_dict())


@api_bp.route("/specializations", methods=["GET"])
def list_specializations():
    """Get all distinct specializations with doctor counts."""
    results = db.session.query(
        Doctor.specialization,
        db.func.count(Doctor.id).label("count")
    ).filter_by(is_active=True).group_by(Doctor.specialization).order_by(Doctor.specialization).all()

    return jsonify([{"name": r.specialization, "doctor_count": r.count} for r in results])


@api_bp.route("/hospitals", methods=["GET"])
def list_hospitals():
    """Get all distinct hospitals with doctor counts."""
    results = db.session.query(
        Doctor.hospital,
        Doctor.hospital_area,
        db.func.count(Doctor.id).label("count")
    ).filter_by(is_active=True).group_by(
        Doctor.hospital, Doctor.hospital_area
    ).order_by(Doctor.hospital).all()

    return jsonify([{
        "name": r.hospital,
        "area": r.hospital_area,
        "doctor_count": r.count
    } for r in results])


# ─── Patients ───

@api_bp.route("/patients", methods=["GET"])
def list_patients():
    patients = Patient.query.order_by(Patient.created_at.desc()).all()
    return jsonify([p.to_dict() for p in patients])


@api_bp.route("/patients/<int:patient_id>", methods=["GET"])
def get_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return jsonify(patient.to_dict())


@api_bp.route("/patients/<int:patient_id>/history", methods=["GET"])
def patient_history(patient_id):
    """Get patient's full history: appointments + follow-ups."""
    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(
        Appointment.appointment_date.desc()
    ).all()

    return jsonify({
        "patient": patient.to_dict(),
        "appointments": [a.to_dict() for a in appointments],
    })


# ─── Appointments ───

@api_bp.route("/appointments", methods=["GET"])
def list_appointments():
    query = Appointment.query

    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)

    patient_id = request.args.get("patient_id")
    if patient_id:
        query = query.filter_by(patient_id=int(patient_id))

    doctor_id = request.args.get("doctor_id")
    if doctor_id:
        query = query.filter_by(doctor_id=int(doctor_id))

    date_filter = request.args.get("date")
    if date_filter:
        query = query.filter_by(appointment_date=date.fromisoformat(date_filter))

    appointments = query.order_by(
        Appointment.appointment_date, Appointment.appointment_time
    ).all()
    return jsonify([a.to_dict() for a in appointments])


@api_bp.route("/appointments", methods=["POST"])
def create_appointment():
    data = request.get_json()
    required = ["patient_id", "doctor_id", "date", "time"]
    if not data or not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}"}), 400

    appointment = Appointment(
        patient_id=data["patient_id"],
        doctor_id=data["doctor_id"],
        appointment_date=date.fromisoformat(data["date"]),
        appointment_time=datetime.strptime(data["time"], "%H:%M").time(),
        status=Appointment.STATUS_CONFIRMED,
        booking_id=Appointment.generate_booking_id(),
    )
    db.session.add(appointment)
    db.session.commit()
    return jsonify(appointment.to_dict()), 201


@api_bp.route("/appointments/<int:appointment_id>", methods=["PATCH"])
def update_appointment(appointment_id):
    """Update appointment status. Completing auto-creates a follow-up."""
    appointment = Appointment.query.get_or_404(appointment_id)
    data = request.get_json()

    new_status = data.get("status")
    if new_status not in (
        Appointment.STATUS_BOOKED, Appointment.STATUS_CONFIRMED,
        Appointment.STATUS_COMPLETED, Appointment.STATUS_CANCELLED,
        Appointment.STATUS_NO_SHOW,
    ):
        return jsonify({"error": f"Invalid status: {new_status}"}), 400

    old_status = appointment.status
    appointment.status = new_status

    # Auto-create follow-up when appointment is completed
    if new_status == Appointment.STATUS_COMPLETED and old_status != Appointment.STATUS_COMPLETED:
        followup = FollowUp(
            appointment_id=appointment.id,
            status=FollowUp.STATUS_PENDING,
        )
        db.session.add(followup)

    db.session.commit()
    return jsonify(appointment.to_dict())


@api_bp.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    appointment.status = Appointment.STATUS_CANCELLED
    db.session.commit()
    return jsonify(appointment.to_dict())


# ─── Follow-ups ───

@api_bp.route("/followups", methods=["GET"])
def list_followups():
    query = FollowUp.query

    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)

    followups = query.order_by(FollowUp.created_at.desc()).all()
    return jsonify([f.to_dict() for f in followups])


@api_bp.route("/followups/send/<int:appointment_id>", methods=["POST"])
def send_followup(appointment_id):
    """Manually trigger a follow-up message for an appointment."""
    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.status != Appointment.STATUS_COMPLETED:
        return jsonify({"error": "Can only follow up on completed appointments"}), 400

    followup = FollowUp.query.filter_by(appointment_id=appointment_id).first()
    if not followup:
        followup = FollowUp(appointment_id=appointment_id, status=FollowUp.STATUS_PENDING)
        db.session.add(followup)
        db.session.commit()

    from .messaging import send_followup_message
    result = send_followup_message(appointment)
    followup.status = FollowUp.STATUS_SENT
    followup.sent_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"followup": followup.to_dict(), "send_result": result})


# ─── Dashboard Stats ───

@api_bp.route("/stats", methods=["GET"])
def dashboard_stats():
    total_doctors = Doctor.query.filter_by(is_active=True).count()
    total_patients = Patient.query.count()
    total_appointments = Appointment.query.count()
    upcoming = Appointment.query.filter(
        Appointment.status.in_([Appointment.STATUS_BOOKED, Appointment.STATUS_CONFIRMED]),
        Appointment.appointment_date >= date.today(),
    ).count()
    completed = Appointment.query.filter_by(status=Appointment.STATUS_COMPLETED).count()
    cancelled = Appointment.query.filter_by(status=Appointment.STATUS_CANCELLED).count()
    pending_followups = FollowUp.query.filter_by(status=FollowUp.STATUS_PENDING).count()
    escalated = FollowUp.query.filter_by(status=FollowUp.STATUS_ESCALATED).count()

    specs = db.session.query(
        Doctor.specialization, db.func.count(Doctor.id)
    ).filter_by(is_active=True).group_by(Doctor.specialization).order_by(
        db.func.count(Doctor.id).desc()
    ).limit(10).all()

    return jsonify({
        "doctors": total_doctors,
        "patients": total_patients,
        "appointments": {
            "total": total_appointments,
            "upcoming": upcoming,
            "completed": completed,
            "cancelled": cancelled,
        },
        "followups": {
            "pending": pending_followups,
            "escalated": escalated,
        },
        "top_specializations": [{"name": s, "count": c} for s, c in specs],
    })
