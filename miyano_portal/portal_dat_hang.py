"""Quy tắc thao tác của luồng đặt hàng — bội số quy cách và ngày giao.

Tách khỏi `api/portal.py` vì hai lý do. `portal_order_place` đã dài và mọi
quy tắc mới đều muốn chen vào giữa nó. Và hai nhóm hàm dưới đây là nghiệp vụ
thuần: kiểm được mà không cần phiên đăng nhập, Blanket Order hay Sales Order
nào — thứ nào kiểm được rẻ thì nên kiểm được rẻ.

Cả hai đều trả **thông điệp lỗi** thay vì ném: `portal_order_place` gom mọi
lỗi của cả giỏ hàng rồi báo một lần (BR-O3), nên hàm con ném ngay lập tức sẽ
phá đúng tính chất đó — khách sửa một lỗi lại gặp lỗi tiếp theo, hết lần này
đến lần khác.
"""

import math

import frappe
from frappe import _
from frappe.utils import add_days, getdate


def kiem_boi_so(item_code: str, qty) -> str | None:
    """BR-O11 / NL-1.6. Trả thông điệp lỗi nếu sai bội số, `None` nếu hợp lệ.

    Gợi ý luôn LÀM TRÒN LÊN chứ không chọn bội số gần nhất theo khoảng cách:
    khách gõ 11 nghĩa là họ cần ít nhất 11, đề nghị 10 là đề nghị thiếu so
    với nhu cầu họ vừa nói ra.

    Mặt hàng không tồn tại cũng trả `None` — không phải việc của hàm này.
    Mặt hàng lạ đã bị chặn ở tầng hạn mức và tầng giá trước đó; ném lỗi ở đây
    chỉ làm rối thông điệp mà khách nhận được.
    """
    boi_so = int(frappe.db.get_value("Item", item_code, "custom_boi_so_dat") or 0)
    if boi_so <= 0:
        return None
    qty = float(qty or 0)
    if qty % boi_so == 0:
        return None
    goi_y = int(math.ceil(qty / boi_so) * boi_so)
    # Nguyên văn ma trận FormSpec §5, dòng NL-1.6. Giao diện hiển thị thẳng
    # chuỗi này, không dịch lại — sửa ở đây là sửa cả hai nơi.
    return _("Số lượng phải là bội số của {0}. Gần nhất: {1}.").format(boi_so, goi_y)


def ngay_giao_mac_dinh(tu_ngay=None):
    """BR-O13 — mặc định +2 NGÀY LÀM VIỆC, bỏ qua Thứ Bảy và Chủ Nhật.

    Cố ý KHÔNG trừ ngày lễ: spec chỉ nói bỏ T7/CN, và một bảng ngày lễ không
    ai duy trì sẽ sai lệch âm thầm — tệ hơn là không có, vì nó tạo cảm giác
    đã được xử lý.
    """
    ngay = getdate(tu_ngay or frappe.utils.today())
    con_lai = 2
    while con_lai > 0:
        ngay = getdate(add_days(ngay, 1))
        if ngay.weekday() < 5:  # 0=T2 … 4=T6
            con_lai -= 1
    return ngay


def kiem_ngay_giao(delivery_date) -> str | None:
    """BR-O13 / NL-1.7. Trả thông điệp lỗi nếu ngày giao ở quá khứ.

    Chỉ chặn QUÁ KHỨ. Hôm nay và ngày mai đều đi qua: "+2 ngày làm việc" là
    giá trị MẶC ĐỊNH của ô nhập, không phải sàn cứng. Khách chủ động chọn
    giao gấp là việc sales thu xếp, không phải lỗi nhập liệu để chặn.
    """
    if getdate(delivery_date) < getdate(frappe.utils.today()):
        som_nhat = ngay_giao_mac_dinh()
        # Nguyên văn ma trận FormSpec §5, dòng NL-1.7.
        return _("Ngày giao sớm nhất là {0} (sau 2 ngày làm việc).").format(
            som_nhat.strftime("%d/%m/%Y")
        )
    return None
