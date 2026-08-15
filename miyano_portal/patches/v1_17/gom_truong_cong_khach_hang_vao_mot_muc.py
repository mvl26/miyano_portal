"""Việc 3 (dọn lean) — gom 9 field tuỳ biến của cổng + bảng con
`custom_dat_ngoai` vào MỘT Section Break "Cổng khách hàng" trên form
`Sales Order`.

TRƯỚC: `custom_nguon_don`, `custom_loai_don`, `custom_hdnt`,
`custom_so_po_khach`, `custom_yeu_cau_khach`, `custom_request_id`,
`custom_ngay_gui_khach_duyet`, `custom_yeu_cau_goc`, `custom_ly_do_tu_choi`
rải rác XEN LẪN với field NATIVE của ERPNext (`customer_name`, `tax_id`,
`order_type`, `transaction_date`...) trong section `customer_section` có
sẵn — mỗi patch tạo field trước đây chỉ `insert_after` field TRƯỚC ĐÓ của
CHÍNH nó, không ai gom lại. Nhân viên back-office phải dò khắp form để tìm
đủ 9 field + bảng con.

VỊ TRÍ Section Break mới — `insert_after: "amended_from"` (field CUỐI CÙNG
của `customer_section`, xem `erpnext/selling/doctype/sales_order/
sales_order.json::field_order`, ngay TRƯỚC `accounting_dimensions_section`
— Section Break NATIVE tiếp theo). Đây là biên AN TOÀN DUY NHẤT: chèn một
Section Break MỚI vào GIỮA một section native (ví dụ ngay sau `customer`)
sẽ nuốt mọi field native phía sau nó (`customer_name`, `tax_id`,
`transaction_date`...) vào section MỚI cho tới khi gặp Section Break tiếp
theo — Frappe không có cơ chế "đóng section" tường minh, section cứ mở tới
khi gặp Section Break kế tiếp (xem `frappe/model/meta.py::sort_fields` +
`_update_field_order_based_on_insert_after`, thuật toán ghép `insert_after`
CHUNG cho cả field native lẫn custom). Chèn NGAY TRƯỚC một Section Break
native có sẵn (`accounting_dimensions_section`) thì section mới tự ĐÓNG
đúng chỗ nó vốn đóng — không cần một Section Break "đóng" thủ công, không
đụng một field native nào.

THỨ TỰ bên trong section (theo cách nhân viên back-office THẬT SỰ dùng khi
xử lý một đơn từ cổng — xem báo cáo lean-report.md để biết lý lẽ đầy đủ):
1. `custom_nguon_don`, `custom_loai_don`, `custom_hdnt`, `custom_so_po_khach`,
   `custom_yeu_cau_khach` — NHẬN DẠNG đơn (đơn này từ đâu, loại gì, theo
   hợp đồng nào, khách yêu cầu gì) — đọc TRƯỚC TIÊN khi mở một đơn portal.
2. `custom_ngay_gui_khach_duyet`, `custom_yeu_cau_goc`, `custom_ly_do_tu_choi`
   — NHÓM XỬ LÝ (mốc gửi báo giá, liên kết yêu cầu gốc, lý do từ chối nếu
   có) — chỉ cần khi đơn đã qua bước gửi khách/bị từ chối, không phải lúc
   mở đơn.
3. `custom_request_id` — mã kỹ thuật chống trùng đơn (BR-O12), CUỐI CÙNG
   trong nhóm field đơn lẻ. CÂN NHẮC `hidden` nhưng chọn GIỮ HIỆN (không
   hidden): field đã `read_only=1` (ERPNext tự làm mờ), và nhân viên đôi
   khi cần NHÌN THẤY nó khi xử lý khiếu nại "đặt trùng đơn" — ẩn hẳn buộc
   họ tra thẳng CSDL/nhờ dev thay vì nhìn trực tiếp trên form đang mở.
4. `custom_dat_ngoai` — bảng con, CUỐI section (Table field luôn full-width
   bất kể section/column, đặt cuối tự nhiên nhất — cũng là dòng khách gõ
   tay, nặng thao tác nhất, hợp lý xem SAU KHI đã nắm được thông tin đơn).

CƠ CHẾ: `create_custom_fields` cho field ĐÃ TỒN TẠI chỉ cập nhật property
được liệt kê trong dict truyền vào (ở đây CHỈ `insert_after`) — không đụng
`label`/`fieldtype`/`options`/`read_only`... của field đó. Chuỗi
`insert_after` DÙNG MỘT TARGET DUY NHẤT cho mỗi field (không field nào
chia sẻ target với field khác) — thuật toán ghép trong
`frappe/model/meta.py::_update_field_order_based_on_insert_after` chạy lặp
tới khi hội tụ, nên với một chuỗi ĐƠN TUYẾN như thế này kết quả cuối cùng
TẤT ĐỊNH bất kể thứ tự xử lý nội bộ (đã kiểm chứng bằng thực nghiệm trên
site: trạng thái TRƯỚC patch này có NHIỀU field cùng chia sẻ một
`insert_after` target — ví dụ `custom_hdnt` VÀ `custom_request_id` cùng
`insert_after: custom_nguon_don` — kết quả cuối phụ thuộc thứ tự xử lý nội
bộ, giải thích vì sao 9 field hiện rải rác không theo đúng thứ tự tạo).

Idempotent: `create_custom_fields` tự nó đã idempotent (so `original_values
!= custom_field.__dict__` trước khi save; gọi lại với cùng giá trị là
no-op).
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

SEC_FIELDNAME = "custom_sec_cong_khach_hang"

# Chuỗi insert_after ĐƠN TUYẾN — mỗi field chỉ trỏ về ĐÚNG MỘT field đứng
# ngay trước nó trong thứ tự mong muốn cuối cùng.
THU_TU = [
    (SEC_FIELDNAME, "amended_from"),
    ("custom_nguon_don", SEC_FIELDNAME),
    ("custom_loai_don", "custom_nguon_don"),
    ("custom_hdnt", "custom_loai_don"),
    ("custom_so_po_khach", "custom_hdnt"),
    ("custom_yeu_cau_khach", "custom_so_po_khach"),
    ("custom_ngay_gui_khach_duyet", "custom_yeu_cau_khach"),
    ("custom_yeu_cau_goc", "custom_ngay_gui_khach_duyet"),
    ("custom_ly_do_tu_choi", "custom_yeu_cau_goc"),
    ("custom_request_id", "custom_ly_do_tu_choi"),
    ("custom_dat_ngoai", "custom_request_id"),
]


def execute():
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": SEC_FIELDNAME,
                    "label": "Cổng khách hàng",
                    "fieldtype": "Section Break",
                    "insert_after": "amended_from",
                    "description": (
                        "Field riêng của đơn đặt qua Client Portal — nguồn/"
                        "loại đơn, hợp đồng khung, yêu cầu khách, xử lý báo "
                        "giá/từ chối, và dòng đặt ngoài chưa có mã."
                    ),
                },
            ],
        },
        ignore_validate=True,
    )
    create_custom_fields(
        {
            "Sales Order": [
                {"fieldname": fieldname, "insert_after": insert_after}
                for fieldname, insert_after in THU_TU
                if fieldname != SEC_FIELDNAME
            ],
        },
        ignore_validate=True,
    )
