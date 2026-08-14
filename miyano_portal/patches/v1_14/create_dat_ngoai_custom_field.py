"""Thiết kế lại mua lẻ §4.3 — bảng con "chưa có trong kho, cần đặt ngoài"
trên `Sales Order`. `Sales Order Item` bắt buộc `item_code` (ràng buộc cứng
của ERPNext, §3 thiết kế), nên dòng khách tự nhập KHÔNG THỂ là một dòng
`Sales Order Item` bình thường cho tới khi nhân viên khớp được mã hàng thật
— đây là lý do bắt buộc phải có bảng con RIÊNG, không phải lựa chọn thẩm mỹ.

`create_custom_fields` tự nó đã idempotent (gọi lại chỉ cập nhật thuộc
tính, không sinh dòng thứ hai).

CỐ Ý không set `allow_on_submit`: field mặc định `allow_on_submit=0`, tức
KHÔNG sửa được bảng con này sau khi đơn đã Submit — nếu bật, chốt
`before_submit` (miyano_portal.portal_mua_le.kiem_dat_ngoai_da_xu_ly, §4.4)
chỉ còn là trang trí, vì ai đó có thể chèn thêm một dòng chưa xử lý SAU khi
đơn đã qua chốt.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": "custom_dat_ngoai",
                    "label": "Dòng đặt ngoài (chưa có trong danh mục)",
                    "fieldtype": "Table",
                    "options": "Sales Order Dat Ngoai Item",
                    "insert_after": "items",
                    "description": (
                        "Khách gõ thẳng tên hàng khi không tìm thấy mã trong danh mục "
                        "(thiết kế §4.3). Nhân viên khớp 'Mã hàng khớp' khi báo giá — "
                        "còn dòng chưa khớp thì không xác nhận được đơn (§4.4)."
                    ),
                },
            ],
        },
        ignore_validate=True,
    )
