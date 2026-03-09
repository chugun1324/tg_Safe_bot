from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_nda_pdf(
    order_id: int,
    customer_name: str,
    artist_name: str,
    work_title: str,
    price_rub: int,
) -> bytes:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    lines = [
        "NDA / Non-Disclosure Agreement (Template)",
        "",
        f"Date: {datetime.now().strftime('%Y-%m-%d')}",
        f"Order ID: {order_id}",
        "",
        f"Customer: {customer_name}",
        f"Artist: {artist_name}",
        f"Commission title: {work_title}",
        f"Contract value: {price_rub} RUB",
        "",
        "1. Artist and Customer agree not to disclose commission files, drafts, and references",
        "   to any third parties without explicit written consent.",
        "2. Customer is prohibited from publishing or transferring preview files before final release.",
        "3. Final rights transfer follows explicit terms agreed in chat and platform rules.",
        "4. Breach may lead to claim, refund request, and platform sanctions (ban/blacklist).",
        "",
        "Signatures:",
        "Customer: ______________________",
        "Artist:   ______________________",
    ]

    y = height - 50
    pdf.setFont("Helvetica", 12)
    for line in lines:
        pdf.drawString(40, y, line)
        y -= 20

    pdf.showPage()
    pdf.save()
    return buf.getvalue()
