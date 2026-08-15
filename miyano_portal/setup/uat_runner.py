"""UAT flow helpers — run the backend (Miyano-side) steps of the order-to-cash
flow via `bench execute` so each op commits only on success (unlike the IPython
console, which continues past exceptions). Test/UAT only; not wired into hooks.
"""

import json

import frappe


def submit_so(so_name: str) -> dict:
    """Miyano Sales confirms: drive the Client-Portal workflow to submit."""
    from frappe.model.workflow import apply_workflow, get_transitions

    so = frappe.get_doc("Sales Order", so_name)
    steps = []
    for _ in range(4):
        trans = get_transitions(so)
        if not trans or so.docstatus == 1:
            break
        action = trans[0]["action"]
        so = apply_workflow(so, action)
        steps.append((action, so.workflow_state, so.docstatus))
    so.reload()
    return {"so": so_name, "docstatus": so.docstatus,
            "workflow_state": so.workflow_state, "status": so.status, "steps": steps}


def bao_gia_gui_khach(so_name: str, gia_map: str | dict | None = None,
                       khop_map: str | dict | None = None) -> dict:
    """Miyano Sales (Mua lẻ): điền giá cho các dòng `items` theo `gia_map`
    ({item_code: rate}), khớp mã cho các dòng `custom_dat_ngoai` theo
    `khop_map` ({ten_hang: item_code_da_khop}), lưu, rồi bấm workflow "Gửi
    khách duyệt" (Chờ xác nhận -> Chờ khách đồng ý). Chỉ set item_khop —
    KHÔNG tự sinh dòng `items` mới (khớp hành vi thật: sales phải tự thêm
    dòng items tương ứng nếu muốn dòng đặt ngoài lên đơn giá)."""
    if isinstance(gia_map, str):
        gia_map = json.loads(gia_map)
    if isinstance(khop_map, str):
        khop_map = json.loads(khop_map)

    from frappe.model.workflow import apply_workflow, get_transitions

    so = frappe.get_doc("Sales Order", so_name)
    for it in so.items:
        if gia_map and it.item_code in gia_map:
            it.rate = gia_map[it.item_code]
    for d in so.get("custom_dat_ngoai") or []:
        if khop_map and d.ten_hang in khop_map:
            d.item_khop = khop_map[d.ten_hang]
    so.save()

    trans = get_transitions(so)
    action = next(t["action"] for t in trans if t["action"] == "Gửi khách duyệt")
    so = apply_workflow(so, action)
    so.reload()
    return {"so": so_name, "workflow_state": so.workflow_state, "docstatus": so.docstatus,
            "custom_ngay_gui_khach_duyet": str(so.custom_ngay_gui_khach_duyet),
            "dat_ngoai": [(d.ten_hang, d.item_khop, d.da_xu_ly) for d in so.get("custom_dat_ngoai") or []]}


def mo_lai_don(so_name: str) -> dict:
    """Miyano Sales: bấm workflow "Mở lại" (từ "Khách huỷ" hoặc "Báo giá hết
    hạn" -> "Chờ xác nhận")."""
    from frappe.model.workflow import apply_workflow, get_transitions

    so = frappe.get_doc("Sales Order", so_name)
    trans = get_transitions(so)
    action = next(t["action"] for t in trans if t["action"] == "Mở lại")
    so = apply_workflow(so, action)
    so.reload()
    return {"so": so_name, "workflow_state": so.workflow_state, "docstatus": so.docstatus}


def deliver_so(so_name: str, qty_map: str | dict | None = None) -> dict:
    """Warehouse ships: make a (possibly partial) Delivery Note and submit it.

    qty_map: JSON/dict {item_code: qty}. Lines not in the map deliver 0 (dropped);
    if None, deliver the full remaining qty.
    """
    from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

    if isinstance(qty_map, str):
        qty_map = json.loads(qty_map)
    dn = make_delivery_note(so_name)
    if qty_map:
        keep = []
        for it in dn.items:
            q = qty_map.get(it.item_code)
            if q:
                it.qty = q
                keep.append(it)
        dn.items = keep
    dn.insert()
    dn.submit()
    so = frappe.get_doc("Sales Order", so_name)
    return {"dn": dn.name, "docstatus": dn.docstatus,
            "lines": [(it.item_code, it.qty, it.warehouse) for it in dn.items],
            "so_per_delivered": so.per_delivered, "so_status": so.status}


def invoice_so(so_name: str) -> dict:
    """Accounting issues a Sales Invoice from the Sales Order and submits it."""
    from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

    si = make_sales_invoice(so_name)
    si.insert()
    si.submit()
    so = frappe.get_doc("Sales Order", so_name)
    return {"si": si.name, "docstatus": si.docstatus,
            "grand_total": si.grand_total, "outstanding": si.outstanding_amount,
            "so_per_billed": so.per_billed, "so_status": so.status}


def reconcile_stock(item_code: str, warehouse: str, qty: float = 0) -> dict:
    """Write off / set a warehouse's stock for one item via Stock Reconciliation.
    Used to clean up a phantom balance in an unused warehouse."""
    sr = frappe.new_doc("Stock Reconciliation")
    sr.purpose = "Stock Reconciliation"
    sr.append("items", {"item_code": item_code, "warehouse": warehouse,
                        "qty": qty, "valuation_rate": 0})
    sr.flags.ignore_mandatory = True
    sr.insert()
    sr.submit()
    bal = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
    return {"reconciliation": sr.name, "item": item_code, "warehouse": warehouse, "actual_qty": bal}


def pay_invoice(si_name: str, amount: float | None = None) -> dict:
    """Record a customer Payment Entry against a Sales Invoice."""
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    pe = get_payment_entry("Sales Invoice", si_name)
    if amount:
        pe.paid_amount = amount
        pe.received_amount = amount
        for ref in pe.references:
            ref.allocated_amount = amount
    pe.reference_no = "UAT-PAY-" + si_name
    pe.reference_date = frappe.utils.today()
    pe.insert()
    pe.submit()
    si = frappe.get_doc("Sales Invoice", si_name)
    return {"pe": pe.name, "docstatus": pe.docstatus,
            "paid": pe.paid_amount, "si_outstanding": si.outstanding_amount,
            "si_status": si.status}
