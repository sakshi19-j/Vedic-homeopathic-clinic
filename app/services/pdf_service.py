import os
import uuid
import json
import io
import logging
import tempfile
import qrcode

from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A5, A4
from reportlab.lib import colors
from reportlab.lib.units import mm

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    Image
)

from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)

from reportlab.lib.enums import (
    TA_CENTER,
    TA_RIGHT
)

from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.schemas.billing import ReceiptData

logger = logging.getLogger(__name__)


# =====================================================
# STATIC COLORS
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

            return None

        else:

            if os.path.exists(url_or_path):

                return ImageReader(
                    url_or_path
                )

            return None

    except Exception as e:

        logger.warning(
            f"Image load error: {e}"
        )

        return None


# =====================================================
# ENUM VALUE
# =====================================================

def _enum_value(val):

    if val is None:
        return ""

    if hasattr(val, "value"):
        return str(val.value)

    return str(val)


# =====================================================
# HOMEOPATHY DRAWER
# =====================================================

def _draw_homeopathy_rx(

    c,
    visit,
    y_start,
    W,
    PRIMARY
):

    y = y_start

    chief = visit.get(
        "chief_complaint",
        ""
    )

    if chief:

        c.setFont(
            "Helvetica-Bold",
            10
        )

        c.setFillColor(PRIMARY)

        c.drawString(
            15*mm,
            y,
            "Chief Complaint:"
        )

        c.setFont(
            "Helvetica",
            10
        )

        c.setFillColor(TEXT_DARK)

        c.drawString(
            60*mm,
            y,
            chief
        )

        y -= 8*mm

    rx = visit.get(
        "rx",
        ""
    )

    if rx:

        c.setFont(
            "Helvetica",
            10
        )

        c.setFillColor(TEXT_DARK)

        for line in rx.split("\n"):

            if line.strip():

                c.drawString(
                    20*mm,
                    y,
                    line[:90]
                )

                y -= 6*mm

    return y


# =====================================================
# ALLOPATHY DRAWER
# =====================================================

def _draw_allopathy_rx(

    c,
    visit,
    y_start,
    W,
    PRIMARY,
    SECONDARY
):

    y = y_start

    medicines = visit.get(
        "medicines",
        []
    )

    if medicines:

        c.setFillColor(PRIMARY)

        c.rect(
            15*mm,
            y-1*mm,
            W-30*mm,
            7*mm,
            fill=1,
            stroke=0
        )

        c.setFillColor(colors.white)

        c.setFont(
            "Helvetica-Bold",
            9
        )

        c.drawString(
            18*mm,
            y+1*mm,
            "Medicine"
        )

        c.drawString(
            90*mm,
            y+1*mm,
            "Dosage"
        )

        c.drawString(
            130*mm,
            y+1*mm,
            "Duration"
        )

        y -= 8*mm

        for i, med in enumerate(
            medicines,
            1
        ):

            bg = (
                SECONDARY
                if i % 2 == 0
                else colors.white
            )

            c.setFillColor(bg)

            c.rect(
                15*mm,
                y-1*mm,
                W-30*mm,
                6*mm,
                fill=1,
                stroke=0
            )

            c.setFillColor(TEXT_DARK)

            c.setFont(
                "Helvetica",
                8
            )

            c.drawString(
                18*mm,
                y+1*mm,
                str(med.get("name", ""))[:28]
            )

            c.drawString(
                90*mm,
                y+1*mm,
                str(med.get("dosage", ""))[:15]
            )

            c.drawString(
                130*mm,
                y+1*mm,
                str(med.get("duration", ""))[:15]
            )

            y -= 6*mm

    return y


# =====================================================
# CLASSIC BLUE THEME
# =====================================================

def draw_classic_blue(

    c,
    W,
    H
):

    PRIMARY = colors.HexColor("#1a237e")

    SECONDARY = colors.HexColor("#e8eaf6")

    c.setFillColor(PRIMARY)

    c.rect(
        0,
        H-60*mm,
        W,
        60*mm,
        fill=1,
        stroke=0
    )

    c.setFillColor(SECONDARY)

    c.rect(
        0,
        H-85*mm,
        W,
        25*mm,
        fill=1,
        stroke=0
    )

    return PRIMARY, SECONDARY


# =====================================================
# GREEN MODERN THEME
# =====================================================

