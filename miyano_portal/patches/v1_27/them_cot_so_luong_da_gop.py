"""Review Task 13 (22/08/2026), Critical-1 — CỘT SỔ SÁCH THỨ BA mà
`them_co_da_chuyen_dat_ngoai` cố ý chưa dựng, và chính chỗ từ chối đó là lỗ.

`chuyen_dong_dat_ngoai_thanh_hang` GỘP số lượng vào một dòng `items` sẵn có
khi mã trùng (bẫy 2). Sau khi gộp, "phần nào của dòng hàng này tới từ dòng
gõ tay" không còn câu trả lời — bản đầu của task GỌI ĐÚNG TÊN khoảng trống
này trong docstring `_kiem_dong_da_chuyen_khong_doi` rồi chọn CHẶN thay vì
dựng cột. Chặn chỉ phủ được `so_luong`/`item_khop`; nó không phủ XOÁ và
không phủ NHÂN BẢN. Hai lỗ còn lại, cả hai đều dựng lại được trên bench
(xem `tests/test_khop_ma_dat_ngoai.py`):

  1. Xoá dòng gõ tay đã chuyển rồi NHẬP LẠI trên cùng đơn nháp → phần số
     lượng cũ vẫn nằm trong dòng hàng, phần mới cộng thêm → 5 thành 10,
     tiền nhân đôi, dòng bằng chứng vẫn ghi 5. Đây đúng là NỬA lời khuyên
     câu báo lỗi bẫy 6 đưa ra, nên không phải ca hiếm — nó là đường gỡ lỗi
     hệ thống tự chỉ cho người dùng.
  2. Nhân bản đơn (nút Duplicate trên Desk) → bản sao mang sẵn dòng hàng,
     phép chuyển chạy lại trên bản sao và cộng thêm lần nữa → cũng 10.

`so_luong_da_gop` ghi ĐÚNG phần số lượng dòng gõ tay này đã bơm vào dòng
`dong_hang`. Có nó thì phép chuyển HOÀN TÁC được đóng góp của một dòng gõ
tay bị xoá mà không ăn lẹm phần khách đã đặt trực tiếp trên cùng dòng hàng.

Backfill: mọi dòng `da_chuyen = 1` có sẵn đều đã bơm ĐÚNG `so_luong` của
chính nó — phép chuyển chưa bao giờ bơm một con số khác (đã đọc lại nhánh
`_gop_hoac_them_dong_hang` của bản trước: `hang.qty += qty` với `qty =
flt(dong.so_luong)`). Gán thẳng, KHÔNG để 0: 0 nghĩa "không hoàn tác gì" và
sẽ giữ nguyên lỗ số 1 cho mọi đơn nháp đang mở.

Bọc backfill trong kiểm cột tồn tại — cùng khuôn `v1_25.them_nguon_gia_
dong_phieu._co_cot_loai_don`. `create_custom_field` đồng bộ schema qua
`CustomField.on_update`, nhưng một patch KHÔNG nên phụ thuộc thứ tự bên
trong của framework để câu `update` phía sau nó chạy được.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

DOCTYPE = "Sales Order Dat Ngoai Item"


def execute():
    create_custom_field(
        DOCTYPE,
        {
            "fieldname": "so_luong_da_gop",
            "label": "Số lượng đã gộp vào dòng hàng",
            "fieldtype": "Float",
            "precision": "3",
            "default": "0",
            "read_only": 1,
            "insert_after": "dong_hang",
            "description": (
                "Phần số lượng dòng gõ tay này đã bơm vào dòng hàng ở cột bên. "
                "Xoá dòng gõ tay khỏi đơn nháp thì hệ TRỪ LẠI đúng phần này, "
                "không để số lượng thừa nằm lại trong đơn."
            ),
        },
        ignore_validate=True,
    )
    if not _co_cot("so_luong_da_gop"):
        return
    frappe.db.sql(
        """
        update `tabSales Order Dat Ngoai Item`
        set so_luong_da_gop = so_luong
        where da_chuyen = 1 and ifnull(so_luong_da_gop, 0) = 0
        """
    )


def _co_cot(ten_cot: str) -> bool:
    return bool(frappe.db.sql(
        f"show columns from `tab{DOCTYPE}` like %s", ten_cot
    ))
