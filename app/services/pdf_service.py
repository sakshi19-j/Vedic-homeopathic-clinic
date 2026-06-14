import os
import io
import logging
import qrcode

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm

from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image
from reportlab.lib.colors import HexColor

logger = logging.getLogger(__name__)

# =====================================================
# COLORS
# =====================================================

TEXT_DARK = colors.HexColor("#1a1a2e")
TEXT_GREY = colors.HexColor("#666666")


# =====================================================
# IMAGE LOADER
# =====================================================

def _load_image(url_or_path: str):

    if not url_or_path:
        return None

    try:

        if url_or_path.startswith("http"):

            import httpx

            resp = httpx.get(
                url_or_path,
                timeout=5.0
            )

            if resp.status_code == 200:

                return ImageReader(
                    io.BytesIO(resp.content)
                )

        else:

            if os.path.exists(url_or_path):

                return ImageReader(
                    url_or_path
                )

    except Exception as e:

        logger.warning(
            f"Image load error: {e}"
        )

    return None


# =====================================================
# THEMES
# =====================================================

def draw_classic_blue(c, W, H):

    PRIMARY = colors.HexColor("#1a237e")

    SECONDARY = colors.HexColor("#e8eaf6")

    c.setFillColor(PRIMARY)

    c.rect(
        0,
        H - 60 * mm,
        W,
        60 * mm,
        fill=1,
        stroke=0
    )

    return PRIMARY, SECONDARY


def draw_green_modern(c, W, H):

    PRIMARY = colors.HexColor("#00695c")

    SECONDARY = colors.HexColor("#e0f2f1")

    c.setFillColor(PRIMARY)

    c.roundRect(
        5 * mm,
        H - 62 * mm,
        W - 10 * mm,
        52 * mm,
        6 * mm,
        fill=1,
        stroke=0
    )

    return PRIMARY, SECONDARY


def draw_luxury_gold(c, W, H):

    PRIMARY = colors.HexColor("#8d6e63")

    SECONDARY = colors.HexColor("#fbe9e7")

    c.setFillColor(PRIMARY)

    c.rect(
        0,
        H - 58 * mm,
        W,
        58 * mm,
        fill=1,
        stroke=0
    )

    return PRIMARY, SECONDARY


# =====================================================
# HOMEOPATHY RX
# =====================================================

def _draw_homeopathy_rx(
    c,
    visit,
    y,
    PRIMARY
):

    rx = visit.get(
        "rx",
        ""
    )

    c.setFont(
        "Helvetica",
        11
    )

    c.setFillColor(TEXT_DARK)

    for line in rx.split("\n"):

        if line.strip():

            c.drawString(
                20 * mm,
                y,
                line
            )

            y -= 7 * mm

    return y


# =====================================================
# ALLOPATHY RX
# =====================================================

def _draw_allopathy_rx(
    c,
    visit,
    y,
    PRIMARY
):

    medicines = visit.get(
        "medicines",
        []
    )

    c.setFont(
        "Helvetica",
        10
    )

    for med in medicines:

        line = (
            f"{med.get('name', '')} | "
            f"{med.get('dosage', '')} | "
            f"{med.get('duration', '')}"
        )

        c.drawString(
            20 * mm,
            y,
            line
        )

        y -= 7 * mm

    return y


# =====================================================
# RECEIPT PDF COMPATIBILITY FUNCTION
# =====================================================

