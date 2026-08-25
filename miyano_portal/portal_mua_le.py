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

# Task 7 — MỘT TÊN cho giá trị `Sales Order.custom_loai_don` đánh dấu "đơn
# này đi qua vòng báo giá của Miyano". Từ Task 4 nó KHÔNG còn nghĩa "đơn mua
# lẻ" (xem `di_vong_bao_gia`), nhưng giá trị lưu trong CSDL thì giữ nguyên vì
# ~118 đơn đã phát sinh mang nó.
#
# Vì sao cần hằng số khi ĐÃ CÓ vị ngữ `di_vong_bao_gia`: ba trong năm nơi
# KHÔNG gọi được hàm Python, chúng buộc phải mang giá trị THÔ —
#   * `portal_bao_gia.quet_bao_gia_het_han` — filter CSDL của `frappe.get_all`
#   * `setup/install_notifications` — chuỗi `condition` chạy qua `safe_eval`
#   * `patches/v1_15/gioi_han_bao_gia_pdf_mua_le` — cùng chuỗi đó, bản patch
# Hai nơi còn lại (`dat_hang` đóng dấu, `di_vong_bao_gia` đọc dấu) gọi được
# hàm nhưng vẫn phải viết ra giá trị.
# Hôm nay cả năm đang khớp. Rủi ro là ngày ai đó đổi vị ngữ mà quên chuỗi
# `condition` và filter CSDL: đơn trong vòng báo giá sẽ THÔI hết hạn và THÔI
# kích thông báo "Báo giá sẵn sàng", trong khi mọi endpoint vẫn coi chúng
# đang trong vòng — im lặng và lệch, đúng kiểu hỏng kế hoạch cảnh báo.
LOAI_DON_BAO_GIA = "Mua lẻ"


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


def di_vong_bao_gia(so) -> bool:
    """Task 6 (QĐ-G2b) — VỊ NGỮ DUY NHẤT cho câu hỏi "đơn này có đi qua vòng
    báo giá của Miyano không?".

    QĐ-G2b, nguyên văn: *"Việc cần làm với nó [`Sales Order.custom_loai_don`]
    không phải xoá, mà là đổi các CHỐT từ 'là đơn Mua lẻ' sang 'có dòng chưa
    có giá'"*. Ruling P8 giữ nguyên field; hàm này là chỗ MỌI chốt hỏi, thay
    cho NĂM chỗ tự so chuỗi `custom_loai_don == "Mua lẻ"`: bốn trong
    `api/portal.py` (banner hiệu lực của `portal_order_track`,
    `portal_bao_gia_pdf`, chốt hết hiệu lực của `portal_order_accept`,
    `portal_order_sua_so_luong`) và bản SOI GƯƠNG trong `Portal De Xuat
    Mua._kiem_don_dung_duoc_xin_sua()`.

    **ĐỌC DẤU ĐÓNG, KHÔNG SUY LẠI TỪ DÒNG.** Hai lý do, cả hai đều là ràng
    buộc chứ không phải sở thích:

    1. *Suy lại từ dòng sẽ lật giữa vòng.* `dat_hang.py` đóng dấu MỘT LẦN
       lúc tạo đơn. Việc CHÍNH của vòng báo giá là Miyano ĐIỀN GIÁ cho những
       dòng chưa có giá — đúng lúc đó một vị ngữ suy lại từ dòng lật sang
       `False` và đơn rơi khỏi vòng báo giá giữa chừng: banner hiệu lực tắt,
       PDF báo giá không tải được, khách hết sửa được số lượng. Xem
       `tests/test_don_tron_bao_gia.py::test_don_tron_da_dien_gia_van_o_
       trong_vong_bao_gia`.
    2. *Hai chốt KHÔNG gọi được hàm Python.* `portal_bao_gia.quet_bao_gia_
       het_han` lọc bằng `frappe.get_all(filters={"custom_loai_don": "Mua
       lẻ"})` — filter CSDL; và Notification "Portal - Báo giá sẵn sàng" lọc
       bằng chuỗi `condition` chạy qua `frappe.safe_eval` trên `doc`
       (`setup/install_notifications.py`). Cả hai buộc phải đọc CỘT. Vị ngữ
       suy lại từ dòng sẽ khiến job/thông báo và các endpoint nói khác nhau
       về CÙNG một đơn — đúng kiểu lệch mà kế hoạch cảnh báo ("hai bên lệch
       nhau, phiếu lại vào ngõ cụt").

    Nói cách khác: giá trị `"Mua lẻ"` là DẤU GHI LẠI ĐƯỜNG đơn đã đi (nó có
    dòng chưa có giá lúc lập đơn nên phải qua Miyano báo giá), không phải
    ảnh chụp tình trạng giá lúc này. Tên hàm nói đúng điều đó — đặt tên nó
    `co_dong_chua_co_gia()` mà thân hàm đọc dấu thì lại là một cái tên nói
    dối về chính mã của mình.

    `so` — `Document` hoặc `dict`/`frappe._dict` có khoá `custom_loai_don`
    (vài endpoint chỉ `db.get_value` vài cột).
    """
    return so.get("custom_loai_don") == LOAI_DON_BAO_GIA


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


