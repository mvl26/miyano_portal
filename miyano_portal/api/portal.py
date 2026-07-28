import frappe
from miyano_portal.portal_context import get_portal_customer, remaining_qty


def _get_outstanding(customer: str) -> float:
    """Sum of unpaid GL Entry balance for this customer across companies.

    Customer.outstanding_amount is not a real field/column in this build,
    so compute it directly from GL Entry instead of frappe.db.get_value.
    """
    total = frappe.db.sql(
        """select sum(debit_in_account_currency) - sum(credit_in_account_currency)
           from `tabGL Entry`
           where party_type='Customer' and party=%s and is_cancelled=0""",
        customer,
    )[0][0]
    return float(total or 0)


@frappe.whitelist()
def portal_me() -> dict:
    customer = get_portal_customer()
    return {
        "customer": customer,
        "customer_name": frappe.db.get_value("Customer", customer, "customer_name"),
        "outstanding": _get_outstanding(customer),
    }


@frappe.whitelist()
def portal_contracts() -> list:
    customer = get_portal_customer()
    today = frappe.utils.today()
    rows = frappe.get_all(
        "Blanket Order",
        filters={
            "customer": customer,
            "blanket_order_type": "Selling",
            "to_date": [">=", today],
        },
        fields=["name", "from_date", "to_date"],
        order_by="to_date asc",
    )
    for r in rows:
        agg = frappe.db.sql(
            """select sum(qty) q, sum(ordered_qty) o
               from `tabBlanket Order Item` where parent=%s""",
            r["name"],
        )[0]
        total, ordered = float(agg[0] or 0), float(agg[1] or 0)
        r["used_pct"] = round(ordered / total * 100, 1) if total else 0
    return rows


@frappe.whitelist()
def portal_catalog(contract: str) -> list:
    customer = get_portal_customer()
    # isolation: the contract must belong to the caller's customer
    if frappe.db.get_value("Blanket Order", contract, "customer") != customer:
        raise frappe.PermissionError("Hợp đồng không thuộc đơn vị của bạn.")
    price_list = frappe.db.get_value("Customer", customer, "default_price_list")
    out = []
    for row in frappe.get_all(
        "Blanket Order Item",
        filters={"parent": contract},
        fields=["item_code", "rate"],
    ):
        item = frappe.db.get_value(
            "Item", row["item_code"], ["item_name", "stock_uom"], as_dict=True
        )
        rate = frappe.db.get_value(
            "Item Price",
            {"item_code": row["item_code"], "price_list": price_list, "selling": 1},
            "price_list_rate",
        ) or row["rate"]
        out.append({
            "item_code": row["item_code"],
            "item_name": item.item_name if item else row["item_code"],
            "uom": item.stock_uom if item else "",
            "rate": float(rate),
            "vat_pct": 0,
            "remaining": remaining_qty(contract, row["item_code"]),
        })
    return out


@frappe.whitelist()
def portal_order_place(contract, items, po=None, delivery_date=None, note=None) -> dict:
    customer = get_portal_customer()
    bo = frappe.db.get_value(
        "Blanket Order", contract, ["customer", "company"], as_dict=True
    )
    if not bo or bo.customer != customer:
        raise frappe.PermissionError("Hợp đồng không thuộc đơn vị của bạn.")
    if isinstance(items, str):
        items = frappe.parse_json(items)
    if not items:
        frappe.throw("Giỏ hàng trống.")

    price_list = frappe.db.get_value("Customer", customer, "default_price_list")
    delivery_date = delivery_date or frappe.utils.add_days(frappe.utils.today(), 2)

    errors = []
    for line in items:
        qty = float(line.get("qty") or 0)
        if qty <= 0:
            errors.append(f"{line.get('item_code')}: số lượng phải > 0")
            continue
        rem = remaining_qty(contract, line["item_code"])
        if qty > rem:
            errors.append(f"{line['item_code']}: vượt hạn mức (còn {rem:g})")
    if errors:
        frappe.throw("<br>".join(errors), frappe.ValidationError)

    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = bo.company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = delivery_date
    so.selling_price_list = price_list
    so.custom_nguon_don = "Client Portal"
    so.custom_hdnt = contract
    so.custom_so_po_khach = po
    so.custom_yeu_cau_khach = note
    for line in items:
        rate = frappe.db.get_value(
            "Item Price",
            {"item_code": line["item_code"], "price_list": price_list, "selling": 1},
            "price_list_rate",
        )
        so.append("items", {
            "item_code": line["item_code"],
            "qty": float(line["qty"]),
            "rate": rate,
            "delivery_date": delivery_date,
            "blanket_order": contract,
        })
    so.flags.ignore_permissions = True
    so.insert(ignore_permissions=True)
    return {"sales_order": so.name, "total": float(so.grand_total)}
