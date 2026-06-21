from fastapi import APIRouter

router = APIRouter(
    prefix="/followups",
    tags=["Followups"]
)

@router.get("/today")
def followups_today():
    return []

@router.get("/upcoming")
def followups_upcoming():
    return []