def chuyen_dong_dat_ngoai_thanh_hang(doc, method=None) -> None:
    """QĐ-G13 (Task 13, chủ đầu tư chốt 21/08/2026) — **khớp mã thì CHUYỂN,
    không chỉ dán nhãn.**

    Trước task này, điền `item_khop` chỉ bật `da_xu_ly`; grep toàn app không
    có đường mã nào biến một dòng đã khớp thành dòng trong `items`. Hệ quả
    không phải "thiếu ô giá" như triệu chứng ban đầu, mà nặng hơn nhiều: đơn
    QUA ĐƯỢC chốt `before_submit` vì mọi dòng "đã xử lý", trong khi mặt hàng
    khách gõ tay KHÔNG có dòng nào trong đơn, không giá, không vào tổng
    tiền, không lên hoá đơn. Việc duy nhất đã xảy ra là gắn một cái mã vào
    một dòng ghi chú.

    **QĐ-G14 — giá lấy từ HÀM DÙNG CHUNG, không phải phép tra thứ bảy.**
    Hợp đồng thắng cuộc suy bằng `nguon_gia_theo_ma_cho_khach()` (Ruling
    P14/P18) và đơn giá bằng `gia_hdnt.gia_dong_hop_dong()` (QĐ-G12/P30/P31)
    — ĐÚNG hai hàm mà `dat_hang._xay_don` dùng. Sáu nơi đã được gộp về một
    hàm chính vì các phép tra độc lập trôi lệch, và hai trong số đó đã lệch
    tới mức báo cho khách một giá rồi xuất hoá đơn một giá khác. Mã không
    thuộc hợp đồng còn hiệu lực nào → `rate = 0`, chờ Miyano báo giá như mọi
    dòng tầng 2 (KHÔNG ném lỗi thiếu giá: đây là thao tác của nhân viên
    Miyano trên đơn nháp, chặn lưu ở đây là chặn đúng người đang xử lý).

    **Ở hook `before_validate` của Sales Order, KHÔNG ở `validate`** —
    khác một chữ so với bẫy 4 của kế hoạch, và đây là lý do (đã dựng lại
    bằng mã nguồn framework, không phải suy diễn): `Document.hook` chạy
    method của CHÍNH doctype TRƯỚC rồi mới tới hook của app
    (`compose(fn, *hooks)`, `frappe/model/document.py`). Một hook `validate`
    vì vậy chạy SAU `SalesOrder.validate()` — tức sau `set_missing_values`,
    sau `calculate_taxes_and_totals`, sau `validate_warehouse`. Dòng hàng
    thêm vào lúc đó sẽ thiếu `item_name`/`uom`/`conversion_factor`, có
    `amount = 0`, và KHÔNG được cộng vào `total`/`grand_total` — đúng nửa
    sau của triệu chứng ("không vào tổng tiền") mà task này sinh ra để dẹp.
    `before_validate` chạy TRƯỚC toàn bộ dây chuyền đó, nên dòng sinh ra đi
    qua y hệt đường một dòng người dùng gõ tay trong lưới. Phần CẤM của bẫy
    4 vẫn được tôn trọng tuyệt đối: chốt này KHÔNG nằm trong `validate()`
    của doctype con — Frappe không bao giờ gọi hàm đó khi cha lưu.

    Bẫy 5 — phép CHUYỂN (hành động MỚI: dựng thêm dòng hàng) CHỈ chạy khi
    đơn còn nháp, kiểm `docstatus == 0` TƯỜNG MINH. `custom_dat_ngoai` không
    `allow_on_submit`, nhưng dựa vào đó là dựa vào một thuộc tính có thể bị
    đổi bằng một patch ở nơi khác.

    **Important-1 (re-review 25/08) — BẤT BIẾN và CHUYỂN ĐỔI tách làm hai
    tầng, chỉ tầng sau bị chặn theo `docstatus`.** Bản trước thoát ngay ở
    dòng đầu khi `docstatus != 0`, và điều đó bỏ trống nguyên một cửa đi
    thật: `frappe/desk/form/save.py::savedocs` đặt
    `doc.docstatus = SUBMITTED` **rồi mới** gọi `submit()`, còn
    `run_before_save_methods` (`document.py:1138`) vẫn chạy `before_validate`
    cho `_action in ("save", "submit")`. Nên **bấm Submit trên một đơn nháp
    đang dở là MỘT lần lưu duy nhất** đi qua hook với `docstatus == 1` —
    `Document._submit` cũng gán docstatus trước `save()`, nên `so.submit()`
    trong test đi đúng đường đó. Ba thứ đã lọt qua cửa này, cả ba đo được:

      * `_hoan_tac_dong_bi_xoa` không chạy → xoá một dòng gõ tay rồi Submit
        thẳng, số lượng của nó vẫn đi theo đơn vào tiền (`kiem_dat_ngoai_
        da_xu_ly` cho qua, `kiem_dong_chuyen_con_tren_don` cũng cho qua vì
        chốt đó không kiểm số lượng);
      * `_kiem_dong_da_chuyen_khong_doi` không chạy → bẫy 6 bị vượt trong
        một thao tác, dòng bằng chứng bị ghi đè;
      * vệ sinh payload không chạy → một dòng khai `da_chuyen = 1` mà không
        có `dong_hang` được `kiem_dong_chuyen_con_tren_don` BỎ QUA (chốt đó
        chỉ xét dòng CÓ `dong_hang`) và đơn xác nhận với mặt hàng khoa yêu
        cầu vắng mặt — đúng con bug QĐ-G16 ban đầu.

    Từ đây: tầng BẤT BIẾN (ép sổ sách P39, hoàn tác, kiểm bất biến, vệ sinh
    payload, chặn mã giữ chỗ) chạy ở CẢ `docstatus == 0` lẫn `1`; chỉ tầng
    CHUYỂN ĐỔI dừng lại ở đơn nháp.
    """
    if doc.docstatus not in (0, 1):
        return
    con_nhap = doc.docstatus == 0
    dong_go_tay = doc.get("custom_dat_ngoai") or []

    # Bẫy 1 — cờ `da_chuyen` là nguồn sự thật DUY NHẤT cho "đã chuyển chưa",
    # và giá trị đáng tin của nó là giá trị ĐÃ XUỐNG DB, không phải giá trị
    # payload gửi lên: `read_only` chặn được lưới Desk chứ không chặn được
    # một lời gọi API tự tay đặt `da_chuyen = 1` để bỏ qua phép chuyển. Cùng
    # nguyên tắc `da_xu_ly` đã dùng từ đầu ("không tin giá trị client gửi").
    truoc = doc.get_doc_before_save()
    cu = {
        d.name: d
        for d in ((truoc.get("custom_dat_ngoai") or []) if truoc else [])
        if d.name
    }
    # Thoát sớm CHỈ khi không có gì để làm ở CẢ HAI phía. Bản trước thoát
    # theo mỗi `not dong_go_tay`, nên lần lưu XOÁ dòng gõ tay cuối cùng
    # không bao giờ chạy được phép hoàn tác bên dưới — số lượng của nó nằm
    # lại trong dòng hàng vĩnh viễn.
    if not dong_go_tay and not cu:
        return

    # BƯỚC 0 (Critical-1, review 22/08) — HOÀN TÁC phần đóng góp của những
    # dòng gõ tay VỪA BỊ XOÁ khỏi lưới. Phải chạy TRƯỚC vòng chuyển: "xoá
    # dòng khớp nhầm rồi gõ lại" là đúng đường gỡ lỗi mà chính câu báo lỗi
    # bẫy 6 chỉ cho người dùng, và nếu không trừ lại thì phần cũ còn nằm
    # trong dòng hàng, phần mới cộng thêm — 5 thành 10, tiền nhân đôi,
    # trong khi dòng bằng chứng vẫn ghi 5.
    # Ruling P39 (chủ đầu tư chốt 25/08) — ép SỔ SÁCH bám theo `qty` TRƯỚC
    # mọi phép trừ, nếu không phép trừ sẽ dựa trên một con số đã lỗi thời.
    gop = _ep_bat_bien_so_sach(doc, cu, truoc)

    _hoan_tac_dong_bi_xoa(doc, cu, {d.get("name") for d in dong_go_tay}, gop)

    da_chuyen_lan_nay = False
    thang_cuoc = None
    price_list = None
    for dong in dong_go_tay:
        xua = cu.get(dong.get("name"))
        if xua and xua.get("da_chuyen"):
            _kiem_dong_da_chuyen_khong_doi(dong, xua)
            # Giữ nguyên đường nối tới dòng hàng đã tạo, kể cả khi payload
            # gửi lên bỏ trống nó.
            dong.da_chuyen = 1
            dong.dong_hang = xua.get("dong_hang")
            dong.so_luong_da_gop = gop.get(
                dong.get("name"), flt(xua.get("so_luong_da_gop"), 3)
            )
            continue
        if truoc is None and dong.get("da_chuyen") and _neo_lai_ban_sao(doc, dong):
            continue
        # Chưa từng chuyển theo DB → xoá mọi dấu vết "đã chuyển" mà payload
        # có thể mang theo.
        dong.da_chuyen = 0
        dong.dong_hang = None
        dong.so_luong_da_gop = 0
        if not dong.get("item_khop"):
            continue
        if la_dong_giu_cho(dong.item_khop):
            # Cùng chốt với `dat_hang._xay_don` (`mat_hang_giu_cho_khong_the_
            # dat`), ở ĐƯỜNG GHI THỨ HAI. `item_khop` là Link `Item` không
            # lọc gì, còn `ITEM_GIU_CHO` là một Item THẬT, không disabled —
            # nên trên Desk nó chọn được. Không có chốt này, phép gộp (bẫy 2)
            # sẽ dồn số lượng VÀO CHÍNH dòng giữ chỗ, rồi `_go_dong_giu_cho`
            # xoá dòng đó đi: kết cục là `da_chuyen = 1`, `da_xu_ly = 1`,
            # `dong_hang` trỏ tới một dòng không còn tồn tại, và đơn submit
            # được trong khi mặt hàng khách yêu cầu KHÔNG có dòng nào — đúng
            # con bug task này sinh ra để dẹp, đi vào bằng một cửa khác.
            frappe.throw(
                f"Dòng đặt ngoài '{dong.get('ten_hang') or '?'}': {ITEM_GIU_CHO} "
                f"là mã kỹ thuật nội bộ, không phải mặt hàng khớp được. Chọn mã "
                f"hàng thật (hoặc tạo mã mới) cho dòng này.",
                frappe.ValidationError,
            )
        if not con_nhap:
            # Bẫy 5 — CHUYỂN là hành động MỚI, không được xảy ra lặng lẽ
            # ngay trong lần bấm Xác nhận. Dòng này ở lại "chưa xử lý" và
            # `kiem_dat_ngoai_da_xu_ly` giữ đơn lại với câu của nó.
            continue
        if flt(dong.get("so_luong")) <= 0:
            # `dong_bo_da_xu_ly_dat_ngoai` ném lỗi cho đúng dòng này ngay ở
            # `validate` (chạy sau hàm này) — không dựng một dòng hàng số
            # lượng âm/0 rồi mới để đơn hỏng ở nơi khác.
            continue
        if thang_cuoc is None:
            from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
                nguon_gia_theo_ma_cho_khach,
            )
            # Tra MỘT LẦN cho cả đơn, không mỗi dòng một lần.
            thang_cuoc = nguon_gia_theo_ma_cho_khach(doc.customer)
            price_list = frappe.db.get_value(
                "Customer", doc.customer, "default_price_list"
            )
        hang = _gop_hoac_them_dong_hang(
            doc, dong.item_khop, flt(dong.so_luong), thang_cuoc, price_list
        )
        dong.da_chuyen = 1
        dong.dong_hang = hang.name
        dong.so_luong_da_gop = flt(dong.so_luong)
        da_chuyen_lan_nay = True

    if da_chuyen_lan_nay:
        _go_dong_giu_cho(doc)
    _dam_bao_con_dong_hang(doc, con_nhap)
    _kep_so_sach_theo_qty(doc)


