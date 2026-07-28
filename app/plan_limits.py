PLAN_LIMITS = {
    "starter": {
        "staff_limit": 1,
        "max_patients_per_month": 100,
        "whatsapp_templates": False,
        "advanced_analytics": False,
        "patient_import": False,
        "multi_branch": False,
    },
    "growth": {
        "staff_limit": 3,
        "max_patients_per_month": None,
        "whatsapp_templates": True,
        "advanced_analytics": True,
        "patient_import": True,
        "multi_branch": False,
    },
    "clinicpro": {
        "staff_limit": None,
        "max_patients_per_month": None,
        "whatsapp_templates": True,
        "advanced_analytics": True,
        "patient_import": True,
        "multi_branch": True,
    },
}

def get_plan_limits(plan_id: str) -> dict:
    return PLAN_LIMITS.get(plan_id, PLAN_LIMITS["starter"])