import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": "custom_nguon_don",
                    "label": "Nguồn đơn",
                    "fieldtype": "Select",
                    "options": "Nội bộ\nClient Portal",
                    "default": "Nội bộ",
                    "insert_after": "customer",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_hdnt",
                    "label": "Hợp đồng khung",
                    "fieldtype": "Link",
                    "options": "Blanket Order",
                    "insert_after": "custom_nguon_don",
                },
                {
                    "fieldname": "custom_so_po_khach",
                    "label": "Số dự trù/PO khách",
                    "fieldtype": "Data",
                    "insert_after": "custom_hdnt",
                },
                {
                    "fieldname": "custom_yeu_cau_khach",
                    "label": "Ghi chú của khách",
                    "fieldtype": "Small Text",
                    "insert_after": "custom_so_po_khach",
                },
            ]
        },
        ignore_validate=True,
    )
