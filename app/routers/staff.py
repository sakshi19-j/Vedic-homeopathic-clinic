from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import uuid4

from app.database import get_db

from app.middleware.auth_middleware import (
    doctor_only,
    get_current_user,
    check_staff_limit
)

from app.models.user import User
from app.enums import UserRole

from app.utils.security import hash_password
from app.services.audit_service import log_action


router = APIRouter(
    prefix="/staff",
    tags=["Staff"]
)


# =====================================================
# SCHEMAS
# =====================================================

class StaffCreate(BaseModel):
    name: str
    phone: str
    email: Optional[EmailStr] = None
    password: str
    role: str = "RECEPTIONIST"


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


# =====================================================
# CREATE STAFF
# =====================================================

@router.post("/")
def create_staff(
    data: StaffCreate,

    db: Session = Depends(get_db),

    # STAFF LIMIT ENFORCER
    current_user: User = Depends(check_staff_limit)
):
    """
    Create new staff member.

    Doctor only.
    Enforces subscription staff limits.
    """

    # Ensure only doctors can create staff
    if current_user.role != UserRole.DOCTOR:
        raise HTTPException(
            status_code=403,
            detail="Only doctor can create staff"
        )

    # Check duplicate phone
    existing = db.query(User).filter(
        User.phone == data.phone
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Phone already registered"
        )

    # Check duplicate email
    if data.email:
        existing_email = db.query(User).filter(
            User.email == data.email
        ).first()

        if existing_email:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

    # Create new staff user
    staff = User(
        id=str(uuid4()),

        clinic_id=current_user.clinic_id,

        name=data.name,
        phone=data.phone,
        email=data.email,

        role=UserRole(data.role),

        hashed_password=hash_password(
            data.password
        ),

        is_active=True
    )

    db.add(staff)

    db.commit()

    db.refresh(staff)

    # =====================================================
    # AUDIT LOG
    # =====================================================

    log_action(
        db=db,
        user=current_user,
        action="STAFF_CREATED",
        resource="staff",
        resource_id=staff.id,
        detail=f"Added staff: {data.name} ({data.role})",
    )

    return {
        "message": "Staff created successfully",
        "id": staff.id
    }


# =====================================================
# LIST STAFF
# =====================================================

@router.get("/")
def list_staff(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        doctor_only
    )
):
    """
    List all staff for this clinic.
    """

    staff = db.query(User).filter(
        User.clinic_id == current_user.clinic_id,

        User.role != UserRole.DOCTOR
    ).all()

    return {
        "total": len(staff),

        "staff": [
            {
                "id": s.id,
                "name": s.name,
                "phone": s.phone,
                "email": s.email,

                "role":
                    s.role.value
                    if hasattr(s.role, "value")
                    else s.role,

                "is_active": s.is_active
            }

            for s in staff
        ]
    }


# =====================================================
# UPDATE STAFF
# =====================================================

@router.put("/{staff_id}")
def update_staff(
    staff_id: str,

    data: StaffUpdate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        doctor_only
    )
):
    """
    Update staff member — doctor only.
    """

    staff = db.query(User).filter(
        User.id == staff_id,

        User.clinic_id == current_user.clinic_id
    ).first()

    if not staff:
        raise HTTPException(
            status_code=404,
            detail="Staff not found"
        )

    update_data = data.model_dump(
        exclude_unset=True
    )

    # Convert role string to enum
    if "role" in update_data:
        update_data["role"] = UserRole(
            update_data["role"]
        )

    for key, value in update_data.items():
        setattr(staff, key, value)

    db.commit()

    db.refresh(staff)

    return {
        "message": "Staff updated",
        "id": staff_id
    }


# =====================================================
# DELETE STAFF
# =====================================================

@router.delete("/{staff_id}")
def delete_staff(
    staff_id: str,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        doctor_only
    )
):
    """
    Deactivate staff member.
    """

    staff = db.query(User).filter(
        User.id == staff_id,

        User.clinic_id == current_user.clinic_id,

        User.role != UserRole.DOCTOR
    ).first()

    if not staff:
        raise HTTPException(
            status_code=404,
            detail="Staff not found"
        )

    staff.is_active = False

    db.commit()

    return {
        "message": "Staff deactivated"
    }