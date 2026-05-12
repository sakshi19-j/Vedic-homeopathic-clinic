import os
import uuid
import json
import io
import logging
import tempfile

from datetime import datetime
from reportlab.lib.pagesizes import A5, A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.schemas.billing import ReceiptData

logger = logging.getLogger(__name__)


# =====================================================
# BRAND COLORS
# =====================================================

VENNOVA_BLUE  = colors.HexColor("#1a237e")
VENNOVA_GREEN = colors.HexColor("#00897b")
VENNOVA_LIGHT = colors.HexColor("#e8eaf6")
TEXT_DARK     = colors.HexColor("#1a1a2e")
TEXT_GREY     = colors.HexColor("#666666")


# =====================================================
# IMAGE LOADER — handles both local paths + URLs
# =====================================================

def _load_image(url_or_path: str):
    """
    FIX: os.path.exists() always fails for Supabase URLs.
    This downloads remote images and returns an ImageReader.
    Returns None if unavailable — PDF renders without image.
    """
    if not url_or_path:
        return None

    try:
        if url_or_path.startswith("http"):
            import httpx
            resp = httpx.get(url_or_path, timeout=5.0)
            if resp.status_code == 200:
                return ImageReader(io.BytesIO(resp.content))
            logger.warning(f"Image download failed: {url_or_path} → {resp.status_code}")
            return None
        else:
            if os.path.exists(url_or_path):
                return ImageReader(url_or_path)
            return None
    except Exception as e:
        logger.warning(f"Image load error: {e}")
        return None


# =====================================================
# ENUM VALUE EXTRACTOR
# =====================================================

def _enum_value(val) -> str:
    """
    FIX: str(enum) returns 'VisitType.ALLOPATHY'.
    This returns just 'ALLOPATHY'.
    """
    if val is None:
        return ""
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)


# =====================================================
# DOCTOR TITLE BY VISIT TYPE
# =====================================================

def _doctor_title(visit_type: str, qualification: str) -> str:
    """
    Dynamic title so allopathy prescriptions don't
    say 'Homoeopathic Consultant'.
    """
    vt = visit_type.upper() if visit_type else "HOMEOPATHY"
    qual = qualification or ""

    if "BHMS" in qual.upper() or "DHMS" in qual.upper() or vt == "HOMEOPATHY":
        return "Homoeopathic Consultant"
    elif "BAMS" in qual.upper() or vt == "AYURVEDIC":
        return "Ayurvedic Consultant"
    else:
        return "Medical Consultant"


# =====================================================
# RECEIPT PDF GENERATOR
# =====================================================

