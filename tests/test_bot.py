"""
WhatsApp Doctor Bot — Comprehensive Test Suite
Tests all conversation flows, API endpoints, and edge cases.
"""

import os
import json
import pytest
from datetime import date, time, timedelta
from app import create_app, db as _db
from app.models import Doctor, Patient, Appointment, FollowUp, ConversationSession


# ─── Fixtures ───

@pytest.fixture
def app():
    """Create test app with in-memory SQLite."""
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",  # in-memory
        "TWILIO_ACCOUNT_SID": "test_sid",
        "TWILIO_API_KEY_SID": "test_key",
        "TWILIO_API_KEY_SECRET": "test_secret",
        "TWILIO_WHATSAPP_NUMBER": "whatsapp:+14155238886",
        "BASE_URL": "http://localhost:5000",
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    }
    os.environ["TWILIO_DEV_MODE"] = "1"
    app = create_app(test_config)
    with app.app_context():
        _db.create_all()
        _seed_test_data()
        yield app
        _db.session.remove()
        _db.drop_all()
    os.environ.pop("TWILIO_DEV_MODE", None)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_phone():
    return "+919876543210"


def _seed_test_data():
    """Seed minimal test doctors."""
    doctors = [
        Doctor(name="Dr. Test Cardiologist", specialization="Cardiology",
               sub_specialization="Interventional", hospital="Medicover Hospitals",
               hospital_area="Chintareddypalem", timings="Mon-Sat 9:00 AM - 5:00 PM",
               experience=15, is_active=True),
        Doctor(name="Dr. Test Ortho", specialization="Orthopaedics",
               sub_specialization="Joint Replacement", hospital="Apollo Specialty Hospital",
               hospital_area="Ramji Nagar", timings="Mon-Sat 9:00 AM - 4:00 PM",
               experience=20, is_active=True),
        Doctor(name="Dr. Test Neuro", specialization="Neurology",
               sub_specialization="", hospital="KIMS Hospital",
               hospital_area="Ambedkar Nagar", timings="Mon-Sat 9:00 AM - 5:00 PM",
               experience=10, is_active=True),
        Doctor(name="Dr. Test Gynae", specialization="Gynaecology",
               sub_specialization="Obstetrics", hospital="Medicover Hospitals",
               hospital_area="Chintareddypalem", timings="Mon-Sat 9:00 AM - 5:00 PM",
               experience=12, is_active=True),
    ]
    for d in doctors:
        _db.session.add(d)
    _db.session.commit()


def _send_whatsapp(client, phone, body):
    """Simulate an incoming WhatsApp message."""
    return client.post("/whatsapp/webhook", data={
        "From": f"whatsapp:{phone}",
        "Body": body,
    })


def _get_last_reply(client, phone):
    """Get the last message sent to a phone (from conversation state)."""
    session = ConversationSession.query.filter_by(patient_phone=phone).first()
    return session


# ─── Health & API Tests ───

class TestHealthCheck:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


