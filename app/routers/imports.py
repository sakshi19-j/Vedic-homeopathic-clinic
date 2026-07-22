from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.middleware.auth_middleware import doctor_only, receptionist_or_doctor
from app.models.import_job import ImportJob
from app.models.user import User
from app.enums import ImportStatus
import uuid, os, json

router = APIRouter(prefix="/imports", tags=["Patient Import"])

@router.post("/patients")
async def import_patients(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(receptionist_or_doctor)
):
    """
    Import patients from CSV or Excel — flexible column matching,
    runs synchronously and returns results immediately.
    """
    from app.services.import_service import import_patients_excel

    filename = file.filename.lower()
    if not any(filename.endswith(ext) for ext in [".csv", ".xlsx", ".xls"]):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files supported")

    result = await import_patients_excel(db, current_user.clinic_id, file)
    return result

@router.get("/history")
def import_history(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """List all import jobs for this clinic"""
    jobs = db.query(ImportJob).filter(
        ImportJob.clinic_id == current_user.clinic_id
    ).order_by(ImportJob.created_at.desc()).limit(20).all()

    return {
        "jobs": [
            {
                "id":               j.id,
                "file_name":        j.file_name,
                "file_type":        j.file_type,
                "status":           j.status,
                "total_rows":       j.total_rows,
                "successful_rows":  j.successful_rows,
                "failed_rows":      j.failed_rows,
                "created_at":       j.created_at.strftime("%d-%m-%Y %H:%M") if j.created_at else None,
                "completed_at":     j.completed_at
            }
            for j in jobs
        ]
    }

@router.get("/{job_id}/status")
def import_status(
    job_id:       str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(receptionist_or_doctor)
):
    """Check import job progress"""
    job = db.query(ImportJob).filter(
        ImportJob.id        == job_id,
        ImportJob.clinic_id == current_user.clinic_id
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    progress = 0
    if job.total_rows and job.total_rows > 0:
        progress = round((job.processed_rows / job.total_rows) * 100, 1)

    return {
        "job_id":          job.id,
        "status":          job.status,
        "file_name":       job.file_name,
        "total_rows":      job.total_rows,
        "processed_rows":  job.processed_rows,
        "successful_rows": job.successful_rows,
        "failed_rows":     job.failed_rows,
        "progress_pct":    progress,
        "errors":          json.loads(job.error_log) if job.error_log else []
    }