def generate_receipt_pdf(data: ReceiptData) -> str:
    """
    Generate payment receipt PDF.
    Railway-safe: saves to /tmp/ only.
    """
    output_path = f"/tmp/receipt_{str(uuid.uuid4())[:8]}.pdf"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A5,
        topMargin=10*mm, bottomMargin=10*mm,
        leftMargin=12*mm, rightMargin=12*mm
    )

    styles  = getSampleStyleSheet()
    content = []

    # ── Clinic header ─────────────────────────────────
    content.append(Paragraph(
        f'"{data.clinic_name}"',
        ParagraphStyle("h", parent=styles["Normal"],
            fontSize=14, fontName="Helvetica-Bold",
            alignment=TA_CENTER, textColor=VENNOVA_BLUE, spaceAfter=2)
    ))
    content.append(Paragraph(
        f"{data.doctor_name} | {data.qualification or 'B.H.M.S.'}",
        ParagraphStyle("sub", parent=styles["Normal"],
            fontSize=9, alignment=TA_CENTER, textColor=TEXT_GREY, spaceAfter=1)
    ))

    # FIX: add registration number for legal validity
    reg = getattr(data, "reg_number", None)
    if reg:
        content.append(Paragraph(
            f"Reg. No: {reg}",
            ParagraphStyle("rn", parent=styles["Normal"],
                fontSize=8, alignment=TA_CENTER, textColor=TEXT_GREY, spaceAfter=1)
        ))

    for field, label in [
        (data.clinic_address, None),
        (data.clinic_phone,   "Mobile: "),
        (data.clinic_timings, "Timings: ")
    ]:
        if field:
            content.append(Paragraph(
                f"{label or ''}{field}",
                ParagraphStyle("inf", parent=styles["Normal"],
                    fontSize=8, alignment=TA_CENTER, textColor=TEXT_GREY, spaceAfter=1)
            ))

    content.append(HRFlowable(width="100%", thickness=1.5,
        color=VENNOVA_BLUE, spaceAfter=6))

    content.append(Paragraph(
        "PAYMENT RECEIPT",
        ParagraphStyle("title", parent=styles["Normal"],
            fontSize=11, fontName="Helvetica-Bold",
            alignment=TA_CENTER, textColor=VENNOVA_BLUE, spaceAfter=8)
    ))

    lbl = ParagraphStyle("lbl", parent=styles["Normal"],
        fontSize=9, fontName="Helvetica-Bold")
    val = ParagraphStyle("val", parent=styles["Normal"], fontSize=9)

    details = [
        [Paragraph("Receipt No:", lbl), Paragraph(data.receipt_no, val),
         Paragraph("Date:", lbl),       Paragraph(data.visit_date, val)],
        [Paragraph("Patient:", lbl),    Paragraph(data.patient_name, val),
         Paragraph("Reg. No:", lbl),    Paragraph(str(data.reg_no), val)],
        [Paragraph("Age/Gender:", lbl),
         Paragraph(f"{data.patient_age or '-'} / {data.patient_gender or '-'}", val),
         Paragraph("Contact:", lbl),    Paragraph(data.patient_phone or "-", val)],
        [Paragraph("Visit Type:", lbl), Paragraph(data.visit_type, val),
         Paragraph("Complaint:", lbl),  Paragraph(data.chief_complaint or "-", val)]
    ]

    dt = Table(details, colWidths=[28*mm, 40*mm, 25*mm, 40*mm])
    dt.setStyle(TableStyle([
        ("VALIGN",         (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [VENNOVA_LIGHT, colors.white]),
        ("TOPPADDING",     (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 4),
        ("LEFTPADDING",    (0,0), (-1,-1), 3),
    ]))
    content.append(dt)
    content.append(Spacer(1, 8*mm))

    payment = [
        ["Consultation Fee", f"Rs. {data.amount:.2f}"],
        ["Payment Mode",     data.payment_mode],
        ["Amount Paid",      f"Rs. {data.amount:.2f}"],
    ]
    pt = Table(payment, colWidths=[80*mm, 50*mm])
    pt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),  (-1,0),  VENNOVA_BLUE),
        ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
        ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
        ("BACKGROUND",    (0,2),  (-1,2),  colors.HexColor("#e8f5e9")),
        ("FONTNAME",      (0,2),  (-1,2),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),  (-1,-1), 10),
        ("GRID",          (0,0),  (-1,-1), 0.5, colors.grey),
        ("TOPPADDING",    (0,0),  (-1,-1), 6),
        ("BOTTOMPADDING", (0,0),  (-1,-1), 6),
        ("LEFTPADDING",   (0,0),  (-1,-1), 8),
        ("ALIGN",         (1,0),  (1,-1),  "RIGHT"),
    ]))
    content.append(pt)
    content.append(Spacer(1, 8*mm))

    # FIX: dynamic doctor title
    doc_title = _doctor_title(data.visit_type, data.qualification)

    sig_data = [[
        Paragraph("Patient's Signature: _______________",
            ParagraphStyle("sl", parent=styles["Normal"], fontSize=8)),
        Paragraph(
            f"<b>{data.doctor_name}</b><br/>"
            f"{data.qualification or 'B.H.M.S.'}<br/>"
            f"{doc_title}",
            ParagraphStyle("sr", parent=styles["Normal"],
                fontSize=8, alignment=TA_RIGHT))
    ]]
    content.append(Table(sig_data, colWidths=[80*mm, 53*mm]))
    content.append(Spacer(1, 6*mm))

    content.append(HRFlowable(width="100%", thickness=0.5,
        color=colors.grey, spaceAfter=3))
    content.append(Paragraph(
        "Thank you for visiting. Please preserve this receipt.",
        ParagraphStyle("f1", parent=styles["Normal"],
            fontSize=7, alignment=TA_CENTER, textColor=TEXT_GREY)
    ))
    content.append(Paragraph(
        "Powered by <b>Vennova</b> — Clinic Growth Engine",
        ParagraphStyle("f2", parent=styles["Normal"],
            fontSize=7, alignment=TA_CENTER, textColor=VENNOVA_BLUE)
    ))

    doc.build(content)
    return output_path


# =====================================================
# PRESCRIPTION PDF — HOMEOPATHY LAYOUT
# =====================================================

