"""
VENNOVA — UPDATED AUTH ROUTER
==============================
REPLACE: app/routers/auth.py

REMOVED:
  - POST /auth/signup  (Supabase handles this)
  - POST /auth/login   (Supabase handles this)

KEPT:
  - GET  /auth/me          (get current user info)
  - GET  /auth/clinic      (get clinic details)
  - PUT  /auth/clinic      (update clinic — admin only)
  - POST /auth/staff       (admin creates staff account)
  - GET  /auth/usage       (usage stats)

HOW STAFF CREATION WORKS NOW:
  1. Admin calls POST /auth/staff with name, email, password, role
  2. FastAPI creates Supabase auth user via Admin API
  3. FastAPI creates profile + user_role in DB
  4. Staff can now log in via Supabase Auth on frontend
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth_middleware import (
    CurrentUser,
    admin_only,
    get_current_user,
)
from app.models.clinic import Clinic
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


# =====================================================
# SCHEMAS
# =====================================================

class CreateStaffRequest(BaseModel):
    name:     str
    email:    EmailStr
    password: str
    role:     str   # reception | allopathy | homeopathy


class UpdateClinicRequest(BaseModel):
    name:                  str | None = None
    doctor_name:           str | None = None
    qualification:         str | None = None
    address:               str | None = None
    city:                  str | None = None
    phone:                 str | None = None
    email:                 str | None = None
    timings:               str | None = None
    primary_color:         str | None = None
    secondary_color:       str | None = None
    logo_url:              str | None = None
    signature_url:         str | None = None
    clinic_type:           str | None = None
    notification_settings: dict | None = None


# =====================================================
# GET CURRENT USER
# =====================================================

@router.get("/me")
def get_me(
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get current logged-in user info"""
    return {
        "id":        current_user.id,
        "email":     current_user.email,
        "full_name": current_user.full_name,
        "role":      current_user.role,
        "clinic_id": current_user.clinic_id
    }


# =====================================================
# GET CLINIC
# =====================================================

@router.get("/clinic")
def get_clinic(
    db:           Session     = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get current clinic details + usage stats"""

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        raise HTTPException(404, "Clinic not found")

    usage = auth_service.get_usage_stats(db, current_user.clinic_id)

    return {
        "id":                    str(clinic.id),
        "name":                  clinic.name,
        "doctor_name":           clinic.doctor_name,
        "qualification":         clinic.qualification,
        "address":               clinic.address,
        "city":                  clinic.city,
        "phone":                 clinic.phone,
        "email":                 clinic.email,
        "timings":               clinic.timings,
        "clinic_type":           clinic.clinic_type,
        "logo_url":              clinic.logo_url,
        "signature_url":         clinic.signature_url,
        "primary_color":         clinic.primary_color,
        "secondary_color":       clinic.secondary_color,
        "branding_enabled":      clinic.branding_enabled,
        "plan":                  clinic.plan_id,
        "subscription_status":   clinic.subscription_status,
        "trial_end_date":        str(clinic.trial_end_date) if clinic.trial_end_date else None,
        "staff_limit":           clinic.staff_limit,
        "max_patients_per_month": clinic.max_patients_per_month,
        "notification_settings": getattr(clinic, "notification_settings", None),
        "onboarding_complete":   clinic.onboarding_complete,
        "has_logo":              clinic.has_logo,
        "has_signature":         clinic.has_signature,
        "has_whatsapp":          clinic.has_whatsapp,
        "usage":                 usage
    }


# =====================================================
# UPDATE CLINIC
# =====================================================

@router.put("/clinic")
def update_clinic(
    data:         UpdateClinicRequest,
    db:           Session     = Depends(get_db),
    current_user: CurrentUser = Depends(admin_only)
):
    """Update clinic details — admin only"""

    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id
    ).first()

    if not clinic:
        raise HTTPException(404, "Clinic not found")

    update_data = data.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(clinic, key, value)

    # Update onboarding flags
    if data.logo_url:
        clinic.has_logo = True
    if data.signature_url:
        clinic.has_signature = True

    db.commit()
    db.refresh(clinic)

    return {"message": "Clinic updated", "clinic": {"id": str(clinic.id), "name": clinic.name}}


# =====================================================
# CREATE STAFF
# Admin creates staff accounts — staff cannot self-register
# Uses Supabase Admin API to create auth user
# =====================================================

@router.post("/staff")
async def create_staff(
    data:         CreateStaffRequest,
    db:           Session     = Depends(get_db),
    current_user: CurrentUser = Depends(admin_only)
):
    """
    Admin creates a reception/doctor staff account.

    Flow:
    1. Create Supabase auth user via Admin API
    2. Create profile row in DB
    3. Create user_role row in DB
    Staff can then log in via frontend with the given password.
    """

    valid_roles = ("reception", "allopathy", "homeopathy")
    if data.role not in valid_roles:
        raise HTTPException(400, f"Role must be one of: {valid_roles}")

    # ─────────────────────────────────────────────
    # Step 1: Create Supabase auth user via Admin API
    # ─────────────────────────────────────────────
    supabase_admin_url = (
        f"{settings.SUPABASE_URL}/auth/v1/admin/users"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            supabase_admin_url,
            headers={
                "apikey":        settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type":  "application/json"
            },
            json={
                "email":            data.email,
                "password":         data.password,
                "email_confirm":    True,
                "user_metadata": {
                    "full_name": data.name,
                    "role":      data.role
                }
            }
        )

    if resp.status_code not in (200, 201):
        error_detail = resp.json().get("msg", "Failed to create user")
        raise HTTPException(400, f"Supabase error: {error_detail}")

    new_user_id = resp.json()["id"]

    # ─────────────────────────────────────────────
    # Step 2: Create profile
    # ─────────────────────────────────────────────
    db.execute(
        text(
            "INSERT INTO public.profiles (id, clinic_id, full_name, email) "
            "VALUES (:id, :clinic_id, :full_name, :email)"
        ),
        {
            "id":        new_user_id,
            "clinic_id": current_user.clinic_id,
            "full_name": data.name,
            "email":     data.email
        }
    )

    # ─────────────────────────────────────────────
    # Step 3: Assign role
    # ─────────────────────────────────────────────
    db.execute(
        text(
            "INSERT INTO public.user_roles (user_id, clinic_id, role) "
            "VALUES (:user_id, :clinic_id, :role)"
        ),
        {
            "user_id":   new_user_id,
            "clinic_id": current_user.clinic_id,
            "role":      data.role
        }
    )

    db.commit()

    logger.info(
        f"Staff created: {data.email} ({data.role}) "
        f"for clinic {current_user.clinic_id}"
    )

    return {
        "message":  "Staff account created successfully",
        "user_id":  new_user_id,
        "email":    data.email,
        "role":     data.role,
        "clinic_id": current_user.clinic_id
    }


# =====================================================
# USAGE STATS
# =====================================================

@router.get("/usage")
def get_usage(
    db:           Session     = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Patient usage this month vs plan limit"""
    return auth_service.get_usage_stats(db, current_user.clinic_id)