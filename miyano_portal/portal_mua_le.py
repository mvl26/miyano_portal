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
from frappe.utils import add_days, flt, getdate

TRANG_THAI_CHO_KHACH = "Chờ khách đồng ý"

# Spec 2026-08-15 §3.4 — mã kỹ thuật giữ chỗ cho đơn TOÀN hàng chưa có mã.
# Dựng bởi `patches/v1_15/create_item_giu_cho_dat_ngoai.py`.
ITEM_GIU_CHO = "HANG-DAT-NGOAI"


# BR-R1 / NL-10.1 (`dam_bao_duoc_mua_le`, chốt cờ `Customer.custom_cho_phep_
# mua_le`) đã BỎ HẲN 21/08 — chủ đầu tư chốt 19/08: "nghiệp vụ đó áp dụng
# cho toàn bộ khách hàng", không còn khách nào cần được "bật" mới mua lẻ
# được. Field bị xoá bằng `patches/v1_25/xoa_co_mua_le.py`. Xem
# `task-1-brief.md` mục (a).


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


def han_hieu_luc_bao_gia(so):
    """Hạn hiệu lực báo giá = mốc GỬI KHÁCH DUYỆT + `hieu_luc_bao_gia_ngay`.
    DÙNG CHUNG bởi `portal_order_accept` (chặn 417 `qua_han_hieu_luc`),
    `portal_order_track` (banner `chap_nhan.han_hieu_luc`) và job daily
    `portal_bao_gia.quet_bao_gia_het_han` — ba nơi tính ra một con số khác
    nhau là đúng thứ làm khách thấy hạn một đằng, hệ thống chặn một nẻo.

    `so` là Document HOẶC `_dict` bất kỳ hỗ trợ `.get()` (đủ cho cả doc đầy
    đủ ở `portal_order_accept`/`portal_order_track` lẫn hàng kết quả
    `frappe.get_all` ở `quet_bao_gia_het_han`).

    review I-2(a), round 2 — MỐC đổi từ `transaction_date` (ngày lập nháp)
    sang `custom_ngay_gui_khach_duyet` (ngày báo giá thực sự ĐẾN TAY khách,
    ghi tự động bởi `ghi_ngay_gui_khach_duyet` mỗi khi workflow chuyển VÀO
    "Chờ khách đồng ý"). Quyết định của người phụ trách nghiệp vụ (không
    phải tự suy diễn): "ngày lập báo giá" trong PRD/BA đọc đúng là ngày báo
    giá được PHÁT HÀNH cho khách — sales chốt giá mất 10 ngày rồi mới gửi
    thì hiệu lực phải đếm từ NGÀY GỬI. Đọc theo `transaction_date` khiến
    khách mở báo giá ra đã thấy "hết hiệu lực" và job daily đóng đơn ngay
    đêm đó — một báo giá không cho khách ngày nào để đồng ý thì không còn
    là báo giá, đúng hệ quả review round 1 (I-2) đã dựng.

    Rơi về `transaction_date` khi `custom_ngay_gui_khach_duyet` rỗng — CHỈ
    xảy ra với đơn đã ở "Chờ khách đồng ý" TỪ TRƯỚC khi field này tồn tại
    (patch mới không backfill được cho quá khứ, và các fixture test dựng
    trực tiếp bằng `frappe.db.set_value` bỏ qua hook cũng rơi vào nhánh
    này). Không rơi về `nowdate()`/`None`: đơn cũ sẽ thành "hạn vô tận" hay
    "hết hạn ngay lập tức", cả hai đều sai hơn dùng `transaction_date`.
    """
    diem_moc = so.get("custom_ngay_gui_khach_duyet") or so.get("transaction_date")
    return getdate(add_days(getdate(diem_moc), hieu_luc_bao_gia_ngay()))


def qua_han_hieu_luc(so, hom_nay=None) -> bool:
    hom_nay = getdate(hom_nay) if hom_nay else getdate(frappe.utils.nowdate())
    return hom_nay > han_hieu_luc_bao_gia(so)


