"""
Gunicorn entry point for WhatsApp Doctor Bot.
"""

from app import create_app
from app.scheduler import init_scheduler

app = create_app()

# Start background scheduler for reminders & follow-ups
init_scheduler(app)

if __name__ == "__main__":
    app.run()
