"""
WhatsApp Doctor Bot — Flask Application Factory
Nellore Doctor Appointment Booking via WhatsApp
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    # Core config
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", os.getenv("FLASK_SECRET_KEY", "dev-key-change-in-prod")),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///doctorbot.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TWILIO_ACCOUNT_SID=os.getenv("TWILIO_ACCOUNT_SID"),
        TWILIO_API_KEY_SID=os.getenv("TWILIO_API_KEY_SID"),
        TWILIO_API_KEY_SECRET=os.getenv("TWILIO_API_KEY_SECRET"),
        TWILIO_WHATSAPP_NUMBER=os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886"),
        BASE_URL=os.getenv("BASE_URL", "http://localhost:5000"),
        FOLLOWUP_DELAY_HOURS=int(os.getenv("FOLLOWUP_DELAY_HOURS", "24")),
    )

    if test_config:
        app.config.update(test_config)

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Init extensions
    db.init_app(app)

    # Register blueprints
    from .whatsapp import whatsapp_bp
    from .api import api_bp

    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Health check
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "nellore-doctor-bot"}

    # CLI commands
    from .models import Doctor, Patient, Appointment, FollowUp, ConversationSession

    @app.cli.command("init-db")
    def init_db():
        """Create tables and seed Nellore doctor data."""
        db.create_all()
        _seed_doctors(app)
        print("✅ Database initialized with Nellore doctor data.")

    with app.app_context():
        db.create_all()

    return app


def _seed_doctors(app):
    """Seed the database with real Nellore doctors from the spreadsheet."""
    from .models import Doctor

    if Doctor.query.first():
        return  # Already seeded

    doctors_data = [
        # ── MEDICOVER HOSPITALS, Chintareddypalem ──
        {"name": "Dr. K. Sasidhar Reddy", "specialization": "Orthopaedics", "sub_specialization": "Joint Replacement Surgery", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 23, "is_active": True},
        {"name": "Dr. Mekala Venkata Sudhakar", "specialization": "Orthopaedics", "sub_specialization": "Arthroscopy & Sports Medicine", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 15, "is_active": True},
        {"name": "Dr. M C Vinod Kumar Reddy", "specialization": "Orthopaedics", "sub_specialization": "", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 10, "is_active": True},
        {"name": "Dr. Balakrishna Malepati", "specialization": "Cardiology", "sub_specialization": "Interventional", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 13, "is_active": True},
        {"name": "Dr. Jayaram M", "specialization": "Cardiology", "sub_specialization": "Consultant", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 13, "is_active": True},
        {"name": "Dr. P. Deekshanti Narayan", "specialization": "Neurology", "sub_specialization": "", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 24, "is_active": True},
        {"name": "Dr. Vaishnavi A", "specialization": "Neurology", "sub_specialization": "Neuro Physician", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 4, "is_active": True},
        {"name": "Dr. Gangapatnam Dinesh", "specialization": "Neurosurgery", "sub_specialization": "Brain & Spine", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 8, "is_active": True},
        {"name": "Dr. G. Vara Prasada Rao", "specialization": "Gastroenterology", "sub_specialization": "Surgical / General Surgery", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 32, "is_active": True},
        {"name": "Dr. Krothapalli Sai Krishna", "specialization": "Gastroenterology", "sub_specialization": "Hepatology", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 4, "is_active": True},
        {"name": "Dr. Nitesh Pagadala", "specialization": "Gastroenterology", "sub_specialization": "HPB & GI Cancer Surgery", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 10, "is_active": True},
        {"name": "Dr. Gundala Venkata Kishore", "specialization": "General Surgery", "sub_specialization": "Laparoscopic & Laser Proctology", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 11, "is_active": True},
        {"name": "Dr. Kousik Amancharla", "specialization": "Urology", "sub_specialization": "Uro Oncology & Robotic Surgery", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 15, "is_active": True},
        {"name": "Dr. G. Gokul Nachiketh", "specialization": "Urology", "sub_specialization": "", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 8, "is_active": True},
        {"name": "Dr. Udaya Keerthi Kanna", "specialization": "Pediatrics", "sub_specialization": "Pediatric Intensive Care", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 15, "is_active": True},
        {"name": "Dr. Seepana Rajesh", "specialization": "Pediatrics", "sub_specialization": "", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 10, "is_active": True},
        {"name": "Dr. K. Sindhu Reddy", "specialization": "Gynaecology", "sub_specialization": "Obstetrics", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 12, "is_active": True},
        {"name": "Dr. Kolakalapudi Sindhu Bala", "specialization": "Gynaecology", "sub_specialization": "Obstetrics", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 10, "is_active": True},
        {"name": "Dr. Anusha Mannem", "specialization": "Gynaecology", "sub_specialization": "Obstetrics", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:30 AM - 4:00 PM", "experience": 13, "is_active": True},
        {"name": "Dr. Vuppu Sita Lakshmi", "specialization": "Gynaecology", "sub_specialization": "Obstetrics", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 10, "is_active": True},
        {"name": "Dr. S. Gayatri", "specialization": "Endocrinology", "sub_specialization": "", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 8, "is_active": True},
        {"name": "Dr. G. Ranga Raman", "specialization": "Oncology", "sub_specialization": "Haematology & Medical Oncology", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 12, "is_active": True},
        {"name": "Dr. Pinniboyana Vijaya Kumar", "specialization": "General Medicine", "sub_specialization": "Diabetology", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 26, "is_active": True},
        {"name": "Dr. Ponugoti Munilakshmi", "specialization": "Microbiology", "sub_specialization": "", "hospital": "Medicover Hospitals", "hospital_area": "Chintareddypalem", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 13, "is_active": True},

        # ── APOLLO SPECIALTY HOSPITAL, Ramji Nagar ──
        {"name": "Dr. Bindu Menon", "specialization": "Neurology", "sub_specialization": "HOD", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 31, "is_active": True},
        {"name": "Dr. Chirra Bhakthavatsala Reddy", "specialization": "Cardiology", "sub_specialization": "", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 14, "is_active": True},
        {"name": "Dr. C. Vivekananda Reddy", "specialization": "Orthopaedics", "sub_specialization": "", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 12, "is_active": True},
        {"name": "Dr. Sreeram Sateesh", "specialization": "General Surgery", "sub_specialization": "Laparoscopic", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 18, "is_active": True},
        {"name": "Dr. Raja Sekhar K", "specialization": "General Surgery", "sub_specialization": "Laparoscopic", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 13, "is_active": True},
        {"name": "Dr. Dinesh Reddy Anapalli", "specialization": "General Medicine", "sub_specialization": "Internal Medicine", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 8, "is_active": True},
        {"name": "Dr. M. C. S. Reddy", "specialization": "General Medicine", "sub_specialization": "Internal Medicine", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 9, "is_active": True},
        {"name": "Dr. Anitha Choppavarapu", "specialization": "General Medicine", "sub_specialization": "Family Medicine", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 20, "is_active": True},
        {"name": "Dr. M. Srinivas", "specialization": "General Medicine", "sub_specialization": "Emergency Medicine", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 6, "is_active": True},
        {"name": "Dr. U. V. Rohini", "specialization": "Gynaecology", "sub_specialization": "Obstetrics", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 15, "is_active": True},
        {"name": "Dr. Lavanya S", "specialization": "Gynaecology", "sub_specialization": "Obstetrics", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 12, "is_active": True},
        {"name": "Dr. Gowrinath K", "specialization": "Pulmonology", "sub_specialization": "Respiratory Medicine", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 42, "is_active": True},
        {"name": "Dr. Kishore", "specialization": "Dermatology", "sub_specialization": "", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 10, "is_active": True},
        {"name": "Dr. Rupa Akurati", "specialization": "Pediatrics", "sub_specialization": "", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 12, "is_active": True},
        {"name": "Dr. Dilip Gopalakrishnan", "specialization": "Cardiology", "sub_specialization": "Cardiac Sciences", "hospital": "Apollo Specialty Hospital", "hospital_area": "Ramji Nagar", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 15, "is_active": True},

        # ── KIMS HOSPITAL, Ambedkar Nagar ──
        {"name": "Dr. D. Saheb Peer", "specialization": "Cardiology", "sub_specialization": "Interventional", "hospital": "KIMS Hospital", "hospital_area": "Ambedkar Nagar", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 17, "is_active": True},
        {"name": "Dr. K. Bala Kondaiah", "specialization": "Orthopaedics", "sub_specialization": "Trauma", "hospital": "KIMS Hospital", "hospital_area": "Ambedkar Nagar", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 15, "is_active": True},

        # ── ENEL HOSPITAL, Magunta Layout ──
        {"name": "Dr. Nagendra Prasad Kulari", "specialization": "Cardiology", "sub_specialization": "Interventional", "hospital": "Enel Hospital", "hospital_area": "Magunta Layout", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 15, "is_active": True},
        {"name": "Dr. P. Haritha Kumari", "specialization": "Neurology", "sub_specialization": "", "hospital": "Enel Hospital", "hospital_area": "Magunta Layout", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 10, "is_active": True},
        {"name": "Dr. Girimahesh Yadav", "specialization": "Orthopaedics", "sub_specialization": "", "hospital": "Enel Hospital", "hospital_area": "Magunta Layout", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 8, "is_active": True},
        {"name": "Dr. Gowrinath K", "specialization": "Pulmonology", "sub_specialization": "Respiratory Medicine", "hospital": "Enel Hospital", "hospital_area": "Magunta Layout", "timings": "Mon-Sat 2:00 PM - 5:00 PM", "experience": 42, "is_active": True},

        # ── SHINE SUPERSPECIALITY HOSPITAL ──
        {"name": "Dr. K. V. Kishore Babu", "specialization": "Rheumatology", "sub_specialization": "", "hospital": "Shine Superspeciality Hospital", "hospital_area": "Nellore", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 11, "is_active": True},

        # ── INDEPENDENT / MULTI-HOSPITAL ──
        {"name": "Dr. C. N. Raju", "specialization": "Orthopaedics", "sub_specialization": "Arthroplasty & Spine Surgery", "hospital": "Multi-Hospital Practice", "hospital_area": "Nellore", "timings": "Mon-Sat 9:00 AM - 1:00 PM, 4:00 PM - 8:00 PM", "experience": 20, "is_active": True},
        {"name": "Dr. B. L. S. Kumar Babu", "specialization": "General Medicine", "sub_specialization": "", "hospital": "Independent Clinic", "hospital_area": "Nellore", "timings": "Mon-Sat 9:30 AM - 2:00 PM, 4:30 PM - 8:30 PM", "experience": 15, "is_active": True},
        {"name": "Dr. C. Vijay Amarnath Reddy", "specialization": "General Medicine", "sub_specialization": "Internal Medicine", "hospital": "Independent Clinic", "hospital_area": "Nellore", "timings": "Mon-Sat 9:00 AM - 1:00 PM, 5:00 PM - 9:00 PM", "experience": 12, "is_active": True},
        {"name": "Dr. Ravindra Reddy Sidhu", "specialization": "Orthopaedics", "sub_specialization": "", "hospital": "Multi-Hospital Practice", "hospital_area": "Nellore", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 15, "is_active": True},
        {"name": "Dr. Sravan Kumar B", "specialization": "General Medicine", "sub_specialization": "", "hospital": "Independent Clinic", "hospital_area": "Nellore", "timings": "Mon-Sat 9:30 AM - 2:00 PM, 4:30 PM - 8:30 PM", "experience": 10, "is_active": True},
        {"name": "Dr. Haritha Medabalimi", "specialization": "Gynaecology", "sub_specialization": "Obstetrics", "hospital": "Independent Clinic", "hospital_area": "Nellore", "timings": "Mon-Sat 9:00 AM - 1:00 PM, 5:00 PM - 8:00 PM", "experience": 10, "is_active": True},
        {"name": "Dr. Ramadevi P", "specialization": "Gynaecology", "sub_specialization": "Obstetrics", "hospital": "Independent Clinic", "hospital_area": "Nellore", "timings": "Mon-Sat 10:00 AM - 1:00 PM, 5:00 PM - 8:00 PM", "experience": 15, "is_active": True},
        {"name": "Dr. Sailesh G. J.", "specialization": "Orthopaedics", "sub_specialization": "", "hospital": "KBR Orthopedic Hospital", "hospital_area": "Pogathota", "timings": "Mon-Sat 9:00 AM - 1:00 PM, 5:00 PM - 8:30 PM", "experience": 14, "is_active": True},
        {"name": "Dr. Amrutha Nagisetty", "specialization": "Orthopaedics", "sub_specialization": "", "hospital": "Independent Clinic", "hospital_area": "Nellore", "timings": "Mon-Sat 9:00 AM - 5:00 PM", "experience": 4, "is_active": True},
        {"name": "Dr. Talari Anil Babu", "specialization": "Orthopaedics", "sub_specialization": "", "hospital": "A C Subba Reddy Govt Hospital", "hospital_area": "Nellore", "timings": "Mon-Sat 9:00 AM - 4:00 PM", "experience": 10, "is_active": True},
    ]

    for doc in doctors_data:
        doctor = Doctor(
            name=doc["name"],
            specialization=doc["specialization"],
            sub_specialization=doc.get("sub_specialization", ""),
            hospital=doc["hospital"],
            hospital_area=doc.get("hospital_area", "Nellore"),
            timings=doc["timings"],
            experience=doc["experience"],
            is_active=doc["is_active"],
        )
        db.session.add(doctor)

    db.session.commit()
    print(f"  Seeded {len(doctors_data)} Nellore doctors.")
