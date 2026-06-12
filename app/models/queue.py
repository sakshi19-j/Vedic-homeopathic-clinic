from sqlalchemy import Column, String, Integer, DateTime, Date
from app.models.base import BaseModel
from app.enums import QueueStatus, VisitTypeQueue
from datetime import datetime


class Queue(BaseModel):
    __tablename__ = "queue"

    clinic_id      = Column(String, nullable=False, index=True)
    patient_id     = Column(String, nullable=False, index=True)
    appointment_id = Column(String, nullable=True)   # linked if booked appointment
    token_number   = Column(Integer, nullable=False)
    queue_date     = Column(Date, nullable=False, index=True)
    visit_type     = Column(String, default=VisitTypeQueue.WALKIN)
    status         = Column(String,default="WAITING",index=True)
    priority       = Column(Integer, default=0)      # 1=urgent, 0=normal
    check_in_time  = Column(DateTime, default=datetime.utcnow)
    called_time    = Column(DateTime, nullable=True)
    start_time     = Column(DateTime, nullable=True)
    end_time       = Column(DateTime, nullable=True)
    notes          = Column(String, nullable=True)
    visit_id       = Column(String, nullable=True)   # linked after visit created