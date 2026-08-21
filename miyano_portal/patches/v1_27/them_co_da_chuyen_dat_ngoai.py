"""Task 13 (gộp luồng đặt hàng, 21/08/2026) — QĐ-G13/QĐ-G15: hai cột ghi
KẾT QUẢ của việc "khớp mã thì CHUYỂN dòng gõ tay thành hàng thật".

Trước task này bảng con `Sales Order Dat Ngoai Item` chỉ có `item_khop` +
`da_xu_ly`, và `da_xu_ly` chỉ nghĩa là "đã gắn một cái mã vào một dòng ghi
chú" — không có cột nào ghi được rằng dòng đó đã THẬT SỰ thành một dòng
hàng trong `items`, cũng không có cách nào biết dòng nào sinh ra dòng nào.

- `da_chuyen` — cờ BẤT BIẾN (bẫy 1): `validate` chạy mỗi lần lưu, nên phép
  kiểm "đã chuyển chưa" phải đọc CỜ này, KHÔNG được đọc "có dòng nào cùng
  `item_code` không" (dòng đó có thể do người khác thêm tay, hoặc do một
  dòng gõ tay KHÁC cùng mã sinh ra — bẫy 2 gộp số lượng).
- `dong_hang` — TÊN của `Sales Order Item` đã tạo/đã được gộp vào. QĐ-G15:
  dòng gõ tay được GIỮ NGUYÊN làm bằng chứng, nên phải có đường nối hai
  chiều để biết dòng bằng chứng nào ứng với dòng tiền nào.

Cả hai `read_only = 1`: nơi DUY NHẤT được phép ghi chúng là
`miyano_portal.portal_mua_le.chuyen_dong_dat_ngoai_thanh_hang` — cùng lý
do `da_xu_ly` đã `read_only` từ đầu (không ai được tự tay tick "đã chuyển"
mà không có dòng hàng thật đứng sau).

`create_custom_field` (SỐ ÍT — chữ ký `(doctype, df)`) tự nó idempotent:
gọi lại khi field đã tồn tại thì không làm gì, không sinh dòng thứ hai.
KHÔNG khai hai field này thẳng trong `sales_order_dat_ngoai_item.json`:
một `DocField` và một `Custom Field` trùng `fieldname` trên cùng doctype
migrate êm rồi hành xử kỳ quặc — chọn ĐÚNG MỘT đường, và đường của dự án
này là patch.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field

DOCTYPE = "Sales Order Dat Ngoai Item"


def execute():
    create_custom_field(
        DOCTYPE,
        {
            "fieldname": "da_chuyen",
            "label": "Đã chuyển thành dòng hàng",
            "fieldtype": "Check",
            "default": "0",
            "read_only": 1,
            "insert_after": "da_xu_ly",
            "description": (
                "Hệ tự bật khi dòng gõ tay này đã được CHUYỂN thành một dòng "
                "trong bảng Hàng hoá của đơn (QĐ-G13). Cờ bất biến: đã bật thì "
                "lưu lại bao nhiêu lần cũng không sinh thêm dòng hàng."
            ),
        },
        ignore_validate=True,
    )
    create_custom_field(
        DOCTYPE,
        {
            "fieldname": "dong_hang",
            "label": "Dòng hàng đã tạo",
            "fieldtype": "Data",
            "read_only": 1,
            "insert_after": "da_chuyen",
            "description": (
                "Tên dòng Sales Order Item sinh ra (hoặc được gộp số lượng vào) "
                "từ dòng gõ tay này — truy vết QĐ-G15."
            ),
        },
        ignore_validate=True,
    )