def _draw_homeopathy_rx(c, visit: dict, y_start: float, W: float):
    """
    Homeopathy layout: Remedy, Potency, Repetition,
    Rubrics list, Miasm — structured for case records.
    """
    y = y_start

    hc = visit.get("homeopathy_case", {})

    # Chief complaint
    chief = visit.get("chief_complaint", "")
    if chief:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColorRGB(0.12, 0.18, 0.35)
        c.drawString(15*mm, y, "Chief Complaint:")
        c.setFont("Helvetica", 10)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.drawString(62*mm, y, chief)
        y -= 8*mm

    # Prescription box
    rx_items = [
        ("Remedy",     hc.get("remedy", "")),
        ("Potency",    hc.get("potency", "")),
        ("Repetition", hc.get("repetition", "")),
        ("Miasm",      hc.get("miasm", "")),
    ]

    for label, value in rx_items:
        if value:
            c.setFont("Helvetica-Bold", 10)
            c.setFillColorRGB(0.12, 0.18, 0.35)
            c.drawString(15*mm, y, f"{label}:")
            c.setFont("Helvetica", 10)
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.drawString(55*mm, y, str(value))
            y -= 7*mm

    # Rubrics
    rubrics = visit.get("rubrics", [])
    if rubrics:
        y -= 3*mm
        c.setFont("Helvetica-Bold", 9)
        c.setFillColorRGB(0.12, 0.18, 0.35)
        c.drawString(15*mm, y, "Rubrics:")
        y -= 6*mm
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.3, 0.3, 0.3)
        for r in rubrics[:8]:  # cap at 8 rubrics shown
            rubric_text = r if isinstance(r, str) else r.get("rubric", str(r))
            c.drawString(20*mm, y, f"• {rubric_text}")
            y -= 5*mm
            if y < 60*mm:
                break

    # Notes
    notes = visit.get("notes", "")
    if notes:
        y -= 3*mm
        c.setFont("Helvetica-Bold", 9)
        c.setFillColorRGB(0.12, 0.18, 0.35)
        c.drawString(15*mm, y, "Notes:")
        y -= 6*mm
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        for line in notes.split("\n"):
            if line.strip():
                c.drawString(20*mm, y, line[:90])
                y -= 5*mm
                if y < 60*mm:
                    break

    return y