def generate_receipt_pdf(receipt):

    import io

    from reportlab.pdfgen import canvas

    from reportlab.lib.pagesizes import A4

    from reportlab.lib.units import mm

    from reportlab.lib import colors

    from reportlab.lib.utils import ImageReader

    buffer = io.BytesIO()

    c = canvas.Canvas(
        buffer,
        pagesize=A4
    )

    W, H = A4

    # =================================================
    # CLINIC COLORS
    # =================================================

    PRIMARY = colors.HexColor(
    getattr(
        receipt,
        "primary_color",
        "#2563eb"
    )
    )

    SECONDARY = colors.HexColor(
        getattr(
            receipt,
            "secondary_color",
            "#14b8a6"
        )
    )

    LIGHT = colors.HexColor("#f8fafc")

    DARK = colors.HexColor("#0f172a")

    # =================================================
    # HEADER
    # =================================================

    c.setFillColor(PRIMARY)

    c.rect(
        0,
        H - 55 * mm,
        W,
        55 * mm,
        fill=1,
        stroke=0
    )
    logo = _load_image(
        getattr(receipt, "logo_url", None)
    )

    if logo:

        try:

            c.drawImage(
                logo,
                W - 55 * mm,
                H - 45 * mm,
                width=28 * mm,
                height=28 * mm,
                preserveAspectRatio=True,
                mask="auto"
            )

        except Exception as e:

            logger.warning(
                f"Receipt logo error: {e}"
            )

    # =================================================
    # TITLE
    # =================================================

    c.setFillColor(colors.white)

    c.setFont(
        "Helvetica-Bold",
        22
    )

    c.drawString(
        20 * mm,
        H - 22 * mm,
        "PAYMENT RECEIPT"
    )

    # =================================================
    # CLINIC NAME
    # =================================================

    clinic_name = getattr(
        receipt,
        "clinic_name",
        "Vennova Clinic"
    )

    doctor_name = getattr(
        receipt,
        "doctor_name",
        "Doctor"
    )

    c.setFont(
        "Helvetica",
        11
    )

    c.drawString(
        20 * mm,
        H - 32 * mm,
        clinic_name
    )

    c.drawString(
        20 * mm,
        H - 39 * mm,
        f"Dr. {doctor_name}"
    )

    # =================================================
    # CARD
    # =================================================

    c.setFillColor(LIGHT)

    c.roundRect(
        15 * mm,
        H - 170 * mm,
        W - 30 * mm,
        95 * mm,
        6 * mm,
        fill=1,
        stroke=0
    )

    # =================================================
    # RECEIPT INFO
    # =================================================

    patient_name = getattr(
        receipt,
        "patient_name",
        "Patient"
    )

    amount = getattr(
        receipt,
        "amount",
        0
    )

    payment_mode = getattr(
        receipt,
        "payment_mode",
        "CASH"
    )

    visit_date = getattr(
        receipt,
        "visit_date",
        ""
    )

    receipt_no = getattr(
        receipt,
        "receipt_no",
        ""
    )

    c.setFillColor(DARK)

    c.setFont(
        "Helvetica-Bold",
        13
    )

    y = H - 90 * mm

    c.drawString(
        25 * mm,
        y,
        f"Receipt No: {receipt_no}"
    )

    y -= 12 * mm

    c.setFont(
        "Helvetica",
        12
    )

    c.drawString(
        25 * mm,
        y,
        f"Patient Name: {patient_name}"
    )

    y -= 10 * mm

    c.drawString(
        25 * mm,
        y,
        f"Amount Paid: ₹{amount}"
    )

    y -= 10 * mm

    c.drawString(
        25 * mm,
        y,
        f"Payment Mode: {payment_mode}"
    )

    y -= 10 * mm

    c.drawString(
        25 * mm,
        y,
        f"Visit Date: {visit_date}"
    )

    # =================================================
    # PAYMENT BADGE
    # =================================================

    c.setFillColor(SECONDARY)

    c.roundRect(
        W - 65 * mm,
        H - 105 * mm,
        35 * mm,
        12 * mm,
        3 * mm,
        fill=1,
        stroke=0
    )

    c.setFillColor(colors.white)

    c.setFont(
        "Helvetica-Bold",
        10
    )

    c.drawCentredString(
        W - 47 * mm,
        H - 98 * mm,
        "PAID"
    )

    signature = _load_image(
        getattr(receipt, "signature_url", None)
    )

    if signature:

        try:

            c.drawImage(
                signature,
                W - 60 * mm,
                25 * mm,
                width=35 * mm,
                height=18 * mm,
                preserveAspectRatio=True,
                mask="auto"
            )

        except Exception as e:

            logger.warning(
                f"Receipt signature error: {e}"
            )

    # =================================================
    # FOOTER
    # =================================================

    c.setFillColor(colors.HexColor("#64748b"))

    c.setFont(
        "Helvetica",
        9
    )

    c.drawCentredString(
        W / 2,
        18 * mm,
        "Digitally generated receipt"
    )

    footer_text = getattr(
        receipt,
        "footer_text",
        None
    )

    if not footer_text:

        footer_text = (
            "Powered by Vennova Clinic OS"
        )

    c.drawCentredString(
        W / 2,
        12 * mm,
        str(footer_text)
    )


    c.save()

    pdf = buffer.getvalue()

    buffer.close()

    return pdf



# =====================================================
# MAIN PDF
# =====================================================

