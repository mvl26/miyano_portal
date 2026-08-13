"""E6 phần B — custom field cho mua lẻ (BR-R1/R4/R6) và liên kết báo giá (BR-R5).

`create_custom_fields` tự nó đã idempotent: gọi lại chỉ cập nhật thuộc tính,
không sinh bản ghi thứ hai.

`custom_cho_phep_mua_le` mặc định 0 — khách hiện hữu KHÔNG đổi hành vi (DoD):
field mới thêm vào một Customer sẵn có nhận default 0 của cột, không phải
`None`, nên `frappe.db.get_value("Customer", cust, "custom_cho_phep_mua_le")`
đọc ra falsy ngay cả với khách đã tồn tại từ trước khi patch này chạy.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Customer": [
                {
                    "fieldname": "custom_cho_phep_mua_le",
                    "label": "Được phép mua lẻ (Client Portal)",
                    "fieldtype": "Check",
                    "default": "0",
                    "insert_after": "default_price_list",
                    "description": (
                        "Bật để khách thấy chế độ Mua lẻ trên cổng (BR-R1). "
                        "Chỉ bật khi khách công lập tự xác nhận được phép mua "
                        "ngoài hợp đồng (VĐ-13)."
                    ),
                }
            ],
            "Item": [
                {
                    "fieldname": "custom_ban_le_portal",
                    "label": "Mở bán lẻ trên Client Portal",
                    "fieldtype": "Check",
                    "default": "0",
                    "insert_after": "item_group",
                    "description": (
                        "Bật để mặt hàng xuất hiện trong danh mục mua lẻ của "
                        "cổng khách hàng (BR-R6). Vẫn cần giá trong Price "
                        "List bán lẻ mới đặt thẳng được (BR-R3/NL-10.2)."
                    ),
                }
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_loai_don",
                    "label": "Loại đơn",
                    "fieldtype": "Select",
                    "options": "Theo HĐNT\nMua lẻ",
                    "default": "Theo HĐNT",
                    "insert_after": "custom_yeu_cau_khach",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_yeu_cau_goc",
                    "label": "Yêu cầu hàng hoá gốc",
                    "fieldtype": "Link",
                    "options": "Portal Item Request",
                    "insert_after": "custom_loai_don",
                    "no_copy": 1,
                    "description": (
                        "SO nháp lập từ báo giá của một Portal Item Request "
                        "(US-E6.5). Khách Đồng ý trên cổng → yêu cầu này "
                        "chuyển 'Đã chuyển thành đơn'; quá hạn hiệu lực → "
                        "'Hết hạn' (job daily)."
                    ),
                },
            ],
        },
        ignore_validate=True,
    )
