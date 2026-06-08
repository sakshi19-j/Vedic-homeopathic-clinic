import os
import uuid
from typing import Union

from supabase import create_client

from app.config import settings


# =====================================================
# SUPABASE CLIENT
# =====================================================

client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_KEY
)


# =====================================================
# UPLOAD PDF
# =====================================================

def upload_pdf(
    local_path: Union[str, bytes],
    folder: str = "receipts"
) -> str:

    # =================================================
    # GENERATE UNIQUE FILENAME
    # =================================================

    filename = (
        f"{folder}_"
        f"{uuid.uuid4().hex[:8]}.pdf"
    )

    storage_path = (
        f"{folder}/{filename}"
    )

    # =================================================
    # HANDLE BYTES OR FILE PATH
    # =================================================

    if isinstance(local_path, bytes):

        file_data = local_path

    else:

        with open(local_path, "rb") as f:

            file_data = f.read()

        # =============================================
        # DELETE LOCAL TEMP FILE
        # =============================================

        if os.path.exists(local_path):

            os.remove(local_path)

    # =================================================
    # UPLOAD TO SUPABASE STORAGE
    # =================================================

    client.storage.from_(

        "prescriptions-private"

    ).upload(

        path=storage_path,

        file=file_data,

        file_options={
            "content-type": "application/pdf"
        }
    )

    # =================================================
    # CREATE 24H SIGNED URL
    # =================================================

    signed = client.storage.from_(

        "prescriptions-private"

    ).create_signed_url(

        storage_path,

        60 * 60 * 24
    )

    # =================================================
    # RETURN SIGNED URL
    # =================================================

    return signed["signedURL"]