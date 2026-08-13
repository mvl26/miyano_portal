"""E6 phần B, review I-2(a) round 2 — mốc tính hạn hiệu lực báo giá (BR-R5)
đổi từ `transaction_date` (ngày lập nháp) sang ngày báo giá THỰC SỰ đến tay
khách. `custom_ngay_gui_khach_duyet` được `portal_mua_le.ghi_ngay_gui_khach_
duyet` (hook `validate`) tự ghi mỗi khi Sales Order chuyển vào "Chờ khách
đồng ý" — field ở đây chỉ khai schema, không tự điền dữ liệu quá khứ (không
có gì để suy ra "ngày gửi" cho các đơn đã ở trạng thái đó từ trước; những
đơn này rơi về `transaction_date` qua fallback trong `han_hieu_luc_bao_gia`).

`create_custom_fields` tự nó đã idempotent: gọi lại chỉ cập nhật thuộc
tính, không sinh bản ghi thứ hai.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": "custom_ngay_gui_khach_duyet",
                    "label": "Ngày gửi khách duyệt",
                    "fieldtype": "Date",
                    "read_only": 1,
                    "no_copy": 1,
                    "insert_after": "custom_yeu_cau_goc",
                    "description": (
                        "Ghi tự động khi đơn chuyển sang 'Chờ khách đồng ý' "
                        "(portal_mua_le.ghi_ngay_gui_khach_duyet). Mốc tính "
                        "hạn hiệu lực báo giá (BR-R5) — KHÔNG PHẢI ngày lập."
                    ),
                },
            ],
        },
        ignore_validate=True,
    )
