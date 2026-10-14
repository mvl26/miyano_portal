"""Địa chỉ email của khách và của sales phụ trách khách — dùng chung cho
các email gửi thẳng (`frappe.sendmail`) mà Notification khai báo không diễn
đạt được: `Customer.account_manager` không nằm trên chứng từ kích hoạt.

Job đóng báo giá "Mua lẻ" quá hạn trên Sales Order đã bỏ (patch v1_44): báo
giá giờ là Quotation, job hết hạn của nó là `bao_gia.quet_het_han`.
"""

import frappe


def _email_khach(so) -> str | None:
    if so.get("contact_email"):
        return so.contact_email
    parent = frappe.db.get_value(
        "Dynamic Link",
        {"parenttype": "Contact", "link_doctype": "Customer", "link_name": so.customer},
        "parent",
    )
    if not parent:
        return None
    return frappe.db.get_value(
        "Contact Email", {"parent": parent, "is_primary": 1}, "email_id"
    ) or frappe.db.get_value("Contact Email", {"parent": parent}, "email_id")


def _email_sales_phu_trach(customer: str) -> str | None:
    return frappe.db.get_value("Customer", customer, "account_manager")
