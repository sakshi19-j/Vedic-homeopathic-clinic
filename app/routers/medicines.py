from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.medicine import Medicine
from app.middleware.auth_middleware import receptionist_or_doctor

router = APIRouter(
    prefix="/medicines",
    tags=["Medicines"]
)


@router.post("/")
def create_medicine(
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(receptionist_or_doctor)
):

    medicine = Medicine(
        visit_id=data.get("visit_id"),
        name=data.get("name"),
        potency=data.get("potency"),
        timing=data.get("timing"),
        days=data.get("days"),
        food_relation=data.get("food_relation"),
        notes=data.get("notes")
    )

    db.add(medicine)
    db.commit()
    db.refresh(medicine)

    return medicine


@router.get("/{visit_id}")
def get_medicines(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(receptionist_or_doctor)
):

    medicines = db.query(Medicine).filter(
        Medicine.visit_id == visit_id
    ).all()

    return {
        "items": medicines
    }