def _neo_lai_ban_sao(doc, dong) -> bool:
    """BẢN SAO của một đơn đã chuyển (nút Duplicate trên Desk,
    `frappe.copy_doc`): NEO `dong_hang` vào dòng hàng đã được chép sang, thay
    vì chuyển lần thứ hai. Trả `True` nếu neo được.

    Vì sao cần một nhánh riêng: bản sao đi qua `insert()`, ở đó KHÔNG có
    `doc_before_save` nào để đối chiếu — nên nhánh thường coi dòng gõ tay là
    "chưa chuyển" và cộng số lượng vào chính dòng hàng vừa được chép sang
    (đo được: 5 thành 10). `no_copy = 1` trên `da_chuyen` KHÔNG cứu được:
    hàng hoá vẫn được chép, chỉ là cờ về 0 rồi phép chuyển cộng thêm lần nữa.
    `dong_hang` chép sang trỏ tới TÊN dòng của bản GỐC, không tồn tại ở đây,
    nên phải neo lại theo `item_khop`.

    Đây là chỗ DUY NHẤT trong toàn hàm tin một giá trị `da_chuyen` do payload
    mang tới, nên phép kiểm phải chặt hơn "có dòng nào cùng mã không":

      * đòi dòng hàng đó mang **đủ số lượng** dòng gõ tay yêu cầu
        (`qty >= so_luong`). Chỉ kiểm sự tồn tại thì một payload dựng tay có
        thể khai `da_chuyen = 1` cho một yêu cầu 100 hộp trong khi đơn chỉ
        có 1 hộp, và `da_xu_ly = 1` lại nói dối một lần nữa — đúng lớp lỗi
        QĐ-G16 vừa dẹp, chỉ nhỏ hơn;
      * không neo được thì KHÔNG throw mà rơi xuống nhánh chuyển bình
        thường — mặt hàng khách yêu cầu vẫn phải có mặt trên đơn với đủ số
        lượng, đó mới là điều bất biến cần giữ.

    Chỉ chạy ở đúng đường ghi này (`insert`), KHÔNG ở mọi lần lưu: bẫy 1 cấm
    dùng "có dòng nào cùng `item_code` không" làm phép kiểm thường trực, vì
    dòng đó có thể có mặt vì lý do khác.
    """
    if not dong.get("item_khop"):
        return False
    for hang in doc.get("items") or []:
        if hang.item_code != dong.item_khop:
            continue
        if flt(hang.qty) < flt(dong.so_luong):
            return False
        dong.da_chuyen = 1
        dong.dong_hang = hang.name
        # **"VẮNG MẶT" ≠ "BẰNG 0"** (re-review 25/08 — lỗ do chính vòng
        # trước tạo ra). Bản trước đọc `not flt(so_luong_da_gop)` (falsy) là
        # "bản ghi cũ, cột chưa tồn tại" rồi GHI ĐÈ bằng `so_luong`. Trước
        # Ruling P39, `da_chuyen = 1` kèm sổ sách 0 quả thật chỉ sinh ra từ
        # dữ liệu cũ — nhưng P39 khiến nó thành trạng thái BÌNH THƯỜNG VÀ
        # ĐÚNG (dòng nhường hết phần của mình khi sales hạ tay `qty`). Ghi
        # đè lúc đó thổi sổ sách của bản sao vượt `qty`, và lần xoá kế tiếp
        # ăn mất phần khách ĐẶT THẲNG — Important-2 quay lại qua cửa nhân
        # bản.
        #
        # Cách phân biệt: KHÔNG đoán từ giá trị nữa. Giá trị chép sang là
        # sự thật của bản gốc (nơi bất biến P39 đang đứng), cứ mang nguyên
        # sang — kể cả `0`. Còn "vắng mặt thật" (payload dựng tay thiếu
        # hẳn field) rơi về `0` qua `flt(None)`, và `0` ở đây là AN TOÀN:
        # nó nghĩa "dòng này không đòi gì trên dòng hàng", nên phép hoàn
        # tác không trừ gì cả — sai theo hướng giữ lại số lượng, không bao
        # giờ theo hướng ăn mất. Dữ liệu cũ thật thì đã được patch
        # `them_cot_so_luong_da_gop` backfill từ trước.
        dong.so_luong_da_gop = flt(dong.get("so_luong_da_gop"), 3)
        return True
    return False


