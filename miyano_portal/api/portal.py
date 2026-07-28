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

    # Aggregate the incoming cart by item_code so duplicate lines for the same
    # item can't each pass the quota check individually while together
    # exceeding the remaining quota (duplicate-line quota bypass).
    aggregated = {}
    for line in items:
        qty = float(line.get("qty") or 0)
        item_code = line.get("item_code")
        aggregated[item_code] = aggregated.get(item_code, 0) + qty

    errors = []
    for item_code, qty in aggregated.items():
        if qty <= 0:
            errors.append(f"{item_code}: số lượng phải > 0")
            continue
        rem = remaining_qty(contract, item_code)
        if qty > rem:
            errors.append(f"{item_code}: vượt hạn mức (còn {rem:g})")
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
    for item_code, qty in aggregated.items():
        rate = frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "price_list": price_list, "selling": 1},
            "price_list_rate",
        )
        if not rate:
            frappe.throw(f"Không tìm thấy giá bán cho mặt hàng {item_code}.")
        so.append("items", {
            "item_code": item_code,
            "qty": qty,
            "rate": rate,
            "delivery_date": delivery_date,
            "blanket_order": contract,
            "against_blanket_order": 1,
        })
    so.flags.ignore_permissions = True
    so.insert(ignore_permissions=True)
    return {"sales_order": so.name, "total": float(so.grand_total)}


STATUS_VI = {
    "Draft": "Chờ xác nhận",
    "To Deliver and Bill": "Đang xử lý",
    "To Bill": "Đang xử lý",
    "To Deliver": "Đang giao",
    "Completed": "Hoàn thành",
    "Cancelled": "Đã huỷ",
    "Closed": "Đã huỷ",
}


def _status_vi(status):
    return STATUS_VI.get(status, status)


@frappe.whitelist()
def portal_order_history(limit=20, start=0) -> list:
    rows = frappe.get_list(
        "Sales Order",
        fields=["name", "transaction_date", "grand_total", "status", "per_delivered"],
        order_by="transaction_date desc, creation desc",
        limit_page_length=int(limit), limit_start=int(start),
    )
    for r in rows:
        r["status_vi"] = _status_vi(r.pop("status"))
    return rows


@frappe.whitelist()
def portal_order_track(order) -> dict:
    so = frappe.get_doc("Sales Order", order)
    # frappe.get_doc does not auto-check permissions on load; check_permission()
    # is what actually invokes the has_permission hook (Task 5) that scopes
    # this to the caller's own customer.
    so.check_permission("read")
    delivered = (so.per_delivered or 0) > 0
    billed = (so.per_billed or 0) > 0
    milestones = [
        {"key": "ordered", "label": "Đặt hàng", "done": True},
        {"key": "confirmed", "label": "Xác nhận", "done": so.docstatus == 1},
        {"key": "delivering", "label": "Giao hàng", "done": delivered},
        {"key": "invoiced", "label": "Hoá đơn", "done": billed},
    ]
    return {
        "order": so.name,
        "status_vi": _status_vi(so.status),
        "milestones": milestones,
        "items": [
            {"item_code": i.item_code, "qty": i.qty, "delivered_qty": i.delivered_qty}
            for i in so.items
        ],
    }


@frappe.whitelist()
def portal_deliveries(limit=20, start=0) -> list:
    return frappe.get_list(
        "Delivery Note",
        fields=["name", "posting_date", "status"],
        order_by="posting_date desc",
        limit_page_length=int(limit), limit_start=int(start),
    )


@frappe.whitelist()
def portal_invoices(limit=20, start=0) -> list:
    rows = frappe.get_list(
        "Sales Invoice",
        fields=["name", "posting_date", "grand_total", "outstanding_amount", "status"],
        order_by="posting_date desc",
        limit_page_length=int(limit), limit_start=int(start),
    )
    for r in rows:
        r["status_vi"] = _status_vi(r.pop("status"))
    return rows


@frappe.whitelist()
def portal_request_cancel(order, reason) -> dict:
    so = frappe.get_doc("Sales Order", order)
    so.check_permission("read")
    if so.docstatus != 0:
        frappe.throw("Chỉ yêu cầu huỷ được khi đơn còn Chờ xác nhận.")
    so.add_comment("Comment", f"[Portal] Khách yêu cầu huỷ: {reason}")
    frappe.get_doc({
        "doctype": "ToDo", "description": f"Khách yêu cầu huỷ {order}: {reason}",
        "reference_type": "Sales Order", "reference_name": order,
    }).insert(ignore_permissions=True)
    return {"ok": True}
