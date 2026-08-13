"""E6 phần B — quy tắc nghiệp vụ thuần cho mua lẻ (QT10) và báo giá hết hạn
(US-E6.5). Xem
docs/Miyano-Portal(Client)_V2/DevHandoff/15_PRD_E6_MuaLe_YeuCauHang.md và
BA §4.10 (BR-R1…R7, NL-10.x).

Tách khỏi `api/portal.py` cùng lý do với `portal_dat_hang.py`/`portal_sla.py`:
nhóm hàm dưới đây là nghiệp vụ thuần, không cần phiên đăng nhập, và
`api/portal.py::portal_order_place` cùng job daily (`portal_bao_gia.py`) đều
cần đọc CHUNG một phép tính — tách riêng để hai nơi không lệch nhau.
"""

import frappe
from frappe.utils import add_days, getdate

TRANG_THAI_CHO_KHACH = "Chờ khách đồng ý"


def price_list_ban_le() -> str:
    """BR-R3 / VĐ-12 — Price List bán lẻ PHẢI được cấu hình trước khi bật
    nhánh mua lẻ. KHÔNG rơi về danh mục rỗng lặng lẽ: một Settings chưa được
    lưu (`tabSingles` rỗng, xem `patches/v1_6/seed_portal_settings_defaults.py`)
    và một Settings CỐ Ý để trống trường này đều phải dừng ở đây với thông
    điệp rõ ràng, không phải trả `catalog=[]` khiến khách tưởng "không có
    hàng bán lẻ" trong khi thật ra là "chưa ai cấu hình".
    """
    pl = frappe.db.get_single_value("Miyano Portal Settings", "price_list_ban_le")
    if not pl:
        frappe.throw(
            "Chưa cấu hình Price List bán lẻ (Miyano Portal Settings). "
            "Vui lòng liên hệ quản trị viên hệ thống.",
            frappe.ValidationError,
        )
    return pl


def hieu_luc_bao_gia_ngay() -> int:
    """BR-R5 — mặc định 7 ngày.

    `frappe.db.get_single_value` đọc thẳng `tabSingles`, KHÔNG rơi về
    `default` khai trong DocType JSON khi Settings chưa từng được lưu (xem
    `patches/v1_6/seed_portal_settings_defaults.py`, cùng bẫy đã trả giá ở
    `portal_sla.sla_yeu_cau_gio`) — fallback `or 7` tường minh ở đây là bắt
    buộc, không phải phòng thủ thừa.
    """
    return int(
        frappe.db.get_single_value("Miyano Portal Settings", "hieu_luc_bao_gia_ngay") or 7
    )


def han_hieu_luc_bao_gia(transaction_date):
    """Hạn hiệu lực báo giá = ngày lập (`Sales Order.transaction_date`) +
    `hieu_luc_bao_gia_ngay`. DÙNG CHUNG bởi `portal_order_accept` (chặn 417
    `qua_han_hieu_luc`), `portal_order_track` (banner `chap_nhan.han_hieu_luc`)
    và job daily `portal_bao_gia.quet_bao_gia_het_han` — ba nơi tính ra một
    con số khác nhau là đúng thứ làm khách thấy hạn một đằng, hệ thống chặn
    một nẻo.
    """
    return getdate(add_days(getdate(transaction_date), hieu_luc_bao_gia_ngay()))


def qua_han_hieu_luc(transaction_date, hom_nay=None) -> bool:
    hom_nay = getdate(hom_nay) if hom_nay else getdate(frappe.utils.nowdate())
    return hom_nay > han_hieu_luc_bao_gia(transaction_date)