def _ep_bat_bien_so_sach(doc, cu: dict, truoc) -> dict:
    """**Ruling P39 (chủ đầu tư chốt 25/08)** — giữ SỔ SÁCH luôn trung thực.

    Bất biến, ép ở MỌI lần lưu, cho MỖI dòng hàng:

        tổng `so_luong_da_gop` của các dòng gõ tay trỏ vào nó  ≤  `qty` của nó

    Trả `{tên dòng gõ tay: so_luong_da_gop đã điều chỉnh}` để mọi phép tính
    phía sau (hoàn tác, chép sang dòng còn sống) đọc CÙNG một con số.

    **KHÔNG chặn `qty` nhỏ hơn tổng khoa yêu cầu.** Dòng gõ tay ghi thứ khoa
    YÊU CẦU; dòng hàng ghi thứ Miyano SẼ GIAO. Hai con số được phép khác
    nhau — giao một phần, hoặc thương lượng giảm, đều là nghiệp vụ thật, và
    chặn nó là bắt hệ thống phủ quyết một quyết định thương mại. Muốn cấm
    giao thiếu thì phải dựng một chốt NGHIỆP VỤ có chủ đích, không phải một
    hệ quả phụ của sổ sách.

    **Phần giảm ăn vào phần ĐÃ GỘP trước, phần khách ĐẶT THẲNG giữ nguyên.**
    `phần đặt thẳng = qty − tổng đã gộp` là một con số suy ra, không được
    lưu ở đâu cả; nếu phép giảm hạ sổ sách xuống thẳng `qty` thì phần đặt
    thẳng bị đẩy về 0 và biến mất khỏi sổ — rồi lần xoá dòng gõ tay kế tiếp
    trừ nốt, làm bốc hơi IM LẶNG số hàng khách đã tự tay đặt (hố
    Important-2, đo được trên Desk thường). Ăn vào phần đã gộp trước giữ
    đúng phần đặt thẳng chừng nào còn chỗ.

    Thứ tự nhường TẤT ĐỊNH: dòng gõ tay nhập SAU nhường trước (`idx` giảm
    dần) — yêu cầu tới trước được phục vụ trước, và không lần chạy nào phụ
    thuộc thứ tự lặp của `dict`.

    **`so_luong` của dòng gõ tay KHÔNG BAO GIỜ đổi** — đó là bằng chứng khoa
    đã xin bao nhiêu (QĐ-G15), nó không chạy theo quyết định giao hàng. Chỉ
    con số SỔ SÁCH `so_luong_da_gop` mới bám theo.
    """
    gop = {
        ten: flt(xua.get("so_luong_da_gop"), 3)
        for ten, xua in cu.items()
        if xua.get("da_chuyen") and xua.get("dong_hang")
    }
    if not gop or truoc is None:
        # `insert` không có mốc `qty` trước để so; giá trị sổ sách của bản
        # sao do `_neo_lai_ban_sao` đặt, và nó đã tự đòi `qty >= so_luong`.
        return gop

    qty_cu = {h.name: flt(h.qty, 3) for h in (truoc.get("items") or []) if h.name}
    qty_moi = {h.name: flt(h.qty, 3) for h in (doc.get("items") or []) if h.name}

    theo_hang: dict = {}
    for ten in gop:
        theo_hang.setdefault(cu[ten].get("dong_hang"), []).append(ten)

    for ten_hang, ds in theo_hang.items():
        if ten_hang not in qty_moi:
            # Dòng hàng đã bị xoá khỏi đơn — `kiem_dong_chuyen_con_tren_don`
            # lo phần đó ở `before_submit`, không đoán mò ở đây.
            continue
        tong = flt(sum(gop[t] for t in ds), 3)
        giam = flt(qty_cu.get(ten_hang, tong) - qty_moi[ten_hang], 3)
        # `min(..., qty_moi)` là lưới an toàn cho dữ liệu cũ/không nhất quán
        # (bản ghi có từ trước bất biến này): kể cả khi `qty` không giảm lần
        # nào, sổ sách vẫn không được phép vượt `qty`.
        muc_tieu = flt(min(max(0.0, tong - max(0.0, giam)), qty_moi[ten_hang]), 3)
        du = flt(tong - muc_tieu, 3)
        if du <= 0:
            continue
        for ten in sorted(ds, key=lambda t: flt(cu[t].get("idx")), reverse=True):
            if du <= 0:
                break
            bot = min(gop[ten], du)
            gop[ten] = flt(gop[ten] - bot, 3)
            du = flt(du - bot, 3)
    return gop


