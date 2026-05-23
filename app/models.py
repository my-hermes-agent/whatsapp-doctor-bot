"""
WhatsApp Doctor Bot — SQLAlchemy Models
Nellore doctor appointment booking system
"""

from datetime import datetime, date, time
from app import db


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    specialization = db.Column(db.String(100), nullable=False, index=True)
    sub_specialization = db.Column(db.String(150), default="")
    hospital = db.Column(db.String(200), nullable=False, index=True)
    hospital_area = db.Column(db.String(100), default="Nellore")
    timings = db.Column(db.String(200), default="Contact hospital")
    experience = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointments = db.relationship("Appointment", backref="doctor", lazy="dynamic")

    @property
    def display_specialization(self):
        if self.sub_specialization:
            return f"{self.specialization} ({self.sub_specialization})"
        return self.specialization

    @property
    def display_hospital(self):
        if self.hospital_area and self.hospital_area != "Nellore":
            return f"{self.hospital}, {self.hospital_area}"
        return self.hospital

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "specialization": self.specialization,
            "sub_specialization": self.sub_specialization,
            "hospital": self.hospital,
            "hospital_area": self.hospital_area,
            "timings": self.timings,
            "experience": self.experience,
            "is_active": self.is_active,
        }


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointments = db.relationship("Appointment", backref="patient", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
        }


class Appointment(db.Model):
    __tablename__ = "appointments"

    STATUS_BOOKED = "booked"
    STATUS_CONFIRMED = "confirmed"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), default=STATUS_BOOKED, index=True)
    booking_id = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    follow_ups = db.relationship("FollowUp", backref="appointment", lazy="dynamic")

    @staticmethod
    def generate_booking_id():
        from datetime import datetime
        prefix = "NEL"
        ts = datetime.utcnow().strftime("%y%m%d%H%M%S")
        import random
        suffix = f"{random.randint(10, 99)}"
        return f"{prefix}-{ts}-{suffix}"

    @property
    def is_past(self):
        now = datetime.utcnow()
        appt_dt = datetime.combine(self.appointment_date, self.appointment_time)
        return appt_dt < now

    def to_dict(self):
        return {
            "id": self.id,
            "booking_id": self.booking_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient.name,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor.name,
            "doctor_specialization": self.doctor.display_specialization,
            "hospital": self.doctor.display_hospital,
            "appointment_date": self.appointment_date.isoformat(),
            "appointment_time": self.appointment_time.strftime("%I:%M %p"),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class FollowUp(db.Model):
    __tablename__ = "followups"

    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_RESPONDED = "responded"
    STATUS_ESCALATED = "escalated"

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=True)  # 1-5
    symptoms = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default=STATUS_PENDING, index=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "appointment_id": self.appointment_id,
            "rating": self.rating,
            "symptoms": self.symptoms,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
        }


class ConversationSession(db.Model):
    """Tracks multi-turn WhatsApp conversation state per patient."""
    __tablename__ = "conversation_sessions"

    id = db.Column(db.Integer, primary_key=True)
    patient_phone = db.Column(db.String(20), nullable=False, index=True)
    state = db.Column(db.String(50), nullable=False, default="start")
    # Context data stored as JSON string
    context = db.Column(db.Text, default="{}")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Context fields (accessed via JSON):
    #   selected_specialization: str
    #   selected_doctor_id: int
    #   selected_hospital: str
    #   selected_date: str (ISO date)
    #   selected_time: str (HH:MM)
    #   pending_booking_id: str
    #   followup_appointment_id: int

    def get_context(self):
        import json
        try:
            return json.loads(self.context) if self.context else {}
        except json.JSONDecodeError:
            return {}

    def set_context(self, data: dict):
        import json
        self.context = json.dumps(data)
        self.updated_at = datetime.utcnow()

    def update_context(self, **kwargs):
        ctx = self.get_context()
        ctx.update(kwargs)
        self.set_context(ctx)

    def clear_context(self):
        self.context = "{}"
        self.state = "start"
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        return {
            "id": self.id,
            "patient_phone": self.patient_phone,
            "state": self.state,
            "context": self.get_context(),
            "updated_at": self.updated_at.isoformat(),
        }