def draw_green_modern(

    c,
    W,
    H
):

    PRIMARY = colors.HexColor("#00695c")

    SECONDARY = colors.HexColor("#e0f2f1")

    c.setFillColor(PRIMARY)

    c.roundRect(
        5*mm,
        H-62*mm,
        W-10*mm,
        52*mm,
        6*mm,
        fill=1,
        stroke=0
    )

    c.setFillColor(SECONDARY)

    c.roundRect(
        8*mm,
        H-88*mm,
        W-16*mm,
        22*mm,
        4*mm,
        fill=1,
        stroke=0
    )

    return PRIMARY, SECONDARY


# =====================================================
# LUXURY GOLD THEME
# =====================================================

def draw_luxury_gold(

    c,
    W,
    H
):

    PRIMARY = colors.HexColor("#8d6e63")

    SECONDARY = colors.HexColor("#fbe9e7")

    c.setFillColor(PRIMARY)

    c.rect(
        0,
        H-58*mm,
        W,
        58*mm,
        fill=1,
        stroke=0
    )

    c.setStrokeColor(
        colors.HexColor("#d4af37")
    )

    c.setLineWidth(2)

    c.line(
        10*mm,
        H-60*mm,
        W-10*mm,
        H-60*mm
    )

    c.setFillColor(SECONDARY)

    c.rect(
        0,
        H-85*mm,
        W,
        24*mm,
        fill=1,
        stroke=0
    )

    return PRIMARY, SECONDARY


# =====================================================
# MAIN PDF ENGINE
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
    # QR CODE GENERATION
    # =================================================

    qr_url = (
        f"https://rx.vennovahealth.com/rx/"
        f"{visit.get('token')}"
    )

    qr = qrcode.make(qr_url)

    buffer = BytesIO()

    qr.save(buffer)

    buffer.seek(0)

    qr_image = Image(buffer)

    qr_image.width = 100
    qr_image.height = 100

    # =================================================
    # THEME ENGINE
    # =================================================

    theme = clinic.get(
        "prescription_theme",
        "CLASSIC_BLUE"
    )

    if theme == "CLASSIC_BLUE":

        PRIMARY, SECONDARY = draw_classic_blue(
            c,
            W,
            H
        )

    elif theme == "GREEN_MODERN":

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

                15*mm,
                H-52*mm,

                width=30*mm,
                height=30*mm,

                preserveAspectRatio=True,

                mask="auto"
            )

        except Exception as e:

            logger.warning(
                f"Logo draw error: {e}"
            )

    # =================================================
    # CLINIC INFO
    # =================================================

    c.setFillColor(colors.white)

    c.setFont(
        "Helvetica-Bold",
        16
    )

    c.drawString(
        55*mm,
        H-22*mm,
        clinic.get("name", "Clinic")
    )

    c.setFont(
        "Helvetica",
        10
    )

    c.drawString(
        55*mm,
        H-31*mm,
        f"Dr. {doctor.get('name', '')}"
    )

    c.drawString(
        55*mm,
        H-38*mm,
        doctor.get(
            "qualification",
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
        15*mm,
        H-70*mm,
        f"Patient: "
        f"{patient.get('name', '')}"
    )

    c.drawString(
        100*mm,
        H-70*mm,
        f"Age/Gender: "
        f"{patient.get('age', '')} / "
        f"{patient.get('gender', '')}"
    )

    c.drawString(
        160*mm,
        H-70*mm,
        datetime.now().strftime(
            "%d %b %Y"
        )
    )

    # =================================================
    # QR CODE DRAW
    # =================================================

    try:

        c.drawImage(

            ImageReader(buffer),

            W - 45*mm,
            H - 115*mm,

            width=28*mm,
            height=28*mm
        )

    except Exception as e:

        logger.warning(
            f"QR draw error: {e}"
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
        15*mm,
        H-105*mm,
        "℞"
    )

    # =================================================
    # CONTENT
    # =================================================

    visit_type = str(
        visit.get(
            "visit_type",
            ""
        )
    ).upper()

    if visit_type == "ALLOPATHY":

        _draw_allopathy_rx(

            c,

            visit,

            H-112*mm,

            W,

            PRIMARY,

            SECONDARY
        )

    else:

        _draw_homeopathy_rx(

            c,

            visit,

            H-112*mm,

            W,

            PRIMARY
        )

    # =================================================
    # FOOTER
    # =================================================

    c.setFont(
        "Helvetica",
        7
    )

    c.setFillColor(TEXT_GREY)

    c.drawCentredString(
        W/2,
        10*mm,
        "Powered by Vennova Clinic OS"
    )

    c.save()

    return buf.getvalue()