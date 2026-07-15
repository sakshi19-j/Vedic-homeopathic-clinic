from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import pytz

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.clinic import Clinic
from app.models.user import User

IST = pytz.timezone("Asia/Kolkata")

def require_active_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    clinic = db.query(Clinic).filter(Clinic.id == current_user.clinic_id).first()
    if not clinic:
        raise HTTPException(404, "Clinic not found")

    status = clinic.subscription_status

    if status == "ACTIVE":
        return current_user

    if status == "TRIAL":
        if clinic.trial_end_date:
            trial_end = (
                IST.localize(clinic.trial_end_date)
                if clinic.trial_end_date.tzinfo is None
                else clinic.trial_end_date
            )
            if datetime.now(IST) > trial_end:
                raise HTTPException(
                    status_code=402,
                    detail="Trial expired. Please subscribe to continue using Vennova."
                )
        return current_user

    # EXPIRED / CANCELLED / anything else
    raise HTTPException(
        status_code=402,
        detail="Your subscription has expired. Please renew to continue."
    )