def _hoan_tac_dong_bi_xoa(doc, cu: dict, con_lai: set, gop: dict) -> None:
    """Trừ lại phần số lượng của những dòng gõ tay ĐÃ CHUYỂN vừa bị xoá khỏi
    lưới; dòng hàng chỉ còn đúng phần của nó thì gỡ hẳn.

    `so_luong_da_gop` là con số DUY NHẤT trả lời được "phần nào của dòng hàng
    này tới từ dòng gõ tay" sau khi bẫy 2 đã gộp. Không có nó thì phép hoàn
    tác hoặc trừ thiếu (để lại số lượng ma) hoặc trừ lẫn cả phần khách đã đặt
    trực tiếp. Đây đúng là "cột sổ sách thứ ba" mà bản đầu của task này gọi
    tên rồi từ chối dựng — và chính chỗ từ chối đó là cái lỗ.

    Từ Ruling P39, phần trừ đọc từ map `gop` do `_ep_bat_bien_so_sach` trả
    về (sổ sách đã bám theo `qty`), KHÔNG đọc thẳng giá trị trong DB — nếu
    không, một lần hạ tay `qty` trước đó sẽ khiến phép trừ dựa trên con số
    đã lỗi thời. Khi bất biến P39 đứng thì `tru ≤ tổng đã gộp ≤ qty`, nên
    `con ≥ san` luôn đúng và cái SÀN dưới đây không bao giờ ràng buộc; giữ
    nó làm lớp phòng thủ thứ hai cho dữ liệu cũ và cho trường hợp bất biến
    bị thủng ở đâu đó.

    Im lặng bỏ qua khi không đối chiếu được (dòng hàng đã bị người khác
    xoá/đổi mã, hoặc bản ghi cũ chưa có cột sổ sách): KHÔNG đoán mò một con
    số để trừ. Phần lệch còn lại do `kiem_dong_chuyen_con_tren_don` bắt ở
    `before_submit`.
    """
    theo_ten = {h.name: h for h in (doc.get("items") or []) if h.name}

    # Gom theo DÒNG HÀNG, không xử lý từng dòng gõ tay một. Một dòng hàng có
    # thể có NHIỀU chủ (khách đặt trực tiếp + nhiều dòng gõ tay cùng khớp về
    # một mã, bẫy 2). Trừ lần lượt từng chủ thì THỨ TỰ LẶP quyết định kết
    # quả: chủ nào bị xử lý lúc số dư đã cạn sẽ kéo gỡ cả dòng, cuốn theo
    # phần của những chủ còn lại.
    tru: dict = {}
    for ten, xua in cu.items():
        if ten in con_lai or not xua.get("da_chuyen"):
            continue
        phan_gop = flt(gop.get(ten), 3)
        hang = theo_ten.get(xua.get("dong_hang"))
        if not phan_gop or not hang or hang.item_code != xua.get("item_khop"):
            continue
        tru[hang.name] = flt(tru.get(hang.name, 0.0) + phan_gop, 3)
    if not tru:
        return

    # SÀN — phần những dòng gõ tay CÒN LẠI vẫn đang đòi ở mỗi dòng hàng.
    # Đọc từ bản ghi ĐÃ XUỐNG DB (`cu`), không từ payload, cùng nguyên tắc
    # với `da_chuyen`. Cần cái sàn này vì `qty` của dòng hàng SỬA ĐƯỢC bằng
    # tay trên đơn nháp (chính câu báo lỗi bẫy 6 bảo người dùng làm thế):
    # sau khi sales hạ 9 xuống 4, tổng "đã gộp" ghi trên các dòng gõ tay đã
    # lớn hơn số lượng thật, và một phép trừ mù sẽ ra số âm rồi gỡ hẳn dòng
    # hàng — làm bốc hơi cả phần của chủ khác. Đã dựng lại được trên bench.
    con_giu: dict = {}
    for d in doc.get("custom_dat_ngoai") or []:
        xua = cu.get(d.get("name"))
        if not xua or not xua.get("da_chuyen") or not xua.get("dong_hang"):
            continue
        hang = theo_ten.get(xua.get("dong_hang"))
        # ĐỐI XỨNG với `tru` ở trên: cùng phép kiểm `item_code`. Thiếu nó,
        # một dòng còn lại mà `item_code` của dòng hàng đã bị đổi vẫn thổi
        # phồng cái sàn và chặn mất phép trừ hợp lệ.
        if not hang or hang.item_code != xua.get("item_khop"):
            continue
        con_giu[xua.get("dong_hang")] = flt(
            con_giu.get(xua.get("dong_hang"), 0.0) + flt(gop.get(d.get("name")), 3), 3
        )

    bo = set()
    for ten_hang, tong_tru in tru.items():
        hang = theo_ten[ten_hang]
        san = flt(con_giu.get(ten_hang, 0.0), 3)
        # `flt(..., 3)` chứ không phải số thực thô: `qty` và `so_luong_da_gop`
        # đều là `decimal(21,3)`, nhưng TỔNG của chúng trong Python lệch vài
        # ULP. Một `con` còn 2.2e-16 sẽ lớn hơn `san = 0`, được gán vào
        # `qty`, rồi làm tròn thành `0.000` lúc lưu và rơi vào
        # `validate_qty_is_not_zero` của ERPNext — người dùng nhận một câu
        # của framework thay vì dòng hàng được gỡ sạch.
        con = flt(flt(hang.qty, 3) - tong_tru, 3)
        if con > san:
            hang.qty = con
        elif san > 0:
            # Còn chủ khác đang đòi phần của họ — không gỡ dòng, và không
            # trừ xuống dưới đúng phần họ đòi.
            hang.qty = san
        else:
            bo.add(ten_hang)
    if bo:
        doc.items = [h for h in doc.get("items") or [] if h.name not in bo]
        for idx, hang in enumerate(doc.get("items") or [], start=1):
            hang.idx = idx


def _kep_so_sach_theo_qty(doc) -> None:
    """Lớp kẹp CUỐI CÙNG của Ruling P39, chạy sau MỌI thay đổi trong một lần
    lưu: với mỗi dòng hàng, tổng `so_luong_da_gop` của các dòng gõ tay trỏ
    vào nó không được vượt `qty` của nó.

    Vì sao cần thêm một lớp nữa dù `_ep_bat_bien_so_sach` đã chạy ở đầu:
    hàm đó đối chiếu `truoc` với hiện tại, nên nó **không có gì để so ở lần
    `insert`** (`truoc is None`) — đúng đường mà một BẢN SAO đi vào. Kẹp ở
    đây đọc thẳng trạng thái CUỐI của document, không cần mốc trước, nên nó
    phủ được cả bản sao lẫn payload dựng tay, và nó là chỗ bất biến P39
    được bảo đảm chứ không chỉ được mong đợi.

    Cùng thứ tự nhường TẤT ĐỊNH với `_ep_bat_bien_so_sach`: dòng gõ tay
    nhập SAU nhường trước (`idx` giảm dần).

    Ở luồng bình thường đây là no-op: phép chuyển luôn cộng `qty` đúng bằng
    phần nó ghi vào sổ sách.
    """
    theo_hang: dict = {}
    for dong in doc.get("custom_dat_ngoai") or []:
        if dong.get("da_chuyen") and dong.get("dong_hang"):
            theo_hang.setdefault(dong.get("dong_hang"), []).append(dong)
    if not theo_hang:
        return
    qty = {h.name: flt(h.qty, 3) for h in (doc.get("items") or []) if h.name}
    for ten_hang, ds in theo_hang.items():
        if ten_hang not in qty:
            # Dòng hàng không còn — `kiem_dong_chuyen_con_tren_don` lo ở
            # `before_submit`, không đoán mò ở đây.
            continue
        tong = flt(sum(flt(d.get("so_luong_da_gop"), 3) for d in ds), 3)
        du = flt(tong - qty[ten_hang], 3)
        if du <= 0:
            continue
        for dong in sorted(ds, key=lambda x: flt(x.get("idx")), reverse=True):
            if du <= 0:
                break
            hien = flt(dong.get("so_luong_da_gop"), 3)
            bot = min(hien, du)
            dong.so_luong_da_gop = flt(hien - bot, 3)
            du = flt(du - bot, 3)


