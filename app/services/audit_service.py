from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.user import User


def log_action(
    db:          Session,
    user:        User,
    action:      str,
    resource:    str  = None,
    resource_id: str  = None,
    detail:      str  = None,
    meta:        dict = None,
    ip_address:  str  = None,
    user_agent:  str  = None,
):
    """
    Write one audit log entry.
    Call this after any significant action.

    Usage:
        log_action(db, current_user,
            action="PATIENT_CREATED",
            resource="patient",
            resource_id=patient.id,
            detail=f"Registered {patient.first_name} ({patient.reg_no})")
    """
    entry = AuditLog(
        clinic_id   = str(user.clinic_id),
        user_id     = str(user.id),
        user_name   = user.name,
        user_role   = user.role.value if hasattr(user.role, "value") else str(user.role),
        action      = action,
        resource    = resource,
        resource_id = str(resource_id) if resource_id else None,
        detail      = detail,
        meta        = meta or {},
        ip_address  = ip_address,
        user_agent  = user_agent,
    )
    db.add(entry)
    db.commit()


def get_audit_logs(
    db:         Session,
    clinic_id:  str,
    user_id:    str  = None,
    action:     str  = None,
    resource:   str  = None,
    skip:       int  = 0,
    limit:      int  = 50,
) -> dict:
    """
    Fetch audit logs with optional filters.
    """
    query = db.query(AuditLog).filter(
        AuditLog.clinic_id == clinic_id
    )

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource:
        query = query.filter(AuditLog.resource == resource)

    total = query.count()
    logs  = query.order_by(
        AuditLog.created_at.desc()
    ).offset(skip).limit(limit).all()

    return {
        "total": total,
        "logs": [
            {
                "id":          l.id,
                "user_name":   l.user_name,
                "user_role":   l.user_role,
                "action":      l.action,
                "resource":    l.resource,
                "resource_id": l.resource_id,
                "detail":      l.detail,
                "meta":        l.meta,
                "ip_address":  l.ip_address,
                "created_at":  l.created_at,
            }
            for l in logs
        ]
    }