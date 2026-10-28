"""
Billing math and roster grouping.

Each client is quoted one all-in monthly amount. That amount is split into
an untaxed portion (e.g. rent) and a taxed portion (e.g. services), so that
the two invoices always add back up to exactly what the client was quoted.
"""


def split_amount(total, untaxed_share=0.8, tax_rate=0.16):
    """Split an all-in (post-tax) amount into untaxed and taxed invoice lines.

    With untaxed_share=0.8 and tax_rate=0.16:
        base     = total / (0.8 + 0.2 * 1.16) = total / 1.032
        subtotal = round(base * 0.2)
        tax      = round(subtotal * 0.16)
        untaxed  = total - (subtotal + tax)

    The untaxed line absorbs the rounding, so untaxed + subtotal + tax == total
    to the last unit, every time.
    """
    taxed_share = 1 - untaxed_share
    base = total / (untaxed_share + taxed_share * (1 + tax_rate))
    taxed_subtotal = round(base * taxed_share)
    tax = round(taxed_subtotal * tax_rate)
    return {
        "untaxed": total - taxed_subtotal - tax,
        "taxed_subtotal": taxed_subtotal,
        "tax": tax,
        "taxed_total": taxed_subtotal + tax,
    }


def group_roster(rows, untaxed_share=0.8, tax_rate=0.16, day_filter=None):
    """Group roster rows into one invoice pair per client.

    rows: dicts with client, email, line_item, amount, item_type, invoice_day,
    next_invoice_no. Rows sharing client + email + invoice_day become one
    multi-line untaxed invoice and one multi-line taxed invoice.
    item_type "Untaxed Only" puts the whole amount on the untaxed invoice
    (for flat fees that never carry tax).
    """
    groups = {}
    for row in rows:
        if not row.get("client") or row.get("amount") in (None, ""):
            continue
        if day_filter is not None and row.get("invoice_day") != day_filter:
            continue

        key = (row["client"], row.get("email"), row.get("invoice_day"))
        group = groups.setdefault(key, {
            "client": row["client"],
            "email": row.get("email"),
            "invoice_day": row.get("invoice_day") or 1,
            "next_invoice_no": int(row.get("next_invoice_no") or 1),
            "untaxed_items": [],
            "taxed_items": [],
            "lines": [],
            "row_indexes": [],
        })

        desc = str(row["line_item"])
        if row.get("item_type") == "Untaxed Only":
            split = {"untaxed": row["amount"], "taxed_subtotal": 0, "tax": 0, "taxed_total": 0}
        else:
            split = split_amount(row["amount"], untaxed_share, tax_rate)
            group["taxed_items"].append({"desc": desc, "qty": 1, "unit_price": split["taxed_subtotal"]})
        group["untaxed_items"].append({"desc": desc, "qty": 1, "unit_price": split["untaxed"]})
        group["lines"].append(dict(split, desc=desc, amount=row["amount"]))
        group["row_indexes"].append(row.get("row_index"))

    return list(groups.values())
