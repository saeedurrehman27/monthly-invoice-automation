"""
Branded invoice PDF renderer (reportlab).

Draws a header band with the company name, a Billed-to / Invoice No. / Date
block, an item table, a Subtotal / Tax / Total Due box and a footer with the
company's contact details. Branding comes from the config file.
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

DARK_TEXT = colors.HexColor("#1A1A1A")
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def fmt_amount(n):
    """120000 -> '120,000'; keeps decimals only when they matter."""
    if abs(n - round(n)) < 0.005:
        return f"{round(n):,}"
    return f"{n:,.2f}"


def _right(c, x_right, y, text, font="Helvetica", size=11, color=DARK_TEXT):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x_right - stringWidth(text, font, size), y, text)


def generate_invoice(out_path, company, client_name, invoice_no, date_str,
                     items, tax_rate=0.0, tax_amount=None, title="INVOICE"):
    """Render one invoice. items: [{"desc", "qty", "unit_price"}, ...].

    tax_rate is shown on the invoice (0 for the untaxed invoice). tax_amount,
    when given, is the exact tax to charge; otherwise tax is tax_rate applied
    to the summed subtotal. Returns the subtotal, tax and total due.
    """
    brand = colors.HexColor(company.get("brand_color", "#2C4D8F"))
    tint = colors.HexColor(company.get("tint_color", "#EDF1F8"))
    currency = company.get("currency", "")

    lines = [dict(it, line_total=it["qty"] * it["unit_price"]) for it in items]
    subtotal = sum(it["line_total"] for it in lines)
    if tax_amount is not None:
        tax = tax_amount
    else:
        tax = round(subtotal * tax_rate) if tax_rate else 0
    total_due = subtotal + tax

    c = canvas.Canvas(out_path, pagesize=A4)
    c.setTitle(f"{title} {invoice_no} - {client_name}")

    # Background accent
    c.setFillColor(tint)
    c.circle(PAGE_W * 0.82, PAGE_H * 0.24, 170, stroke=0, fill=1)

    # Header band
    header_h = 34 * mm
    c.setFillColor(brand)
    c.rect(0, PAGE_H - header_h, PAGE_W, header_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(MARGIN, PAGE_H - 20 * mm, company["name"].upper())
    _right(c, PAGE_W - MARGIN, PAGE_H - 19 * mm, title, "Helvetica-Bold", 24, colors.white)

    # Billed to / invoice meta
    y = PAGE_H - header_h - 16 * mm
    c.setFillColor(brand)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, "Billed to:")
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica", 12)
    c.drawString(MARGIN + stringWidth("Billed to:", "Helvetica-Bold", 12) + 6, y, client_name)

    right = PAGE_W - MARGIN
    for label, value, row_y in (("Invoice No.", invoice_no, y), ("Date:", date_str, y - 8 * mm)):
        c.setFillColor(brand)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(right - stringWidth(label, "Helvetica-Bold", 11) - 40 * mm, row_y, label)
        _right(c, right, row_y, value)
        c.setStrokeColor(brand)
        c.line(right - 38 * mm, row_y - 3, right, row_y - 3)

    # Item table
    table_top = y - 30 * mm
    cols = {"ITEM": MARGIN, "QTY": 95 * mm, "UNIT PRICE": 130 * mm}
    c.setFillColor(brand)
    c.setFont("Helvetica-Bold", 11)
    for label, x in cols.items():
        c.drawString(x, table_top, label)
    _right(c, right, table_top, f"TOTAL ({currency})" if currency else "TOTAL", "Helvetica-Bold", 11, brand)
    c.setStrokeColor(brand)
    c.line(MARGIN, table_top - 4, right, table_top - 4)

    row_y = table_top - 12 * mm
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica", 11)
    for it in lines:
        c.drawString(cols["ITEM"], row_y, str(it["desc"]))
        c.drawString(cols["QTY"], row_y, str(it["qty"]))
        c.drawString(cols["UNIT PRICE"], row_y, fmt_amount(it["unit_price"]))
        _right(c, right, row_y, fmt_amount(it["line_total"]))
        row_y -= 8 * mm

    # Totals box
    totals_top = row_y - max(40 * mm, 60 * mm - (len(lines) - 1) * 8 * mm) + 8 * mm
    c.line(MARGIN, totals_top + 6 * mm, right, totals_top + 6 * mm)
    label_x = PAGE_W - 70 * mm
    tax_label = f"Tax ({tax_rate * 100:g}%)" if tax_rate else "Tax"
    for label, value, row_y in (("Subtotal", fmt_amount(subtotal), totals_top),
                                (tax_label, fmt_amount(tax) if tax_rate else "-", totals_top - 8 * mm)):
        c.setFillColor(brand)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(label_x, row_y, label)
        _right(c, right, row_y, value)
    c.setStrokeColor(brand)
    c.line(label_x, totals_top - 12 * mm, right, totals_top - 12 * mm)
    due_y = totals_top - 20 * mm
    c.setFillColor(brand)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(label_x, due_y, "Total Due")
    due = f"{currency} {fmt_amount(total_due)}".strip()
    _right(c, right, due_y, due, "Helvetica-Bold", 12)

    # Footer band
    footer_h = 16 * mm
    c.setFillColor(brand)
    c.rect(0, 0, PAGE_W, footer_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(MARGIN, footer_h - 6 * mm, company.get("address_line_1", ""))
    c.drawString(MARGIN, footer_h - 11 * mm, company.get("address_line_2", ""))
    _right(c, right, footer_h - 6 * mm, company.get("phone", ""), "Helvetica-Bold", 8, colors.white)
    _right(c, right, footer_h - 11 * mm, company.get("email", ""), "Helvetica-Bold", 8, colors.white)

    c.showPage()
    c.save()
    return {"subtotal": subtotal, "tax": tax, "total_due": total_due}
