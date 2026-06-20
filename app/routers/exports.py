from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import receptionist_or_doctor
from app.models.user import User
from app.models.patient import Patient

import csv
import io

router = APIRouter(
    prefix="/exports",
    tags=["Exports"]
)


@router.get("/patients/csv")
def export_patients_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):

    patients = db.query(Patient).filter(
        Patient.clinic_id == current_user.clinic_id
    ).all()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Reg No",
        "Name",
        "Phone",
        "Age",
        "Gender",
        "City"
    ])

    for p in patients:

        writer.writerow([
            p.reg_no,
            f"{p.first_name} {p.last_name or ''}".strip(),
            p.phone_mobile,
            p.age,
            p.gender,
            p.res_city
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=patients.csv"
        }
    )