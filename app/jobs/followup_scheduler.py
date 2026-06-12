from app.database import SessionLocal

from app.services.followup_service import (
    send_due_followups
)


def run_followup_scheduler():

    db = SessionLocal()

    try:

        send_due_followups(db)

    finally:

        db.close()


if __name__ == "__main__":

    run_followup_scheduler()