def _dam_bao_con_dong_hang(doc, con_nhap: bool = True) -> None:
    """ERPNext KHÔNG lưu nổi một Sales Order với bảng `items` RỖNG
    (`calculate_taxes_and_totals` không có gì để tính, `grand_total` là
    `None`) — xác nhận thực nghiệm, ghi ở `dat_hang._xay_don`.

    Phép hoàn tác phía trên có thể vét cạn `items`: đơn TOÀN hàng gõ tay đã
    khớp mã thì dòng giữ chỗ đã bị gỡ (bẫy 3), nên `items` chỉ còn đúng dòng
    vừa sinh — xoá dòng gõ tay đi là hết sạch. Trả đơn về đúng hình dạng
    §3.4 của nó (một dòng giữ chỗ) thay vì để framework ném một câu không
    nói cho nhân viên biết chuyện gì vừa xảy ra.
    """
    if doc.get("items"):
        return
    if not con_nhap:
        # Đang XÁC NHẬN đơn. Dòng giữ chỗ là hình dạng của một đơn NHÁP
        # (§3.4); chèn nó vào lúc này chỉ dẫn tới việc
        # `kiem_khong_con_dong_giu_cho` từ chối bằng một câu nói về DÒNG GIỮ
        # CHỖ — chặn đúng nhưng kể sai chuyện, người dùng vừa xoá dòng hàng
        # chứ không hề thêm dòng giữ chỗ nào.
        #
        # Để `items` rỗng và NHƯỜNG LỜI cho hai chốt `before_submit` vốn nói
        # đúng nguyên nhân hơn hẳn: `kiem_dat_ngoai_da_xu_ly` ("còn dòng
        # chưa xử lý") và `kiem_dong_chuyen_con_tren_don` ("dòng hàng tương
        # ứng đã bị xoá hoặc đổi mã"). Chỉ tự lên tiếng khi cả hai chốt đó
        # đều không có gì để nói — nếu không thì đơn rỗng sẽ chạm tới
        # `MandatoryError: items` của framework.
        ds = doc.get("custom_dat_ngoai") or []
        chot_khac_se_noi = any(not d.get("da_chuyen") for d in ds) or any(
            d.get("da_chuyen") and d.get("dong_hang") for d in ds
        )
        if not chot_khac_se_noi:
            frappe.throw(
                "Đơn không còn dòng hàng nào để xác nhận — mọi dòng hàng đã bị "
                "xoá khỏi đơn. Thêm lại dòng hàng (hoặc khớp mã lại cho các "
                "dòng đặt ngoài) trước khi xác nhận đơn.",
                frappe.ValidationError,
            )
        return
    if not doc.get("custom_dat_ngoai"):
        # Không còn dòng hàng NÀO và cũng không còn dòng gõ tay nào: đơn
        # rỗng, không có nhu cầu nào để phục vụ. ERPNext sẽ ném
        # `MandatoryError: items` — nói thẳng ra thì hơn.
        # Câu chữ CỐ Ý không đoán nguyên nhân: nhánh này tới được cả khi
        # nhân viên tự tay xoá sạch `items` trên một đơn nháp, không riêng
        # khi phép hoàn tác vét cạn. Nói "xoá dòng gõ tay cuối cùng" ở đó là
        # mô tả một việc người dùng không hề làm.
        frappe.throw(
            "Đơn này không còn dòng hàng nào và cũng không còn dòng gõ tay nào "
            "— một đơn rỗng không lưu được. Thêm một mặt hàng vào đơn, hoặc "
            "huỷ hẳn đơn nháp này.",
            frappe.ValidationError,
        )
    if not frappe.db.exists("Item", ITEM_GIU_CHO):
        return
    from miyano_portal.dat_hang import _resolve_item_warehouse

    doc.append("items", {
        "item_code": ITEM_GIU_CHO,
        "qty": 1,
        "rate": 0,
        "price_list_rate": 0,
        "warehouse": _resolve_item_warehouse(ITEM_GIU_CHO, doc.company),
        "delivery_date": doc.get("delivery_date"),
    })


def _kiem_dong_da_chuyen_khong_doi(dong, xua) -> None:
    """Bẫy 6 — đổi `so_luong` (hoặc `item_khop`) SAU khi dòng đã chuyển:
    **CHẶN**, không đồng bộ. Lý do, ghi để không phải phát hiện lại:

    Phép chuyển GỘP số lượng vào dòng `items` sẵn có khi mã trùng (bẫy 2 —
    hai dòng cùng `item_code` trên một Sales Order là mồi cho lệch hạn mức
    và lệch hoá đơn). Sau khi đã gộp, câu hỏi "phần nào của dòng hàng này
    tới từ dòng gõ tay" KHÔNG còn câu trả lời trung thực nào nếu không dựng
    thêm một cột sổ sách thứ ba. Đồng bộ mù sẽ ghi đè cả phần số lượng do
    người khác đặt. Chặn thì không cần trạng thái mới, và nó ăn khớp với
    QĐ-G15: dòng gõ tay là BẰNG CHỨNG yêu cầu gốc — bằng chứng không được
    sửa sau khi đã dùng.

    Chặn ở đây KHÔNG tạo ngõ cụt (đã kiểm thực nghiệm trên bench): đơn còn
    `docstatus = 0` nên chính dòng gõ tay này vẫn XOÁ được khỏi lưới, nên
    một lần khớp nhầm mã vẫn gỡ lại được — câu báo lỗi phải nói ra đường
    gỡ đó, chứ không chỉ nói "không được".
    """
    doi_so_luong = flt(dong.get("so_luong")) != flt(xua.get("so_luong"))
    doi_ma = (dong.get("item_khop") or "") != (xua.get("item_khop") or "")
    if not (doi_so_luong or doi_ma):
        return
    frappe.throw(
        f"Dòng đặt ngoài '{xua.get('ten_hang') or '?'}' đã chuyển thành dòng hàng "
        f"{xua.get('item_khop')} trên đơn — không sửa được số lượng hay mã khớp "
        f"trên dòng gõ tay nữa (dòng gõ tay là bằng chứng yêu cầu gốc của khoa). "
        f"Sửa số lượng ngay trên dòng hàng {xua.get('item_khop')}; nếu khớp nhầm "
        f"mã thì XOÁ DÒNG GÕ TAY NÀY khỏi đơn nháp rồi nhập lại — hệ sẽ tự trừ "
        f"lại đúng phần số lượng nó đã gộp vào dòng hàng, không phải xoá tay "
        f"dòng hàng.",
        frappe.ValidationError,
    )