def items_thuoc_hdnt_hieu_luc(customer: str) -> set:
    """BR-R7 / NL-10.7 — tập `item_code` đang thuộc HĐNT CÒN HIỆU LỰC của
    khách. "Còn hiệu lực" dùng ĐÚNG điều kiện `portal_contracts()` đang dùng
    (`blanket_order_type=Selling`, `to_date >= hôm nay`) — không tự dựng một
    định nghĩa "hiệu lực" thứ hai lệch với màn Hợp đồng khách đang thấy.

    CỐ Ý không lọc theo hạn mức còn lại: mặt hàng ĐÃ HẾT hạn mức trong HĐNT
    vẫn phải nằm trong tập này — đó chính xác là tình huống BR-R7 sinh ra để
    chặn (khách hết hạn mức né sang mua lẻ). Chỉ xét "có mặt trong hợp đồng
    còn hiệu lực hay không", không xét "còn hạn mức hay không".
    """
    bo_names = frappe.get_all(
        "Blanket Order",
        filters={
            "customer": customer,
            "blanket_order_type": "Selling",
            "to_date": [">=", frappe.utils.today()],
        },
        pluck="name",
    )
    if not bo_names:
        return set()
    return set(frappe.get_all(
        "Blanket Order Item",
        filters={"parent": ["in", bo_names]},
        pluck="item_code",
    ))


def trang_thai_hang(item_code: str) -> str:
    """F-21 — cột "Tình trạng hàng" thay cột hạn mức của danh mục lẻ.

    Đọc tồn Miyano THẬT (`tabBin`, kho của công ty bán hàng) — KHÔNG phải
    kho khách hàng (`Customer Stock Ledger Entry`, quyết định nền tảng #1
    CLAUDE.md): đây là tồn Miyano còn để bán, không phải tồn của khách.
    """
    tong = frappe.db.sql(
        "select sum(actual_qty) from `tabBin` where item_code=%s", item_code
    )[0][0]
    return "Còn hàng" if float(tong or 0) > 0 else "Liên hệ"


def resolve_ban_le_company(item_codes: list[str]):
    """Đơn mua lẻ KHÔNG có Blanket Order để suy `company` như nhánh HĐNT
    (`bo.company`) — suy từ `Item Default` của chính các mặt hàng trong giỏ.
    Một Sales Order chỉ có MỘT `company`, nên chỉ company nào có
    `default_warehouse` khai cho ĐỦ mọi mặt hàng trong giỏ mới hợp lệ.

    Trả `None` khi không có company nào thoả — người gọi phải báo lỗi cấu
    hình rõ ràng, không được đoán bừa một company.
    """
    candidates = None
    for item_code in item_codes:
        companies = set(frappe.get_all(
            "Item Default",
            filters={
                "parent": item_code, "parenttype": "Item",
                "default_warehouse": ["is", "set"],
            },
            pluck="company",
        ))
        candidates = companies if candidates is None else (candidates & companies)
        if not candidates:
            return None
    return next(iter(candidates)) if candidates else None


def cap_nhat_yeu_cau_goc(so, trang_thai_moi: str) -> None:
    """US-E6.5 — ghi vào hai cạnh máy trạng thái `Portal Item Request` mà
    Phần A đã dựng sẵn nhưng chưa ai ghi ("Đã chuyển thành đơn"/"Hết hạn").

    Phòng thủ, KHÔNG ném lỗi ra ngoài luồng chính (`portal_order_accept`
    hoặc job daily): đây là bút toán SỔ SÁCH đi kèm hành động chính (khách
    đồng ý / báo giá hết hạn), không được phép làm hành động chính thất bại
    chỉ vì bản ghi yêu cầu gốc đang ở một trạng thái không khớp cạnh chuyển
    hợp lệ (ví dụ ai đó trên Desk đã tự tay đổi trạng thái yêu cầu trước đó).
    """
    ten_yc = so.get("custom_yeu_cau_goc")
    if not ten_yc:
        return
    if not frappe.db.exists("Portal Item Request", ten_yc):
        return
    yc = frappe.get_doc("Portal Item Request", ten_yc)
    if yc.trang_thai == trang_thai_moi:
        return
    from miyano_portal.miyano_portal.doctype.portal_item_request.portal_item_request import (
        CHUYEN_TRANG_THAI_HOP_LE,
    )
    if trang_thai_moi not in CHUYEN_TRANG_THAI_HOP_LE.get(yc.trang_thai, set()):
        return
    yc.trang_thai = trang_thai_moi
    if trang_thai_moi == "Đã chuyển thành đơn" and not yc.don_lien_ket:
        yc.don_lien_ket = so.name
    yc.save(ignore_permissions=True)