class TestDoctorAPI:
    def test_list_doctors(self, client):
        resp = client.get("/api/doctors")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 4

    def test_filter_by_specialization(self, client):
        resp = client.get("/api/doctors?specialization=Cardiology")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["specialization"] == "Cardiology"

    def test_list_specializations(self, client):
        resp = client.get("/api/specializations")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 3
        specs = [s["name"] for s in data]
        assert "Cardiology" in specs

    def test_list_hospitals(self, client):
        resp = client.get("/api/hospitals")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 2

    def test_create_doctor(self, client):
        resp = client.post("/api/doctors", json={
            "name": "Dr. New Doc",
            "specialization": "Dermatology",
            "hospital": "New Hospital",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Dr. New Doc"
        assert data["specialization"] == "Dermatology"

    def test_create_doctor_missing_fields(self, client):
        resp = client.post("/api/doctors", json={"name": "No Spec"})
        assert resp.status_code == 400


class TestAppointmentAPI:
    def test_create_and_list_appointments(self, client, app):
        patient = Patient(phone="+919999999999", name="Test Patient")
        _db.session.add(patient)
        _db.session.commit()

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        resp = client.post("/api/appointments", json={
            "patient_id": patient.id,
            "doctor_id": 1,
            "date": tomorrow,
            "time": "09:30",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert "booking_id" in data
        assert data["status"] == "confirmed"

    def test_cancel_appointment(self, client, app):
        patient = Patient(phone="+918888888888", name="Cancel Patient")
        _db.session.add(patient)
        _db.session.commit()

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        resp = client.post("/api/appointments", json={
            "patient_id": patient.id,
            "doctor_id": 1,
            "date": tomorrow,
            "time": "10:00",
        })
        data = resp.get_json()
        apt_id = data["id"]

        cancel_resp = client.post(f"/api/appointments/{apt_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.get_json()["status"] == "cancelled"

    def test_complete_creates_followup(self, client, app):
        patient = Patient(phone="+917777777777", name="Followup Patient")
        _db.session.add(patient)
        _db.session.commit()

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        resp = client.post("/api/appointments", json={
            "patient_id": patient.id,
            "doctor_id": 2,
            "date": tomorrow,
            "time": "11:00",
        })
        apt_id = resp.get_json()["id"]

        patch_resp = client.patch(f"/api/appointments/{apt_id}", json={
            "status": "completed",
        })
        assert patch_resp.status_code == 200

        followups = FollowUp.query.filter_by(appointment_id=apt_id).all()
        assert len(followups) == 1
        assert followups[0].status == "pending"


class TestPatientAPI:
    def test_list_patients(self, client, app):
        patient = Patient(phone="+916666666666", name="List Patient")
        _db.session.add(patient)
        _db.session.commit()

        resp = client.get("/api/patients")
        assert resp.status_code == 200
        assert len(resp.get_json()) >= 1

    def test_patient_history(self, client, app):
        patient = Patient(phone="+915555555555", name="History Patient")
        _db.session.add(patient)
        _db.session.commit()

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        client.post("/api/appointments", json={
            "patient_id": patient.id,
            "doctor_id": 1,
            "date": tomorrow,
            "time": "09:00",
        })

        resp = client.get(f"/api/patients/{patient.id}/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["patient"]["name"] == "History Patient"
        assert len(data["appointments"]) >= 1


class TestStatsAPI:
    def test_dashboard_stats(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "doctors" in data
        assert "appointments" in data
        assert data["doctors"] == 4


# ─── Conversation Flow Tests ───

class TestConversationFlows:
    """Test the WhatsApp conversation state machine end-to-end."""

    def test_new_user_registration(self, client, app, test_phone):
        """New user sends Hi → gets registration prompt → registers → sees menu."""
        _send_whatsapp(client, test_phone, "Hi")

        session = ConversationSession.query.filter_by(patient_phone=test_phone).first()
        assert session is not None
        assert session.state == "register"

        _send_whatsapp(client, test_phone, "John Doe")
        patient = Patient.query.filter_by(phone=test_phone).first()
        assert patient is not None
        assert patient.name == "John Doe"

    def test_full_booking_flow(self, client, app, test_phone):
        """Complete flow: Hi → Register → Menu → Spec → Doctor → Hospital → Date → Time → Confirm."""
        # Step 1: Register
        _send_whatsapp(client, test_phone, "Hi")
        _send_whatsapp(client, test_phone, "Jane Smith")

        # Step 2: Select "Book Appointment" (1)
        _send_whatsapp(client, test_phone, "1")

        session = ConversationSession.query.filter_by(patient_phone=test_phone).first()
        assert session.state == "select_specialization"

        # Step 3: Select Cardiology (1)
        _send_whatsapp(client, test_phone, "1")
        ctx = session.get_context()
        assert ctx.get("selected_specialization") == "Cardiology"
        assert session.state == "select_doctor"

        # Step 4: Select first doctor (1)
        _send_whatsapp(client, test_phone, "1")
        ctx = session.get_context()
        assert "selected_doctor_id" in ctx
        assert session.state == "hospital_info"

        # Step 5: Proceed to date
        _send_whatsapp(client, test_phone, "next")
        assert session.state == "select_date"

        # Step 6: Select date (1)
        _send_whatsapp(client, test_phone, "1")
        ctx = session.get_context()
        assert "selected_date" in ctx
        assert session.state == "select_time"

        # Step 7: Select time (1 = 9:00 AM)
        _send_whatsapp(client, test_phone, "1")
        ctx = session.get_context()
        assert "selected_time" in ctx
        assert session.state == "confirm_booking"

        # Step 8: Confirm YES
        _send_whatsapp(client, test_phone, "yes")
        assert session.state == "booked"

        # Verify appointment created
        patient = Patient.query.filter_by(phone=test_phone).first()
        appointments = Appointment.query.filter_by(patient_id=patient.id).all()
        assert len(appointments) == 1
        assert appointments[0].status == "confirmed"
        assert appointments[0].booking_id.startswith("NEL-")

    def test_booking_declined(self, client, app, test_phone):
        """User says NO at confirmation → booking cancelled, returns to menu."""
        # Quick register + flow to confirm
        _send_whatsapp(client, test_phone, "Hi")
        _send_whatsapp(client, test_phone, "Decline User")
        _send_whatsapp(client, test_phone, "1")  # Book
        _send_whatsapp(client, test_phone, "2")  # Ortho
        _send_whatsapp(client, test_phone, "1")  # Doctor
        _send_whatsapp(client, test_phone, "next")  # Hospital
        _send_whatsapp(client, test_phone, "1")  # Date
        _send_whatsapp(client, test_phone, "3")  # Time
        _send_whatsapp(client, test_phone, "no")  # Decline

        session = ConversationSession.query.filter_by(patient_phone=test_phone).first()
        assert session.state == "menu"

    def test_my_appointments(self, client, app, test_phone):
        """Menu option 2 shows upcoming appointments."""
        # Register + book first
        _send_whatsapp(client, test_phone, "Hi")
        _send_whatsapp(client, test_phone, "Apt User")
        _send_whatsapp(client, test_phone, "1")  # Book
        _send_whatsapp(client, test_phone, "1")  # Cardiology
        _send_whatsapp(client, test_phone, "1")  # Doctor
        _send_whatsapp(client, test_phone, "next")
        _send_whatsapp(client, test_phone, "1")
        _send_whatsapp(client, test_phone, "1")
        _send_whatsapp(client, test_phone, "yes")

        # Now check appointments
        _send_whatsapp(client, test_phone, "menu")
        _send_whatsapp(client, test_phone, "2")

        session = ConversationSession.query.filter_by(patient_phone=test_phone).first()
        assert session.state == "my_appointments"

    def test_cancel_command(self, client, app, test_phone):
        """CANCEL <booking_id> cancels an appointment."""
        # Register + book (flow: Hi → Name → 1=Book → 1=Spec → 1=Doctor → next → 1=Date → 1=Time → yes)
        _send_whatsapp(client, test_phone, "Hi")
        _send_whatsapp(client, test_phone, "Cancel User")
        _send_whatsapp(client, test_phone, "1")  # Book appointment
        _send_whatsapp(client, test_phone, "1")  # Select specialization
        _send_whatsapp(client, test_phone, "1")  # Select doctor
        _send_whatsapp(client, test_phone, "next")  # Hospital info → proceed
        _send_whatsapp(client, test_phone, "1")  # Select date
        _send_whatsapp(client, test_phone, "1")  # Select time
        _send_whatsapp(client, test_phone, "yes")  # Confirm

        patient = Patient.query.filter_by(phone=test_phone).first()
        assert patient is not None, "Patient should exist after registration"
        apt = Appointment.query.filter_by(patient_id=patient.id).first()
        assert apt is not None, "Appointment should exist after booking flow"
        booking_id = apt.booking_id

        # Cancel
        _send_whatsapp(client, test_phone, f"CANCEL {booking_id}")
        _db.session.refresh(apt)
        assert apt.status == "cancelled"

    def test_go_back_from_doctor_to_spec(self, client, app, test_phone):
        """Type 0 from doctor selection → back to specialization."""
        _send_whatsapp(client, test_phone, "Hi")
        _send_whatsapp(client, test_phone, "Back User")
        _send_whatsapp(client, test_phone, "1")  # Book
        _send_whatsapp(client, test_phone, "1")  # Spec

        # Go back — "0" from doctor selection returns to specialization
        _send_whatsapp(client, test_phone, "0")
        session = ConversationSession.query.filter_by(patient_phone=test_phone).first()
        assert session.state == "select_specialization"

    def test_help_command(self, client, app, test_phone):
        """HELP works from any state."""
        _send_whatsapp(client, test_phone, "Hi")
        _send_whatsapp(client, test_phone, "Help User")
        _send_whatsapp(client, test_phone, "1")  # Enter booking flow
        _send_whatsapp(client, test_phone, "help")  # Should show help

        session = ConversationSession.query.filter_by(patient_phone=test_phone).first()
        # Help doesn't change state, returns to current flow
        assert session.state == "select_specialization"

    def test_profile(self, client, app, test_phone):
        """Menu option 3 shows patient profile."""
        _send_whatsapp(client, test_phone, "Hi")
        _send_whatsapp(client, test_phone, "Profile User")
        _send_whatsapp(client, test_phone, "3")  # Profile

        # Should stay in menu state (profile is a view-only action)
        session = ConversationSession.query.filter_by(patient_phone=test_phone).first()
        assert session.state == "menu"

    def test_followup_low_rating_escalation(self, client, app, test_phone):
        """Follow-up: rating 1-2 → ask symptoms → escalate."""
        # Setup: create patient + completed appointment + follow-up
        patient = Patient(phone=test_phone, name="Followup Test")
        _db.session.add(patient)
        _db.session.commit()

        apt = Appointment(
            patient_id=patient.id, doctor_id=1,
            appointment_date=date.today(), appointment_time=time(9, 0),
            status=Appointment.STATUS_COMPLETED,
            booking_id=Appointment.generate_booking_id(),
        )
        _db.session.add(apt)
        _db.session.commit()

        fu = FollowUp(appointment_id=apt.id, status=FollowUp.STATUS_PENDING)
        _db.session.add(fu)
        _db.session.commit()

        # Set session to follow-up state
        session = ConversationSession(
            patient_phone=test_phone,
            state="followup_rating",
            context=json.dumps({"followup_appointment_id": apt.id}),
        )
        _db.session.add(session)
        _db.session.commit()

        # Rate 1 (poor)
        _send_whatsapp(client, test_phone, "1")
        assert session.state == "followup_symptoms"

        # Describe symptoms
        _send_whatsapp(client, test_phone, "Severe headache and dizziness")
        _db.session.refresh(fu)
        assert fu.status == "escalated"
        assert fu.symptoms == "Severe headache and dizziness"

    def test_followup_good_rating(self, client, app, test_phone):
        """Follow-up: rating 4-5 → good health message."""
        # Use a different phone to avoid conflicts
        phone2 = "+919999999991"
        patient = Patient(phone=phone2, name="Good Followup")
        _db.session.add(patient)
        _db.session.commit()

        apt = Appointment(
            patient_id=patient.id, doctor_id=2,
            appointment_date=date.today(), appointment_time=time(10, 0),
            status=Appointment.STATUS_COMPLETED,
            booking_id=Appointment.generate_booking_id(),
        )
        _db.session.add(apt)
        _db.session.commit()

        fu = FollowUp(appointment_id=apt.id, status=FollowUp.STATUS_PENDING)
        _db.session.add(fu)

        session = ConversationSession(
            patient_phone=phone2,
            state="followup_rating",
            context=json.dumps({"followup_appointment_id": apt.id}),
        )
        _db.session.add(session)
        _db.session.commit()

        _send_whatsapp(client, phone2, "5")
        _db.session.refresh(fu)
        assert fu.status == "responded"
        assert fu.rating == 5


class TestEdgeCases:
    def test_empty_message(self, client):
        resp = client.post("/whatsapp/webhook", data={"From": "whatsapp:+1", "Body": ""})
        assert resp.status_code == 204

    def test_invalid_input_in_menu(self, client, app, test_phone):
        """Invalid number in menu → error prompt."""
        _send_whatsapp(client, test_phone, "Hi")
        _send_whatsapp(client, test_phone, "Edge User")
        _send_whatsapp(client, test_phone, "99")  # Invalid

        session = ConversationSession.query.filter_by(patient_phone=test_phone).first()
        assert session.state == "menu"  # Stays in menu

    def test_invalid_spec_number(self, client, app, test_phone):
        """Invalid number in spec selection → error prompt."""
        _send_whatsapp(client, test_phone, "Hi")
        _send_whatsapp(client, test_phone, "Edge Spec")
        _send_whatsapp(client, test_phone, "1")
        _send_whatsapp(client, test_phone, "999")

        session = ConversationSession.query.filter_by(patient_phone=test_phone).first()
        assert session.state == "select_specialization"  # Stays

    def test_booking_id_format(self, app):
        """Verify booking ID generation format."""
        bid = Appointment.generate_booking_id()
        assert bid.startswith("NEL-")
        parts = bid.split("-")
        assert len(parts) == 3

    def test_inactive_doctors_excluded(self, client, app):
        """Inactive doctors should not appear in lists."""
        doc = Doctor.query.first()
        doc.is_active = False
        _db.session.commit()

        resp = client.get("/api/doctors")
        data = resp.get_json()
        assert len(data) == 3  # Was 4, now 3