def _gop_hoac_them_dong_hang(doc, item_code: str, qty: float, thang_cuoc: dict,
                             price_list):
    """Trả về dòng `Sales Order Item` mang mặt hàng này — GỘP vào dòng sẵn
    có nếu đã có, ngược lại thêm mới. Bẫy 2: không bao giờ để hai dòng cùng
    `item_code` đứng trên một Sales Order.

    Dòng GỘP giữ nguyên `rate`/`blanket_order` ĐÃ CÓ — dòng đó đã được định
    giá theo đúng luật ở đường dựng đơn, chuyện xảy ra ở đây chỉ là khách
    cần thêm số lượng, và giá đã chốt là giá Miyano đàm phán/đã báo cho
    khách, không ai được đè lên.

    Nhưng dòng sẵn có CHƯA có giá / CHƯA gắn hợp đồng thì phép gộp phải DÁN
    vào (Critical-2, review 22/08 — dựng lại được trên bench). Vòng lặp
    nghiệp vụ chủ đầu tư mô tả 21/08 tới thẳng ca này mà không ai phải sửa
    tay: khoa đặt một mặt hàng lúc nó còn NGOÀI hợp đồng (dòng tầng 2,
    `rate = 0`), Miyano bổ sung chính mặt hàng đó vào hợp đồng khung và ký,
    rồi khớp một dòng gõ tay về đúng mã đó. Bản trước `return` ngay và VỨT
    con số 88.000 vừa tính cùng cả `blanket_order`, nên TOÀN BỘ số lượng
    (cũ lẫn mới) submit được với `grand_total = 0` và không trừ hạn mức nào
    — đúng nửa còn lại của con bug QĐ-G13 dẹp, đi vào bằng đường gộp.

    Vì thế giá/hợp đồng phải tính TRƯỚC vòng gộp, không phải sau nó.
    """
    # Import tại chỗ: `dat_hang` import ngược lại module này ở tầng module
    # (ITEM_GIU_CHO, can_chen_giu_cho, resolve_ban_le_company...), nên import
    # ở đầu file sẽ thành vòng.
    from frappe.model.naming import set_new_name

    from miyano_portal import gia_hdnt
    from miyano_portal.dat_hang import _resolve_item_warehouse
    from miyano_portal.portal_context import han_muc_con

    bo_dong = thang_cuoc.get(item_code)
    # QĐ-G14 — CHỈ dòng thuộc một hợp đồng còn hiệu lực mới được hỏi giá.
    # Dòng tầng 2 nhận thẳng `rate = 0` và KHÔNG rơi xuống bảng giá: đó
    # đúng là hành vi của `dat_hang._xay_don` cho tầng 2 (bước 2 "Item
    # Price" của QĐ-G12 là bước LUI CỦA DÒNG HỢP ĐỒNG, không phải một
    # nguồn giá cho hàng ngoài hợp đồng). Gọi `gia_dong_hop_dong` vô điều
    # kiện sẽ đọc trúng một giá bảng giá cũ và ghi nó lên đơn — trong khi
    # cùng mặt hàng đó, đặt qua giỏ hàng, lại ra 0 và chờ Miyano báo giá.
    # Hai con số cho một mặt hàng tuỳ đường đi: đúng lớp lệch giá dự án này
    # đã trả giá (Ruling P28/P30).
    rate = (
        flt(gia_hdnt.gia_dong_hop_dong(item_code, bo_dong, price_list))
        if bo_dong else 0.0
    )
    # BR-O15 — hạn mức khai 0 nghĩa KHÔNG GIỚI HẠN. KHÔNG gắn
    # `against_blanket_order` cho dòng đó: cơ chế gốc của ERPNext đối chiếu
    # cờ này với `qty` của Blanket Order Item, thấy 0 thì hiểu là CẤM ĐẶT và
    # chặn ngay lúc submit. Y hệt nhánh `con_lai is None` của `_xay_don` —
    # một luật, hai nơi thi hành giống nhau.
    gan_hop_dong = None
    if bo_dong:
        con_lai, _da_dat = han_muc_con(bo_dong, item_code)
        if con_lai is not None:
            gan_hop_dong = bo_dong

    # ---- BẪY 2 — GỘP vào dòng sẵn có, không thêm dòng thứ hai cùng mã ----
    for hang in doc.get("items") or []:
        if hang.item_code != item_code:
            continue
        hang.qty = flt(hang.qty) + qty
        if rate and not flt(hang.rate):
            # Dòng sẵn có đang CHỜ BÁO GIÁ mà mặt hàng thì đã có giá hợp
            # đồng — không im lặng để cả cụm số lượng đi tiếp với 0 đồng.
            # CHỈ điền vào chỗ trống, xem docstring.
            hang.rate = rate
            hang.price_list_rate = 0
        if gan_hop_dong and not hang.get("blanket_order"):
            hang.blanket_order = gan_hop_dong
            hang.against_blanket_order = 1
        return hang

    kho = _resolve_item_warehouse(item_code, doc.company)
    if not kho:
        frappe.throw(
            f"Không tìm thấy kho giao hàng cho mặt hàng {item_code} tại công ty "
            f"{doc.company} — chưa chuyển được dòng đặt ngoài thành dòng hàng. "
            f"Vui lòng liên hệ quản trị viên hệ thống.",
            frappe.ValidationError,
        )

    moi = {
        "item_code": item_code,
        "qty": qty,
        "rate": rate,
        "warehouse": kho,
        "delivery_date": doc.get("delivery_date"),
    }
    if not rate:
        # BẪY ERPNext, giống hệt `dat_hang._xay_don`:
        # `taxes_and_totals.calculate_item_values` có nhánh `elif
        # item.price_list_rate: if not item.rate: item.rate =
        # price_list_rate` — `rate = 0` là FALSY nên ERPNext ÂM THẦM thay 0
        # bằng giá trong bảng giá của đơn. Đơn có dòng hợp đồng mang chính
        # bảng giá của khách, nên nhánh này KÍCH HOẠT THẬT. Gán tường minh
        # `price_list_rate = 0` để `set_missing_item_details` không điền hộ
        # (nó chỉ điền khi field đang là `None`).
        moi["price_list_rate"] = 0
    if gan_hop_dong:
        moi["blanket_order"] = gan_hop_dong
        moi["against_blanket_order"] = 1

    hang = doc.append("items", moi)
    # Đặt tên NGAY: `set_name_in_children()` đã chạy xong TRƯỚC
    # `run_before_save_methods()`, nên một dòng con thêm vào ở đây còn
    # `name = None` cho tới tận `db_insert`. Không có tên thì `dong_hang`
    # (đường nối bằng chứng ↔ tiền, QĐ-G15) ghi được một giá trị rỗng và im
    # lặng. `db_insert` chỉ tự đặt tên khi `name` còn trống nên gọi ở đây là
    # an toàn, không tranh chấp.
    set_new_name(hang)
    return hang


