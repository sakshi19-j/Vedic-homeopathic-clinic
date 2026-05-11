from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.middleware.auth_middleware import doctor_only
from app.models.user import User
from app.services.audit_service import get_audit_logs

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/logs")
def fetch_audit_logs(
    user_id:  Optional[str] = Query(None),
    action:   Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    skip:     int = Query(0),
    limit:    int = Query(50),
    db:       Session = Depends(get_db),
    current_user: User = Depends(doctor_only)
):
    """
    Doctor-only: fetch audit trail for this clinic.
    """
    return get_audit_logs(
        db         = db,
        clinic_id  = current_user.clinic_id,
        user_id    = user_id,
        action     = action,
        resource   = resource,
        skip       = skip,
        limit      = limit,
    )