def _draw_allopathy_rx(c, visit: dict, y_start: float, W: float):
    """
    Allopathy layout: medicines as numbered table rows,
    advice block, next visit date.
    """
    y = y_start

    # Chief complaint
    chief = visit.get("chief_complaint", "")
    if chief:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColorRGB(0.12, 0.18, 0.35)
        c.drawString(15*mm, y, "Chief Complaint:")
        c.setFont("Helvetica", 10)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.drawString(62*mm, y, chief)
        y -= 8*mm

    # Diagnosis
    diagnosis = visit.get("diagnosis", "")
    if diagnosis:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColorRGB(0.12, 0.18, 0.35)
        c.drawString(15*mm, y, "Diagnosis:")
        c.setFont("Helvetica", 10)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.drawString(55*mm, y, diagnosis)
        y -= 8*mm

    # Medicines header
    medicines = visit.get("medicines", [])
    if medicines:
        y -= 2*mm
        c.setFillColorRGB(0.12, 0.18, 0.35)
        c.rect(15*mm, y-1*mm, W-30*mm, 7*mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(17*mm, y+1*mm,  "#")
        c.drawString(25*mm, y+1*mm,  "Medicine")
        c.drawString(90*mm, y+1*mm,  "Dosage")
        c.drawString(120*mm, y+1*mm, "Frequency")
        c.drawString(155*mm, y+1*mm, "Duration")
        y -= 8*mm

        for i, med in enumerate(medicines, 1):
            bg = colors.HexColor("#f0f4ff") if i % 2 == 0 else colors.white
            c.setFillColor(bg)
            c.rect(15*mm, y-1*mm, W-30*mm, 6*mm, fill=1, stroke=0)
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont("Helvetica", 9)
            c.drawString(17*mm,  y+1*mm, str(i))
            c.drawString(25*mm,  y+1*mm, str(med.get("name", ""))[:28])
            c.drawString(90*mm,  y+1*mm, str(med.get("dosage", ""))[:12])
            c.drawString(120*mm, y+1*mm, str(med.get("frequency", ""))[:16])
            c.drawString(155*mm, y+1*mm, str(med.get("duration", ""))[:12])
            y -= 6*mm
            if y < 60*mm:
                c.showPage()
                y = 250*mm

    # Advice
    advice = visit.get("advice", "")
    if advice:
        y -= 4*mm
        c.setFont("Helvetica-Bold", 9)
        c.setFillColorRGB(0.12, 0.18, 0.35)
        c.drawString(15*mm, y, "Advice:")
        y -= 6*mm
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        for line in advice.split("\n"):
            if line.strip():
                c.drawString(20*mm, y, line[:90])
                y -= 5*mm

    # Next visit date
    next_visit = visit.get("next_visit_date", "")
    if next_visit:
        y -= 4*mm
        c.setFont("Helvetica-Bold", 10)
        c.setFillColorRGB(0.0, 0.53, 0.48)
        c.drawString(15*mm, y,
            f"Next Visit: {next_visit}")

    return y


# =====================================================
# PRESCRIPTION PDF — MAIN GENERATOR
# =====================================================

def generate_prescription_pdf(
    visit: dict,
    clinic: dict,
    doctor: dict,
    patient: dict
) -> bytes:
    """
    Premium A4 prescription PDF.
    Separate layouts for Homeopathy vs Allopathy.
    Loads logo + signature from Supabase URLs safely.
    """
    buf    = io.BytesIO()
    c      = canvas.Canvas(buf, pagesize=A4)
    W, H   = A4

    visit_type = _enum_value(
        visit.get("visit_type") or visit.get("type")
    ).upper()
    # Handle "VISITTYPE.ALLOPATHY" style just in case
    if "." in visit_type:
        visit_type = visit_type.split(".")[-1]

    # ── Header band ───────────────────────────────────
    c.setFillColorRGB(0.12, 0.18, 0.35)
    c.rect(0, H-60*mm, W, 60*mm, fill=1, stroke=0)

    # ── Logo ─────────────────────────────────────────
    logo = _load_image(clinic.get("logo_url"))
    if logo:
        try:
            c.drawImage(logo, 15*mm, H-52*mm,
                width=30*mm, height=30*mm,
                preserveAspectRatio=True, mask="auto")
        except Exception as e:
            logger.warning(f"Logo draw error: {e}")

    # ── Clinic info ───────────────────────────────────
    left = 52*mm if logo else 15*mm

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(left, H-22*mm, clinic.get("name", "Clinic"))

    c.setFont("Helvetica", 10)
    c.drawString(left, H-31*mm,
        f"Dr. {doctor.get('name', '')}  ·  "
        f"{doctor.get('qualification', '')}")
    c.drawString(left, H-39*mm, clinic.get("address", ""))
    c.drawString(left, H-47*mm,
        f"Ph: {clinic.get('phone', '')}  ·  "
        f"Reg: {clinic.get('reg_number', '')}")
    c.drawString(left, H-54*mm,
        f"Timings: {clinic.get('timings', '')}")

    # ── Patient info band ─────────────────────────────
    c.setFillColorRGB(0.93, 0.95, 0.98)
    c.rect(0, H-85*mm, W, 25*mm, fill=1, stroke=0)

    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(15*mm, H-69*mm,
        f"Patient:  {patient.get('name', '')}")
    c.drawString(100*mm, H-69*mm,
        f"Age / Sex:  "
        f"{patient.get('age', '')} / "
        f"{_enum_value(patient.get('gender', ''))}")
    c.drawString(160*mm, H-69*mm,
        f"Date:  {datetime.now().strftime('%d %b %Y')}")

    c.setFont("Helvetica", 9)
    c.drawString(15*mm, H-77*mm,
        f"Reg No: {patient.get('reg_no', '')}  "
        f"·  Visit ID: {str(visit.get('id', ''))[:8]}")

    # ── Rx symbol ────────────────────────────────────
    c.setFont("Helvetica-Bold", 28)
    c.setFillColorRGB(0.12, 0.18, 0.35)
    c.drawString(15*mm, H-106*mm, "℞")

    y_content = H - 112*mm

    # ── Visit-type specific layout ────────────────────
    if visit_type == "ALLOPATHY":
        y_end = _draw_allopathy_rx(c, visit, y_content, W)
    else:
        # Homeopathy and Ayurvedic both use homeopathy layout
        y_end = _draw_homeopathy_rx(c, visit, y_content, W)

    # ── Signature block ───────────────────────────────
    sig = _load_image(clinic.get("signature_url"))
    if sig:
        try:
            c.drawImage(sig, W-68*mm, 36*mm,
                width=48*mm, height=18*mm,
                preserveAspectRatio=True, mask="auto")
        except Exception as e:
            logger.warning(f"Signature draw error: {e}")

    # Signature line + doctor name
    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    c.line(W-68*mm, 34*mm, W-20*mm, 34*mm)

    doc_title = _doctor_title(visit_type, doctor.get("qualification", ""))

    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(W-68*mm, 28*mm, f"Dr. {doctor.get('name', '')}")

    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(W-68*mm, 23*mm, doctor.get("qualification", ""))
    c.drawString(W-68*mm, 18*mm, doc_title)

    # ── Footer ────────────────────────────────────────
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(W/2, 12*mm,
        "This is a computer-generated prescription — Vennova Clinic OS")
    c.drawCentredString(W/2, 8*mm,
        f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}")

    c.save()
    return buf.getvalue()