def _go_dong_giu_cho(doc) -> None:
    """Bẫy 3 — đơn đã có hàng thật thì GỠ dòng giữ chỗ `ITEM_GIU_CHO`.

    `kiem_khong_con_dong_giu_cho` (`before_submit`) sẽ chặn xác nhận nếu nó
    còn, và mẫu in "Miyano - Xác nhận đơn hàng" — chứng từ khách THẬT SỰ
    nhận — không lọc nó.

    CHỈ gỡ khi lần lưu này VỪA chuyển được ít nhất một dòng (người gọi kiểm,
    không phải hàm này): gỡ vô điều kiện ở mọi lần lưu sẽ khiến chốt
    `kiem_khong_con_dong_giu_cho` không bao giờ với tới được — mà chốt đó
    sinh ra cho tình huống KHÁC (sales tự tay để sót dòng giữ chỗ trong
    `items`), không phải cho tình huống này.

    Không bao giờ để `items` rỗng: ERPNext không lưu nổi Sales Order với
    bảng `items` rỗng (`calculate_taxes_and_totals` không có gì để tính,
    `grand_total` là `None`) — nhưng nhánh đó không tới được ở đây vì hàm
    chỉ chạy sau khi vừa thêm một dòng hàng thật.
    """
    tat_ca = doc.get("items") or []
    con_lai = [i for i in tat_ca if not la_dong_giu_cho(i.item_code)]
    if not con_lai or len(con_lai) == len(tat_ca):
        return
    doc.items = con_lai
    for idx, hang in enumerate(doc.items, start=1):
        hang.idx = idx


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
    này là chính hàm này — server tự suy ra, không tin giá trị `da_xu_ly`
    client gửi lên (nếu có).

    **QĐ-G16 (Task 13, 21/08/2026) — ĐỔI NGUỒN SUY, đổi luôn NGHĨA.** Trước
    task này `da_xu_ly` suy từ `item_khop`, tức nghĩa "đã gắn một cái mã".
    Nhưng chốt `kiem_dat_ngoai_da_xu_ly` (`before_submit`) đọc nó như "đã
    lo xong" — nên nó ĐANG NÓI DỐI: đơn qua được chốt xác nhận trong khi
    mặt hàng khách gõ tay không có dòng nào trong `items`, không giá, không
    vào tổng tiền, không lên hoá đơn. Từ đây nó suy từ `da_chuyen` — cờ chỉ
    được bật bởi `chuyen_dong_dat_ngoai_thanh_hang()` SAU khi dòng hàng
    thật đã tồn tại. `da_xu_ly = 1` khi và chỉ khi dòng đã CHUYỂN.
    """
    for dong in doc.get("custom_dat_ngoai") or []:
        dong.da_xu_ly = 1 if dong.get("da_chuyen") else 0
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


def kiem_dong_chuyen_con_tren_don(doc, method=None) -> None:
    """Critical-3 (review Task 13, 22/08) — CHỐT MỚI: `da_xu_ly = 1` phải có
    một dòng hàng THẬT đứng sau nó NGAY TẠI LÚC xác nhận đơn.

    `dong_bo_da_xu_ly_dat_ngoai` suy `da_xu_ly` từ `da_chuyen`, và `da_chuyen`
    được bật đúng lúc dòng hàng ra đời — nhưng KHÔNG có gì canh khoảng thời
    gian giữa lúc đó và lúc submit. Nhân viên Desk xoá dòng `items` do phép
    chuyển sinh ra (một thao tác lưới bình thường, không cảnh báo gì) thì
    `da_chuyen`/`da_xu_ly` vẫn bằng 1, `dong_hang` trỏ tới một dòng không còn
    tồn tại, và đơn XÁC NHẬN ĐƯỢC với mặt hàng khoa yêu cầu KHÔNG có dòng
    nào, không giá, không lên hoá đơn — đo được trên bench. Cùng LỚP lỗi
    QĐ-G16 dẹp, tới bằng cửa XOÁ thay vì cửa khớp mã.

    Đối chiếu bằng TÊN dòng (`dong_hang`) VÀ `item_code`: đổi mã ngay trên
    dòng hàng đã tạo cũng làm bằng chứng nói dối y hệt, chỉ khó thấy hơn.

    Bỏ qua dòng chưa có `dong_hang` (đơn nháp mở từ trước bản vá này) —
    `kiem_dat_ngoai_da_xu_ly` vẫn canh phần "đã xử lý hay chưa" cho chúng.

    Đứng ở `before_submit` chứ không ở `validate`: giữa hai lần lưu, một đơn
    nháp được phép ở trạng thái dở dang (sales xoá dòng hàng rồi dựng lại).
    Thứ không được phép là đơn ĐI TIẾP trong trạng thái đó.
    """
    ten_dong = {h.name: h for h in (doc.get("items") or []) if h.name}
    hong = []
    for dong in doc.get("custom_dat_ngoai") or []:
        if not dong.get("da_chuyen") or not dong.get("dong_hang"):
            continue
        hang = ten_dong.get(dong.get("dong_hang"))
        if not hang or hang.item_code != dong.get("item_khop"):
            hong.append(dong)
    if not hong:
        return
    ten = ", ".join(f"{d.get('ten_hang') or '?'} → {d.get('item_khop')}" for d in hong)
    frappe.throw(
        f"Còn {len(hong)} dòng đặt ngoài ghi \"đã xử lý\" nhưng dòng hàng tương "
        f"ứng đã bị xoá hoặc đổi mã ({ten}). Xác nhận đơn lúc này nghĩa là mặt "
        f"hàng khoa yêu cầu KHÔNG có dòng nào trên đơn, không giá, không lên "
        f"hoá đơn. Thêm lại dòng hàng, hoặc xoá dòng gõ tay tương ứng khỏi đơn "
        f"nháp rồi khớp mã lại.",
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
