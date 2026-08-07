import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import text, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth_middleware import (
    CurrentUser,
    get_current_user,
    require_role
)
from app.models.clinic import Clinic
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/superadmin",
    tags=["Superadmin"]
)


# =====================================================
# SCHEMAS
# =====================================================

class SuperadminClinicCreateRequest(BaseModel):
    clinic_name: str
    owner_name: str
    owner_email: EmailStr
    password: str
    clinic_type: Optional[str] = "HOMEOPATHY"
    phone: Optional[str] = None
    city: Optional[str] = None
    timings: Optional[str] = None


class SuperadminClinicResponse(BaseModel):
    id: str
    name: str
    owner_name: str
    owner_email: str
    plan: Optional[str] = None
    subscription_status: Optional[str] = None
    trial_end_date: Optional[str] = None
    patient_count: int
    total_revenue: float


# =====================================================
# LIST CLINICS
# =====================================================

@router.get("/clinics")
def list_clinics(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("super_admin"))
):
    query = text(
        """
        SELECT
            c.id AS clinic_id,
            c.name AS clinic_name,
            c.plan_id AS plan_id,
            c.subscription_status AS subscription_status,
            c.trial_end_date AS trial_end_date,
            p.full_name AS owner_name,
            p.email AS owner_email,
            COALESCE(patient_counts.count, 0) AS patient_count,
            COALESCE(revenue.total_revenue, 0) AS total_revenue
        FROM public.clinics c
        LEFT JOIN public.profiles p
            ON p.id = c.owner_id
        LEFT JOIN (
            SELECT clinic_id, COUNT(*) AS count
            FROM public.patients
            WHERE is_active = true
            GROUP BY clinic_id
        ) AS patient_counts
            ON patient_counts.clinic_id = c.id
        LEFT JOIN (
            SELECT clinic_id, SUM(fee) AS total_revenue
            FROM public.visits
            WHERE payment_status = 'PAID'
            GROUP BY clinic_id
        ) AS revenue
            ON revenue.clinic_id = c.id
        """
    )

    rows = db.execute(query).fetchall()

    return {
        "total": len(rows),
        "clinics": [
            {
                "id": str(row.clinic_id),
                "name": row.clinic_name,
                "owner_name": row.owner_name,
                "owner_email": row.owner_email,
                "plan": row.plan_id,
                "subscription_status": row.subscription_status,
                "trial_end_date": str(row.trial_end_date) if row.trial_end_date else None,
                "patient_count": int(row.patient_count),
                "total_revenue": float(row.total_revenue or 0)
            }
            for row in rows
        ]
    }


# =====================================================
# CREATE CLINIC + OWNER
# =====================================================

@router.post("/clinics")
async def create_clinic(
    data: SuperadminClinicCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("super_admin"))
):
    # Create Supabase auth user via Admin API
    supabase_admin_url = (
        f"{settings.SUPABASE_URL}/auth/v1/admin/users"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            supabase_admin_url,
            headers={
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "email": data.owner_email,
                "password": data.password,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": data.owner_name,
                    "role": "admin"
                }
            }
        )

    if resp.status_code not in (200, 201):
        error_detail = resp.json().get("msg", "Failed to create user")
        raise HTTPException(400, f"Supabase error: {error_detail}")

    user_id = resp.json()["id"]

    # Insert clinic
    clinic_id = str(user_id)

    db.execute(
        text(
            "INSERT INTO public.clinics (id, name, owner_id, clinic_type, phone, city, timings, plan_id, subscription_status, trial_end_date, is_active, created_at, updated_at) "
            "VALUES (:id, :name, :owner_id, :clinic_type, :phone, :city, :timings, :plan_id, :subscription_status, :trial_end_date, true, now(), now())"
        ),
        {
            "id": user_id,
            "name": data.clinic_name,
            "owner_id": user_id,
            "clinic_type": data.clinic_type,
            "phone": data.phone,
            "city": data.city,
            "timings": data.timings,
            "plan_id": "STARTER",
            "subscription_status": "TRIAL",
            "trial_end_date": datetime.utcnow() + timedelta(days=30)
        }
    )

    # Insert owner profile
    db.execute(
        text(
            "INSERT INTO public.profiles (id, clinic_id, full_name, email, phone, created_at, updated_at) "
            "VALUES (:id, :clinic_id, :full_name, :email, :phone, now(), now())"
        ),
        {
            "id": user_id,
            "clinic_id": user_id,
            "full_name": data.owner_name,
            "email": data.owner_email,
            "phone": data.phone
        }
    )

    # Assign owner/admin role
    db.execute(
        text(
            "INSERT INTO public.user_roles (user_id, clinic_id, role, is_active, created_at) "
            "VALUES (:user_id, :clinic_id, :role, true, now())"
        ),
        {
            "user_id": user_id,
            "clinic_id": user_id,
            "role": "admin"
        }
    )

    db.commit()

    return {
        "message": "Clinic created successfully",
        "clinic_id": user_id,
        "owner_id": user_id,
        "owner_email": data.owner_email,
        "plan": "STARTER",
        "subscription_status": "TRIAL",
        "trial_end_date": str(datetime.utcnow() + timedelta(days=30))
    }