def ghi_ngay_gui_khach_duyet(doc, method=None) -> None:
    """US-E6.5/BR-R5 (review I-2(a), round 2) — ghi `custom_ngay_gui_khach_
    duyet` tại HOOK `validate` của Sales Order (đăng ký ở
    `hooks.py::doc_events["Sales Order"]["validate"]`), KHÔNG ở một endpoint
    cổng: đường đi CHÍNH của US-E6.5 là sales bấm nút workflow "Gửi khách
    duyệt" TỪ DESK ("sales lập SO nháp từ yêu cầu... đặt trạng thái Chờ
    khách đồng ý") — không có endpoint cổng nào cho hành động đó để gắn
    logic vào; chỉ `validate` mới chắc chắn chạy dù đơn được chuyển trạng
    thái từ đâu (`apply_workflow` cuối cùng cũng gọi `doc.save()`).

    Ghi lại MỖI LẦN đơn CHUYỂN VÀO "Chờ khách đồng ý", không chỉ lần đầu:
    khách "Không đồng ý" đưa đơn về "Chờ xác nhận", sales sửa giá rồi gửi
    lại — hiệu lực phải đếm từ lần GỬI LẠI, không phải lần gửi đầu tiên đã
    bị khách từ chối.
    """
    if doc.get("workflow_state") != TRANG_THAI_CHO_KHACH:
        return
    if doc.is_new():
        # Hiếm gặp (tạo mới đã thẳng ở state này) nhưng vẫn xử lý nhất quán.
        if not doc.get("custom_ngay_gui_khach_duyet"):
            doc.custom_ngay_gui_khach_duyet = frappe.utils.today()
        return
    truoc = doc.get_doc_before_save()
    if not truoc or truoc.get("workflow_state") != TRANG_THAI_CHO_KHACH:
        # Vừa CHUYỂN VÀO state này (từ state khác, hoặc chưa từng ở đó) —
        # ghi lại NGÀY MỚI, ghi đè giá trị cũ nếu có (xem docstring: gửi
        # lại sau khi bị từ chối phải reset đồng hồ).
        doc.custom_ngay_gui_khach_duyet = frappe.utils.today()


def dong_bo_da_xu_ly_dat_ngoai(doc, method=None) -> None:
    """Thiết kế lại mua lẻ §4.3 — đồng bộ `da_xu_ly` của bảng con
    `custom_dat_ngoai` (Sales Order Dat Ngoai Item) theo `item_khop`, và
    kiểm `so_luong > 0`.

    Ở HOOK `validate` của Sales Order (đăng ký ở
    `hooks.py::doc_events["Sales Order"]["validate"]`), KHÔNG ở
    `validate()` của chính doctype con: Frappe KHÔNG gọi `validate()` của
    controller bảng con khi document CHA lưu — chỉ các kiểm tra tầng khung
    (mandatory/link/options) tự chạy cho bảng con. Một `validate()` đặt ở
    `SalesOrderDatNgoaiItem` sẽ không bao giờ được gọi — xem docstring dài ở
    file đó.

    `da_xu_ly` là field `read_only=1` trên JSON (chặn ai đó tự tay tick từ
    UI mà không thật sự khớp mã hàng), nên nơi DUY NHẤT được phép ghi field
    này là chính hàm này — server tự suy ra từ `item_khop`, không tin giá
    trị `da_xu_ly` client gửi lên (nếu có).
    """
    for dong in doc.get("custom_dat_ngoai") or []:
        dong.da_xu_ly = 1 if dong.get("item_khop") else 0
        so_luong = flt(dong.get("so_luong"))
        if so_luong <= 0:
            frappe.throw(
                f"Dòng đặt ngoài '{dong.get('ten_hang') or '?'}': số lượng phải > 0.",
                frappe.ValidationError,
            )


