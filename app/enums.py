from enum import Enum

class GenderEnum(str, Enum):
    MALE   = "MALE"
    FEMALE = "FEMALE"
    OTHER  = "OTHER"

class MaritalStatusEnum(str, Enum):
    SINGLE   = "SINGLE"
    MARRIED  = "MARRIED"
    WIDOWED  = "WIDOWED"
    DIVORCED = "DIVORCED"

class UserRole(str, Enum):
    DOCTOR       = "DOCTOR"
    RECEPTIONIST = "RECEPTIONIST"
    STAFF        = "STAFF"

class PatientType(str, Enum):
    ALLOPATHY  = "ALLOPATHY"
    HOMEOPATHY = "HOMEOPATHY"
    BOTH       = "BOTH"

class VisitType(str, Enum):
    ALLOPATHY  = "ALLOPATHY"
    HOMEOPATHY = "HOMEOPATHY"
    AYURVEDIC  = "AYURVEDIC"   # ← ADDED

class QueueStatus(str, Enum):

    WAITING = "WAITING"

    IN_TREATMENT = "IN_TREATMENT"

    WAITING_BILLING = "WAITING_BILLING"

    COMPLETED = "COMPLETED"

    NO_SHOW = "NO_SHOW"

class VisitTypeQueue(str, Enum):
    WALKIN      = "WALKIN"
    APPOINTMENT = "APPOINTMENT"

class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID    = "PAID"
    WAIVED  = "WAIVED"

class PaymentMode(str, Enum):
    CASH   = "CASH"
    UPI    = "UPI"
    ONLINE = "ONLINE"
    CARD   = "CARD"

class FollowUpType(str, Enum):
    THREE_DAY   = "THREE_DAY"
    SEVEN_DAY   = "SEVEN_DAY"
    FIFTEEN_DAY = "FIFTEEN_DAY"
    MONTHLY     = "MONTHLY"
    CUSTOM      = "CUSTOM"

class FollowUpStatus(str, Enum):
    PENDING = "PENDING"
    SENT    = "SENT"
    DONE    = "DONE"
    SKIPPED = "SKIPPED"
    FAILED  = "FAILED"

class Channel(str, Enum):
    WHATSAPP = "WHATSAPP"
    SMS      = "SMS"
    VOICE    = "VOICE"
    EMAIL    = "EMAIL"

class SubscriptionPlan(str, Enum):
    STARTER    = "STARTER"
    GROWTH     = "GROWTH"
    ENTERPRISE = "ENTERPRISE"

class SubscriptionStatus(str, Enum):
    TRIAL     = "TRIAL"
    ACTIVE    = "ACTIVE"
    EXPIRED   = "EXPIRED"
    CANCELLED = "CANCELLED"

class ImportStatus(str, Enum):
    PENDING    = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"

class AppointmentStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW   = "NO_SHOW"

class VisitStatus(str, Enum):
    DRAFT     = "DRAFT"       # started, not complete
    ACTIVE    = "ACTIVE"      # consultation in progress
    BILLING   = "BILLING"     # consultation done, waiting payment
    COMPLETED = "COMPLETED"   # paid and closed
    CANCELLED = "CANCELLED"