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

    buffer = io.BytesIO()

    c = canvas.Canvas(buffer)

    # -------------------------------------------------
    # TITLE
    # -------------------------------------------------

    c.setFont(
        "Helvetica-Bold",
        18
    )

    c.drawString(
        80,
        800,
        "Vennova Receipt"
    )

    # -------------------------------------------------
    # CONTENT
    # -------------------------------------------------

    c.setFont(
        "Helvetica",
        12
    )

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

    date = getattr(
        receipt,
        "date",
        ""
    )

    c.drawString(
        80,
        750,
        f"Patient: {patient_name}"
    )

    c.drawString(
        80,
        725,
        f"Amount: ₹{amount}"
    )

    c.drawString(
        80,
        700,
        f"Payment Mode: {payment_mode}"
    )

    c.drawString(
        80,
        675,
        f"Date: {date}"
    )

    # -------------------------------------------------
    # FOOTER
    # -------------------------------------------------

    c.setFont(
        "Helvetica-Oblique",
        9
    )

    c.drawString(
        80,
        620,
        "Generated by Vennova Clinic OS"
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