def kiem_dat_ngoai_da_xu_ly(doc, method=None) -> None:
    """Thiết kế lại mua lẻ §4.4 — CHỐT MỚI: không xác nhận đơn khi còn dòng
    "đặt ngoài" chưa xử lý (chưa có `item_khop`).

    Ở `before_submit`, ÁP CHO MỌI Sales Order (không riêng đơn Mua lẻ) —
    bảng con `custom_dat_ngoai` rỗng với đơn không dùng nhóm này nên vòng
    lặp dưới đây là no-op, chi phí không đáng kể.

    VÌ SAO CẦN: thiếu chốt này, một đơn có thể được duyệt và giao trong khi
    hai dòng khách yêu cầu chưa ai đụng tới — khách trả tiền cho thứ họ
    không nhận được, và không có tín hiệu nào báo (thiết kế §4.4).

    Field `custom_dat_ngoai` KHÔNG `allow_on_submit` (xem patch
    `create_dat_ngoai_custom_field`), nên không có đường nào thêm được một
    dòng chưa xử lý SAU khi đơn đã qua chốt này — chốt chỉ cần đứng đúng
    MỘT lần, ở đây.
    """
    chua_xu_ly = [d for d in doc.get("custom_dat_ngoai") or [] if not d.get("da_xu_ly")]
    if not chua_xu_ly:
        return
    ten = ", ".join(d.get("ten_hang") or "?" for d in chua_xu_ly)
    frappe.throw(
        f"Còn {len(chua_xu_ly)} dòng đặt ngoài chưa xử lý ({ten}). "
        "Khớp mã hàng (hoặc tạo mã mới) cho từng dòng trước khi xác nhận đơn.",
        frappe.ValidationError,
    )


def kiem_khong_con_dong_giu_cho(doc, method=None) -> None:
    """Việc thêm (controller, ngoài Task 9) — CHỐT MỚI, cạnh
    `kiem_dat_ngoai_da_xu_ly`: chốt đó chỉ nhìn `custom_dat_ngoai` (còn dòng
    nào chưa khớp `item_khop` hay không), KHÔNG hề nhìn `items` — nên một
    đơn có TẤT CẢ dòng đặt ngoài đã khớp mã (chốt kia hài lòng) vẫn có thể
    submit trong khi dòng giữ chỗ `ITEM_GIU_CHO` còn nằm nguyên trong
    `items`, vì không có gì bắt sales GỠ nó ra sau khi khớp mã xong.

    VÌ SAO CẦN: `ITEM_GIU_CHO` là chi tiết kỹ thuật nội bộ (đã lọc khỏi
    `portal_order_track` — xem `la_dong_giu_cho` — và khỏi mẫu in "Miyano -
    Báo giá"), nhưng mẫu in "Miyano - Xác nhận đơn hàng" (chứng từ khách
    THẬT SỰ nhận sau khi đơn được duyệt) không lọc nó. Không có chốt này,
    một đơn toàn hàng chưa có mã có thể được xác nhận và giao trong khi
    khách nhận PDF xác nhận có một dòng "HANG-DAT-NGOAI" vô nghĩa với họ.

    Ở `before_submit`, CẠNH `kiem_dat_ngoai_da_xu_ly` (đăng ký cùng chỗ
    trong `hooks.py::doc_events["Sales Order"]["before_submit"]`) — cùng lý
    do: field `items`/`custom_dat_ngoai` không `allow_on_submit`, nên chốt
    chỉ cần đứng đúng MỘT lần, ở đây.
    """
    if any(la_dong_giu_cho(i.item_code) for i in doc.get("items") or []):
        frappe.throw(
            f"Đơn còn dòng giữ chỗ kỹ thuật ({ITEM_GIU_CHO}). Gỡ dòng này khỏi "
            "danh sách hàng và thay bằng dòng hàng thật đã khớp mã trước khi "
            "xác nhận đơn.",
            frappe.ValidationError,
        )


def la_dong_giu_cho(item_code) -> bool:
    """Dùng CHUNG bởi Python và Jinja (đăng ký trong `hooks.py::jinja`).

    Mẫu in "Miyano - Báo giá" phải lọc dòng giữ chỗ. Viết `{% if i.item_code
    != "HANG-DAT-NGOAI" %}` trong template là chép hằng số sang một nơi
    không ai grep tới: đổi `ITEM_GIU_CHO` thì template lặng lẽ hết lọc và
    khách nhận báo giá có một dòng kỹ thuật, không test nào đỏ.
    """
    return item_code == ITEM_GIU_CHO


