PLAN_LIMITS = {
    "starter": {
        "max_patients_per_month": 200,
        "whatsapp_templates": True,
        "advanced_analytics": False,
        "patient_import": False,
        "multi_branch": False,
    },
    "growth": {
        "max_patients_per_month": 1000,
        "whatsapp_templates": True,
        "advanced_analytics": True,
        "patient_import": True,
        "multi_branch": False,
    },
    "clinicpro": {
        "max_patients_per_month": None,
        "whatsapp_templates": True,
        "advanced_analytics": True,
        "patient_import": True,
        "multi_branch": True,
    },
}


def get_plan_limits(plan_id: str) -> dict:
    return PLAN_LIMITS.get(plan_id, PLAN_LIMITS["starter"])