"""Spec 2026-08-15 §3.5 — Mua lẻ mặc định BẬT.

Hai việc, thiếu một là hỏng nửa: đổi `default` (khách TẠO MỚI từ nay) và
UPDATE khách HIỆN HỮU (những người đã tồn tại trước patch).

KHÔNG bỏ chốt `dam_bao_duoc_mua_le()` ở server — cờ vẫn còn tác dụng, sales
vẫn tắt được cho một khách cụ thể (khách nợ quá hạn, chỉ cho mua theo hợp
đồng). Đây là đổi GIÁ TRỊ MẶC ĐỊNH, không phải bỏ cơ chế.

Idempotent: đặt `default` về đúng "1" (đã đúng thì không lưu lại) và chỉ
UPDATE các dòng đang là 0/NULL.
"""

import frappe

FIELD = {"dt": "Customer", "fieldname": "custom_cho_phep_mua_le"}


def execute():
    ten = frappe.db.get_value("Custom Field", FIELD, "name")
    if not ten:
        # Patch v1_8 chưa chạy — không có field để đổi mặc định.
        return

    if str(frappe.db.get_value("Custom Field", ten, "default") or "") != "1":
        frappe.db.set_value("Custom Field", ten, "default", "1")
        frappe.clear_cache(doctype="Customer")

    frappe.db.sql(
        """update `tabCustomer`
           set custom_cho_phep_mua_le = 1
           where ifnull(custom_cho_phep_mua_le, 0) = 0"""
    )
