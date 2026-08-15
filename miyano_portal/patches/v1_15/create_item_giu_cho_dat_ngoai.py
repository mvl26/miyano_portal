"""Spec 2026-08-15 §3.4 — Item kỹ thuật `HANG-DAT-NGOAI`.

`is_stock_item = 0`: mặt hàng này không bao giờ tồn tại trong kho, nó chỉ
giữ chỗ để ERPNext lưu được đơn (bảng `items` rỗng thì `Sales Order` crash ở
`accounts_controller.set_payment_schedule` — đã kiểm thực nghiệm).

Item Default với `default_warehouse` là BẮT BUỘC, không phải trang trí:
`portal_mua_le.resolve_ban_le_company()` chỉ nhận company nào có
`default_warehouse` khai cho mọi mặt hàng trong giỏ. Thiếu dòng này thì đơn
toàn hàng lạ bị từ chối vì "không xác định được công ty giao hàng" — đúng
thứ Item này sinh ra để tránh, hỏng vì một lý do khác.

Idempotent: chạy lại chỉ bổ sung phần còn thiếu, không sinh trùng.
"""

import frappe

# Một nguồn duy nhất cho mã này. Khai lại chuỗi ở đây thì patch và runtime
# có thể trỏ vào hai Item khác nhau sau một lần đổi tên, và không có gì báo.
from miyano_portal.portal_mua_le import ITEM_GIU_CHO as MA

TEN = "Hàng đặt ngoài (chờ Miyano khớp mã)"


def _nhom_item():
    return (
        frappe.db.get_value("Item Group", {"item_group_name": "Vật tư tiêu hao"}, "name")
        or frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    )


def execute():
    company = frappe.defaults.get_global_default("company")
    if not company:
        company = frappe.db.get_value("Company", {}, "name")
    kho = frappe.db.get_value(
        "Warehouse", {"company": company, "is_group": 0}, "name"
    ) if company else None

    if not frappe.db.exists("Item", MA):
        doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": MA,
            "item_name": TEN,
            "item_group": _nhom_item(),
            "stock_uom": "Cái",
            "is_stock_item": 0,
            "is_sales_item": 1,
            "is_purchase_item": 0,
            "description": TEN,
        })
        if company and kho:
            doc.append("item_defaults", {"company": company, "default_warehouse": kho})
        doc.insert(ignore_permissions=True)
        return

    doc = frappe.get_doc("Item", MA)
    thay_doi = False
    if doc.is_stock_item:
        doc.is_stock_item = 0
        thay_doi = True
    if company and kho and not any(
        d.company == company and d.default_warehouse for d in doc.item_defaults
    ):
        doc.append("item_defaults", {"company": company, "default_warehouse": kho})
        thay_doi = True
    if thay_doi:
        doc.save(ignore_permissions=True)