def can_chen_giu_cho(items, dat_ngoai) -> bool:
    """CHỈ chèn `ITEM_GIU_CHO` khi giỏ không còn mặt hàng thật nào.

    Đây là ràng buộc cứng, không phải tối ưu. `resolve_ban_le_company()`
    GIAO tập company của MỌI mặt hàng trong giỏ (chỉ company nào khai
    `default_warehouse` cho đủ mọi mã mới hợp lệ). Chèn `ITEM_GIU_CHO` vào
    một giỏ hỗn hợp sẽ thu hẹp phép giao đó và có thể làm nó RỖNG — tức là
    làm hỏng một đơn vốn đang đặt được, vì một dòng khách không hề yêu cầu.

    Giỏ rỗng hoàn toàn (không hàng thật, không dòng đặt ngoài) trả False:
    không có nhu cầu nào để phục vụ, để `portal_order_place` từ chối như cũ.
    """
    return not items and bool(dat_ngoai)


def items_thuoc_hdnt_hieu_luc(customer: str) -> set:
    """BR-R7 / NL-10.7 — tập `item_code` đang thuộc HĐNT CÒN HIỆU LỰC của
    khách. "Còn hiệu lực" dùng ĐÚNG điều kiện `portal_contracts()` đang dùng
    (`blanket_order_type=Selling`, `to_date >= hôm nay`) — không tự dựng một
    định nghĩa "hiệu lực" thứ hai lệch với màn Hợp đồng khách đang thấy.

    CỐ Ý không lọc theo hạn mức còn lại: mặt hàng ĐÃ HẾT hạn mức trong HĐNT
    vẫn phải nằm trong tập này — đó chính xác là tình huống BR-R7 sinh ra để
    chặn (khách hết hạn mức né sang mua lẻ). Chỉ xét "có mặt trong hợp đồng
    còn hiệu lực hay không", không xét "còn hạn mức hay không".

    review M-1 — thêm `docstatus: 1` và `from_date <= hôm nay`: bản trước
    không lọc hai điều kiện này, nên một HĐNT còn NHÁP (docstatus=0, chưa
    ai submit — khách không thể đặt hàng theo nó qua `portal_order_place`,
    `bo.customer`/kiểm ở đó không đòi docstatus nhưng `portal_contracts()`
    thực tế chỉ liệt kê hợp đồng đã ký thật ở Desk) hoặc HĐNT **đã huỷ**
    (docstatus=2) vẫn chặn được mua lẻ — khách rơi vào khe hở "không mua
    HĐNT được (đã huỷ/chưa ký) mà cũng không mua lẻ được". Fail-closed nên
    không phải một lỗ an ninh (không né được hạn mức), nhưng đúng ra khách
    phải mua lẻ được trong tình huống đó. Tương tự, một HĐNT có `from_date`
    ở TƯƠNG LAI (chưa tới hiệu lực) không nên chặn mua lẻ ngay từ bây giờ.
    """
    bo_names = frappe.get_all(
        "Blanket Order",
        filters={
            "customer": customer,
            "blanket_order_type": "Selling",
            "docstatus": 1,
            "from_date": ["<=", frappe.utils.today()],
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

    Rơi về `Global Defaults.default_company` khi phép giao rỗng (không
    company nào có `default_warehouse` cho ĐỦ mọi mặt hàng trong giỏ) —
    quyết định của chủ dự án: một công ty giao hàng ĐOÁN được rồi để nhân
    viên back-office SỬA trên đơn nháp (`Sales Order.docstatus=0`, nơi
    nhân viên vốn đã sửa giá) tốt hơn CHẶN khách đặt hàng vì admin khai
    thiếu `Item Default`. `Sales Order.company` là `reqd=1` trong ERPNext
    nên "để nhân viên điền" không thể là để trống — phải có sẵn một giá
    trị hợp lệ khi đơn về tới Desk.

    Vẫn ưu tiên giá trị SUY ĐƯỢC (khi phép giao khác rỗng) hơn giá trị mặc
    định: company suy từ `Item Default` của chính giỏ hàng đảm bảo kho
    giao thật sự khai cho mọi mặt hàng, còn `default_company` chỉ là một
    phỏng đoán không biết gì về giỏ — dùng nó CHỈ khi không còn lựa chọn
    nào chính xác hơn.

    review I-3 — TẤT ĐỊNH: bản trước dùng `next(iter(candidates))`, một
    phần tử TUỲ Ý của `set` — thứ tự lặp của `set` phụ thuộc hash, có thể
    khác nhau giữa hai lần gọi (khác tiến trình worker, khác lần khởi động
    Python). Trên site nhiều company, HAI lần đặt CÙNG một giỏ có thể ra
    HAI `company` khác nhau — sai sổ, sai kho, sai chuỗi số chứng từ. Ưu
    tiên company mặc định toàn hệ thống (`Global Defaults.default_company`)
    nếu nó nằm trong tập hợp lệ; nếu không, chọn phần tử NHỎ NHẤT theo thứ
    tự chữ cái (`sorted()[0]`) — tất định tuyệt đối, không phụ thuộc hash.
    Cùng giá trị `default_company` này cũng là kết quả fallback khi phép
    giao rỗng, nên toàn hàm chỉ có MỘT nguồn "mặc định", không hai.
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
            candidates = None
            break
    mac_dinh = frappe.defaults.get_global_default("company")
    if not candidates:
        return mac_dinh
    if mac_dinh in candidates:
        return mac_dinh
    return sorted(candidates)[0]


def items_san_sang_giao(item_codes: list[str]) -> set:
    """review I-3 — tập `item_code` CÓ ÍT NHẤT MỘT company với
    `default_warehouse` cấu hình (`Item Default`).

    Dùng cho `portal_catalog_ban_le` để báo tín hiệu "chưa sẵn sàng giao"
    NGAY TẠI DANH MỤC, thay vì để khách điền hết giỏ, chọn địa chỉ, bấm
    Xác nhận rồi mới nhận "Không xác định được công ty giao hàng, liên hệ
    quản trị viên hệ thống" ở bước cuối phễu — một lỗi CẤU HÌNH (admin quên
    khai Item Default khi bật bán lẻ + đặt giá cho mã mới) bị đẩy tới đúng
    người không sửa được nó (khách hàng), ở đúng bước tệ nhất để nhận nó.

    MỘT truy vấn duy nhất cho CẢ danh mục (không lặp `resolve_ban_le_company`
    cho từng dòng — N+1). Không đồng nghĩa "đặt được": khi thật sự đặt,
    `resolve_ban_le_company` còn đòi TOÀN GIỎ đồng thuận một company — kiểm
    đó vẫn chạy lại ở `portal_order_place`, hàm này chỉ là tín hiệu SỚM.
    """
    if not item_codes:
        return set()
    return set(frappe.get_all(
        "Item Default",
        filters={
            "parent": ["in", item_codes], "parenttype": "Item",
            "default_warehouse": ["is", "set"],
        },
        pluck="parent",
    ))


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
        # review M-4 — dữ liệu KHÔNG NHẤT QUÁN (Link trỏ tới bản ghi không
        # còn tồn tại), không phải luồng bình thường. Vẫn không ném lỗi
        # (không được chặn hành động chính), nhưng phải để lại dấu vết.
        frappe.log_error(
            title="cap_nhat_yeu_cau_goc: yêu cầu gốc không tồn tại",
            message=f"SO {so.name}: custom_yeu_cau_goc={ten_yc} không tìm thấy Portal Item Request.",
        )
        return
    yc = frappe.get_doc("Portal Item Request", ten_yc)
    if yc.trang_thai == trang_thai_moi:
        return
    from miyano_portal.miyano_portal.doctype.portal_item_request.portal_item_request import (
        CHUYEN_TRANG_THAI_HOP_LE,
    )
    if trang_thai_moi not in CHUYEN_TRANG_THAI_HOP_LE.get(yc.trang_thai, set()):
        # review M-4 — bản trước nuốt im lặng. Đây thường là dấu hiệu ai đó
        # trên Desk đã tự tay đổi trạng thái yêu cầu trước khi SO tới bước
        # này — vẫn KHÔNG ném lỗi (không được chặn luồng chính: khách đồng
        # ý / job đóng báo giá đã thành công ở SO), chỉ log để điều tra sau.
        frappe.log_error(
            title="cap_nhat_yeu_cau_goc: cạnh chuyển không hợp lệ",
            message=(
                f"SO {so.name}: không chuyển được yêu cầu gốc {ten_yc} từ "
                f"'{yc.trang_thai}' sang '{trang_thai_moi}' — cạnh không có "
                f"trong CHUYEN_TRANG_THAI_HOP_LE."
            ),
        )
        return
    yc.trang_thai = trang_thai_moi
    if trang_thai_moi == "Đã chuyển thành đơn" and not yc.don_lien_ket:
        yc.don_lien_ket = so.name
    yc.save(ignore_permissions=True)
