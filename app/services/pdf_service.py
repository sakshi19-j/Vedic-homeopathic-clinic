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
        doctor_name
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
        f"Amount Paid: Rs. {amount}"
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
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    PRIMARY = colors.HexColor("#5B21B6")   # deep purple
    LIGHT   = colors.HexColor("#EDE9FE")   # pale lavender
    TEXT    = colors.HexColor("#1F2937")

    # ---------- Decorative curve (top-right wave) ----------
    c.saveState()
    p = c.beginPath()
    p.moveTo(W, H)
    p.lineTo(W - 70*mm, H)
    p.curveTo(W - 40*mm, H - 10*mm, W - 20*mm, H - 25*mm, W, H - 55*mm)
    p.close()
    c.setFillColor(colors.HexColor("#C4B5FD"))
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()

    # ---------- Clinic name ----------
    c.setFillColor(PRIMARY)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(15*mm, H - 30*mm, clinic.get("name", "Clinic").upper())
    c.setLineWidth(2)
    c.line(15*mm, H - 34*mm, 65*mm, H - 34*mm)

    # ---------- Logo (top-right of header) ----------
    logo = _load_image(clinic.get("logo_url"))
    if logo:
        try:
            c.drawImage(
                logo, W - 45*mm, H - 40*mm,
                width=25*mm, height=25*mm,
                preserveAspectRatio=True, mask="auto"
            )
        except Exception as e:
            logger.warning(f"Logo draw error: {e}")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15*mm, H - 44*mm, f"Dr. {doctor.get('name', 'Doctor')}")
    c.setFont("Helvetica", 10)
    c.drawString(15*mm, H - 50*mm, doctor.get("qualification", ""))

    # ---------- Contact block (right) ----------
    c.setFont("Helvetica", 9)
    c.drawString(120*mm, H - 22*mm, clinic.get("phone", ""))
    c.drawString(120*mm, H - 29*mm, clinic.get("email", ""))
    c.drawString(120*mm, H - 36*mm, clinic.get("address", ""))

    # ---------- Patient info bar ----------
    y_bar = H - 68*mm
    c.setFillColor(LIGHT)
    c.roundRect(15*mm, y_bar, W - 30*mm, 20*mm, 3*mm, fill=1, stroke=0)
    c.setFillColor(PRIMARY)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(20*mm, y_bar + 14*mm, "PATIENT NAME")
    c.drawString(90*mm, y_bar + 14*mm, "DATE")
    c.drawString(140*mm, y_bar + 14*mm, "AGE / GENDER")
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20*mm, y_bar + 6*mm, patient.get("name", ""))
    c.setFont("Helvetica", 11)
    c.drawString(90*mm, y_bar + 6*mm, datetime.now().strftime("%d %b %Y"))
    c.drawString(140*mm, y_bar + 6*mm, f"{patient.get('age','–')} / {patient.get('gender','–')}")

    # ---------- PRESCRIPTION tab ----------
    y_tab = y_bar - 14*mm
    c.setFillColor(PRIMARY)
    c.rect(15*mm, y_tab, 55*mm, 9*mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(19*mm, y_tab + 3*mm, "PRESCRIPTION")

    # ---------- Table ----------
    medicines = visit.get("medicines", [])
    col_x = [15*mm, 30*mm, 100*mm, 145*mm, W - 15*mm]
    row_y = y_tab - 2*mm
    c.setFillColor(LIGHT)
    c.rect(15*mm, row_y - 8*mm, W - 30*mm, 8*mm, fill=1, stroke=0)
    c.setFillColor(PRIMARY)
    c.setFont("Helvetica-Bold", 8)
    headers = ["Sr.", "Instruction / Test", "Timing", "Duration"]
    for i, h in enumerate(headers):
        c.drawString(col_x[i] + 2*mm, row_y - 5.5*mm, h)

    row_y -= 8*mm
    c.setStrokeColor(colors.HexColor("#DDD6FE"))
    for idx, med in enumerate(medicines, start=1):
        row_h = 14*mm
        c.rect(15*mm, row_y - row_h, W - 30*mm, row_h, stroke=1, fill=0)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col_x[0] + 2*mm, row_y - 6*mm, str(idx))
        c.drawString(col_x[1] + 2*mm, row_y - 5*mm, f"{med.get('name','')} {med.get('dosage','')}".strip())
        c.setFont("Helvetica", 9)
        c.drawString(col_x[1] + 2*mm, row_y - 10*mm, med.get("food_relation", ""))
        c.drawString(col_x[2] + 2*mm, row_y - 6*mm, med.get("timing", ""))
        c.drawString(col_x[3] + 2*mm, row_y - 6*mm, f"{med.get('duration','')} Days")
        row_y -= row_h

    # ---------- Advice box ----------
    advice_y = row_y - 8*mm
    c.setStrokeColor(colors.HexColor("#DDD6FE"))
    c.roundRect(15*mm, advice_y - 22*mm, W - 30*mm, 22*mm, 3*mm, stroke=1, fill=0)
    c.setFillColor(PRIMARY)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(19*mm, advice_y - 6*mm, "ADVICE:")
    c.setFillColor(TEXT)
    c.setFont("Helvetica", 9)
    c.drawString(19*mm, advice_y - 13*mm, visit.get("advice", ""))

    # ---------- Signature ----------
    sig_y = advice_y - 32*mm
    c.setStrokeColor(TEXT)
    c.line(W - 65*mm, sig_y, W - 20*mm, sig_y)
    c.setFont("Helvetica", 9)
    c.drawCentredString(W - 42*mm, sig_y - 5*mm, "Signature")

    # ---------- Footer (4 columns) ----------
    footer_y = 25*mm
    c.setFillColor(colors.HexColor("#F5F3FF"))
    c.rect(0, 0, W, footer_y + 5*mm, fill=1, stroke=0)
    labels = [("CARE", "Compassionate care"), ("TRUST", "Trusted homeopathy"),
              ("NATURAL", "Natural healing"), ("WELLNESS", "Your wellness first")]
    col_w = W / 4
    for i, (title, sub) in enumerate(labels):
        x = i * col_w + 15*mm
        c.setFillColor(PRIMARY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, footer_y, title)
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 7)
        c.drawString(x, footer_y - 5*mm, sub)

    c.setFillColor(PRIMARY)
    c.rect(0, 0, W, 4*mm, fill=1, stroke=0)

    c.save()
    pdf = buf.getvalue()
    buf.close()
    return pdf