def generate_prescription_pdf(
    visit: dict,
    clinic: dict,
    doctor: dict,
    patient: dict
) -> bytes:

    buf = io.BytesIO()

    c = canvas.Canvas(
        buf,
        pagesize=A4
    )

    W, H = A4

    # =================================================
    # THEME
    # =================================================

    theme = clinic.get(
        "prescription_theme",
        "CLASSIC_BLUE"
    )

    if theme == "GREEN_MODERN":

        PRIMARY, SECONDARY = draw_green_modern(
            c,
            W,
            H
        )

    elif theme == "LUXURY_GOLD":

        PRIMARY, SECONDARY = draw_luxury_gold(
            c,
            W,
            H
        )

    else:

        PRIMARY, SECONDARY = draw_classic_blue(
            c,
            W,
            H
        )

    # =================================================
    # LOGO
    # =================================================

    logo = _load_image(
        clinic.get("logo_url")
    )

    if logo:

        try:

            c.drawImage(
                logo,
                15 * mm,
                H - 52 * mm,
                width=30 * mm,
                height=30 * mm,
                preserveAspectRatio=True,
                mask="auto"
            )

        except Exception as e:

            logger.warning(
                f"Logo draw error: {e}"
            )

    # =================================================
    # HEADER
    # =================================================

    c.setFillColor(colors.white)

    c.setFont(
        "Helvetica-Bold",
        18
    )

    c.drawString(
        55 * mm,
        H - 20 * mm,
        clinic.get(
            "name",
            "Clinic"
        )
    )

    c.setFont(
        "Helvetica",
        11
    )

    c.drawString(
        55 * mm,
        H - 30 * mm,
        f"Dr. {doctor.get('name', '')}"
    )

    c.drawString(
        55 * mm,
        H - 37 * mm,
        doctor.get(
            "qualification",
            ""
        )
    )

    c.drawString(
        55 * mm,
        H - 44 * mm,
        clinic.get(
            "phone",
            ""
        )
    )

    c.drawString(
        55 * mm,
        H - 51 * mm,
        clinic.get(
            "address",
            ""
        )
    )

    # =================================================
    # PATIENT INFO
    # =================================================

    c.setFillColor(TEXT_DARK)

    c.setFont(
        "Helvetica-Bold",
        10
    )

    c.drawString(
        15 * mm,
        H - 72 * mm,
        f"Patient: "
        f"{patient.get('name', '')}"
    )

    c.drawString(
        90 * mm,
        H - 72 * mm,
        f"Age/Gender: "
        f"{patient.get('age', '')} / "
        f"{patient.get('gender', '')}"
    )

    c.drawString(
        160 * mm,
        H - 72 * mm,
        datetime.now().strftime(
            "%d %b %Y"
        )
    )

    # =================================================
    # QR
    # =================================================

    backend_url = visit.get(
        "backend_url",
        ""
    )

    token = visit.get(
        "token",
        ""
    )

    # FIXED QR URL
    qr_url = (
        f"{backend_url}"
        f"/prescriptions/rx/{token}"
    )

    try:

        qr = qrcode.make(
            qr_url
        )

        qr_buffer = BytesIO()

        qr.save(qr_buffer)

        qr_buffer.seek(0)

        c.drawImage(
            ImageReader(qr_buffer),
            W - 45 * mm,
            H - 110 * mm,
            width=25 * mm,
            height=25 * mm
        )

    except Exception as e:

        logger.warning(
            f"QR error: {e}"
        )

    # =================================================
    # RX SYMBOL
    # =================================================

    c.setFillColor(PRIMARY)

    c.setFont(
        "Helvetica-Bold",
        28
    )

    c.drawString(
        15 * mm,
        H - 105 * mm,
        "℞"
    )

    # =================================================
    # CONTENT
    # =================================================

    y = H - 115 * mm

    visit_type = str(
        visit.get(
            "visit_type",
            ""
        )
    ).upper()

    if visit_type == "ALLOPATHY":

        y = _draw_allopathy_rx(
            c,
            visit,
            y,
            PRIMARY
        )

    else:

        y = _draw_homeopathy_rx(
            c,
            visit,
            y,
            PRIMARY
        )

    # =================================================
    # SIGNATURE
    # =================================================

    signature = _load_image(
        clinic.get(
            "signature_url"
        )
    )

    if signature:

        try:

            c.drawImage(
                signature,
                W - 60 * mm,
                30 * mm,
                width=35 * mm,
                height=20 * mm,
                preserveAspectRatio=True,
                mask="auto"
            )

        except Exception as e:

            logger.warning(
                f"Signature draw error: {e}"
            )

    # =================================================
    # FOOTER
    # =================================================

    c.setFillColor(TEXT_GREY)

    c.setFont(
        "Helvetica",
        8
    )

    c.drawCentredString(
        W / 2,
        15 * mm,
        "Digitally generated prescription"
    )

    c.drawCentredString(
        W / 2,
        10 * mm,
        "Powered by Vennova Clinic OS"
    )

    c.save()

    pdf = buf.getvalue()

    buf.close()

    return pdf