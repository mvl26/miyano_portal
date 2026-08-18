"""Thông báo từ Miyano/hệ thống SANG khách hàng (chiều ngược với
`portal_thong_bao.py`, module đó khai rõ là "cổng sang nhân viên Miyano").

Brief 2026-08-15 (trang thông báo) — hai việc:

1. **Resolve** (Phần 3, `kho/delivery_hook.py` gọi `bao_da_nhap_hang`): thông
   báo "đã nhập hàng" KHÔNG đi qua khuôn `Notification` khai báo
   (`setup/install_notifications.py`) — app tự biết khách hàng nào, tự tra
   tài khoản cổng của khách đó qua `Portal Member` (đảo chiều
   `portal_context.get_allowed_customers`; từ 18/08/2026 không còn đi qua
   `Contact.user` nữa — xem docstring `_portal_users_cua_khach`), rồi tạo
   thẳng `Notification Log`. Đường này do app kiểm soát hoàn toàn nên "điểm
   giòn" (contact_email khác tài khoản cổng) không áp dụng — ta resolve
   đúng người, không đoán qua một field email.

2. **Detect-and-log** (Phần 2, `hooks.py` doc_events): năm Notification
   "Portal - *" mới bật `send_system_notification` định tuyến người nhận qua
   `receiver_by_document_field: contact_email` — CƠ CHẾ CỦA FRAPPE, app không
   chen vào được. `Notification Log` chỉ sinh cho người nhận LÀ một User
   enabled (`frappe.desk.doctype.notification_log.notification_log.
   _get_user_ids` lọc theo email khớp `tabUser`) — nếu `contact_email` của
   chứng từ khác tài khoản cổng đã gắn với khách, thông báo hệ thống KHÔNG
   hiện trên trang Thông báo, và Frappe không báo gì cả (email qua kênh
   Email riêng vẫn gửi bình thường, chỉ System Notification bị rơi rụng
   trong im lặng). `kiem_tra_dinh_tuyen_thong_bao_khach` không sửa được
   đường định tuyến đó — chỉ PHÁT HIỆN và ghi một dòng Error Log (không lặp
   lại) để vận hành biết mà sửa contact_person/gắn lại tài khoản cổng.
"""

import frappe

TIEN_TO_DA_NHAP_HANG = "Portal - Đã nhập hàng"
TIEN_TO_KIEM_HANG = "Portal - Kiểm hàng"
TIEN_TO_HEN_GIAO = "Portal - Hẹn lịch giao"


def _portal_users_cua_khach(customer: str) -> list[str]:
    """Tài khoản cổng (User) gắn với khách hàng — chiều NGƯỢC của
    `portal_context.get_allowed_customers`.

    Từ 18/08/2026 đọc `Portal Member`, không đi qua `Contact` nữa. Giữ đường
    Contact ở đây trong khi `portal_context` đã chuyển sang `Portal Member`
    sẽ tạo đúng thứ mà việc chuyển đổi này tồn tại để dẹp: hai câu trả lời
    cho một câu hỏi. Cụ thể là hai kiểu sai đối xứng — user có Portal Member
    mà thiếu Contact thì KHÔNG nhận được thông báo nào; user còn Contact cũ
    mà đã tắt Portal Member thì NHẬN thông báo về dữ liệu mình không mở được
    (`TestChieuNguocDanhTinh` trong test_portal_member.py khoá lại cả hai
    chiều sai này).

    Chỉ trả User còn `enabled`: `_get_user_ids` của Frappe cũng lọc y hệt,
    báo cho một tài khoản đã khoá là báo cho không ai cả.

    Chưa lọc theo khoa phòng — hàm này vẫn trả TOÀN BỘ thành viên đang hoạt
    động của khách hàng (Quản lý lẫn Nhân viên khoa mọi khoa). Task 8 sẽ cần
    một biến thể chỉ gửi cho thành viên MỘT khoa phòng cụ thể; chỗ mở rộng
    tự nhiên là thêm tham số `khoa_phong` tuỳ chọn vào filters bên dưới,
    không sửa hàm này thành hai hàm song song.
    """
    users = frappe.get_all(
        "Portal Member", filters={"customer": customer, "active": 1}, pluck="user"
    )
    if not users:
        return []
    # `user` là field unique trên Portal Member (ràng buộc DB — xem
    # test_mot_user_chi_thuoc_mot_benh_vien) nên mỗi user tối đa MỘT bản ghi
    # ở đây, không như hàm cũ phải tự khử trùng lặp bằng set() vì một User
    # có thể có nhiều Contact. Vẫn bọc set() một cách tường minh — không im
    # lặng dựa vào ràng buộc đó, phòng khi nó đổi.
    return frappe.get_all(
        "User", filters={"name": ["in", set(users)], "enabled": 1}, pluck="name"
    )


def _log_khong_co_tai_khoan_cong(customer: str, phieu: str) -> None:
    """Khách có `Customer Warehouse` (tức là khách ĐÃ dùng tính năng kho
    cổng) nhưng KHÔNG có tài khoản cổng nào tra được — không phải lỗi
    (nhiều khách kho được mở tay chưa cấp tài khoản), nhưng vận hành cần
    biết để cấp tài khoản nếu khách cần thấy thông báo trên cổng. Ghi MỘT
    lần cho mỗi phiếu (không lặp lại mỗi lần hook chạy lại)."""
    tieu_de = f"Portal - Không tra được tài khoản cổng: {customer}"
    if frappe.db.exists(
        "Error Log", {"reference_doctype": "Customer Stock Receipt", "reference_name": phieu, "method": tieu_de}
    ):
        return
    try:
        frappe.log_error(
            title=tieu_de,
            message=(
                f"Phiếu nhập {phieu} vừa tạo cho khách hàng <b>{customer}</b>, nhưng "
                "khách này không có tài khoản cổng nào tra được qua Portal Member "
                "đang active — thông báo \"đã nhập hàng\" không gửi được cho ai. Nếu "
                "khách CẦN thấy thông báo trên cổng, cấp tài khoản (portal_provision) "
                "hoặc bật lại Portal Member đúng khách hàng."
            ),
            reference_doctype="Customer Stock Receipt",
            reference_name=phieu,
        )
    except Exception:
        # Đường gọi hàm này luôn nằm trong _chay_an_toan() của delivery_hook —
        # tự nuốt lỗi ở đây nữa để không phụ thuộc lớp bọc ngoài.
        pass


def bao_da_nhap_hang(customer: str, phieu: str, delivery_note: str) -> int:
    """§4.6/brief 2026-08-15 — Miyano giao hàng, `kho/delivery_hook.py` sinh
    phiếu nhập nháp; khách cần biết để vào đối chiếu. Trả số Notification Log
    vừa tạo.

    Chống trùng theo PHIẾU (không theo ngày) — cùng khuôn `bao_chenh_lech`
    trong `portal_thong_bao.py`: một Customer Stock Receipt draft chỉ được
    TẠO một lần trong đời một `name`, không có "lần tạo thứ hai" cho cùng
    tên đó để phải chặn theo cửa sổ thời gian.

    Không bao giờ ném lỗi: người gọi (`delivery_hook._chay_an_toan`, lệnh gọi
    RIÊNG với savepoint riêng — xem QĐ nền 4) đã tự bọc, nhưng hàm này tự
    chịu trách nhiệm không ném lỗi cho đúng thiết kế của cả cụm thông báo.
    """
    try:
        nguoi_nhan = _portal_users_cua_khach(customer)
        if not nguoi_nhan:
            _log_khong_co_tai_khoan_cong(customer, phieu)
            return 0

        chu_de = f"{TIEN_TO_DA_NHAP_HANG}: {phieu}"
        dem = 0
        for u in nguoi_nhan:
            if frappe.db.exists("Notification Log", {"subject": chu_de, "for_user": u}):
                continue
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": chu_de,
                "for_user": u,
                "type": "Alert",
                "document_type": "Customer Stock Receipt",
                "document_name": phieu,
                "email_content": (
                    f"Miyano vừa giao hàng theo phiếu giao {delivery_note}. Phiếu nhập "
                    f"kho <b>{phieu}</b> đã được tạo, đang chờ bạn đối chiếu hàng thực "
                    "nhận rồi ghi sổ."
                ),
            }).insert(ignore_permissions=True)
            dem += 1
        return dem
    except Exception:
        try:
            frappe.log_error(
                title="Kho khách: lỗi khi gửi thông báo đã nhập hàng",
                message=frappe.get_traceback(with_context=True),
                reference_doctype="Customer Stock Receipt",
                reference_name=phieu,
            )
        except Exception:
            pass
        return 0


def kiem_tra_dinh_tuyen_thong_bao_khach(doc, method=None) -> None:
    """doc_events hook (`hooks.py`, "on_update" của Sales Order/Delivery
    Note/Sales Invoice) — điểm giòn Phần 2/brief: PHÁT HIỆN khi
    `contact_email` của chứng từ không khớp tài khoản cổng nào của khách,
    nghĩa là các Notification "Portal - *" (Đơn xác nhận/Đơn bị từ chối/Xuất
    giao/Hoá đơn phát hành/Báo giá sẵn sàng) sẽ KHÔNG sinh Notification Log
    cho chứng từ này dù `send_system_notification = 1` — email qua Notification
    vẫn gửi bình thường (kênh Email độc lập), chỉ System Notification rơi
    rụng trong im lặng vì Frappe chỉ sinh log cho người nhận là User thật.

    CHỈ kiểm khi khách hàng CÓ tài khoản cổng (nếu không, contact_email
    không khớp ai là chuyện bình thường — khách chưa từng lên cổng, không
    phải một lỗ hổng của tính năng thông báo). Từ 18/08/2026, "CÓ tài khoản
    cổng" nghĩa là "CÓ ít nhất một Portal Member đang `active`" (qua
    `_portal_users_cua_khach`, giờ đọc Portal Member) — một khách mà tài
    khoản cổng duy nhất vừa bị tắt cũng rơi vào nhánh "chưa lên cổng" này và
    không còn bị bắt lỗi định tuyến nữa, ĐÚNG tinh thần "không ai để báo thì
    không phải lỗ hổng". Việc kiểm scope theo đúng tinh thần đó tránh log
    tràn ngập cho toàn bộ Delivery Note/Sales Invoice của khách KHÔNG dùng
    cổng (hai Notification "Xuất giao"/"Hoá đơn phát hành" không giới hạn
    `condition`, áp cho MỌI chứng từ trong hệ thống).

    Không bao giờ ném lỗi: chạy trên đường `on_update` của ba doctype bán
    hàng cốt lõi.
    """
    try:
        customer = doc.get("customer")
        contact_email = (doc.get("contact_email") or "").strip()
        if not customer or not contact_email:
            return
        nguoi_dung_cong = _portal_users_cua_khach(customer)
        if not nguoi_dung_cong:
            return
        if contact_email in nguoi_dung_cong:
            return

        tieu_de = f"Portal - Điểm giòn định tuyến thông báo: {doc.doctype} {doc.name}"
        if frappe.db.exists(
            "Error Log",
            {"reference_doctype": doc.doctype, "reference_name": doc.name, "method": tieu_de},
        ):
            return
        frappe.log_error(
            title=tieu_de,
            message=(
                f"Khách hàng <b>{customer}</b> có tài khoản cổng "
                f"({', '.join(nguoi_dung_cong)}) nhưng contact_email trên "
                f"{doc.doctype} <b>{doc.name}</b> là \"{contact_email}\", không khớp "
                "tài khoản nào trong số đó. Các Notification \"Portal - *\" đã bật "
                "send_system_notification sẽ KHÔNG hiện trên trang Thông báo cho chứng "
                "từ này (Frappe chỉ sinh Notification Log cho người nhận là User thật "
                "khớp contact_email) — email qua kênh Email của Notification vẫn gửi "
                "bình thường. Kiểm tra lại contact_person/contact_email của chứng từ, "
                "hoặc gắn lại tài khoản cổng khớp địa chỉ khách dùng khi đặt hàng."
            ),
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )
    except Exception:
        pass


def bao_kiem_hang_ket_qua(doc, tieu_de: str, noi_dung: str) -> int:
    """Miyano đã xử lý biên bản kiểm hàng → báo về cho khách.

    Chống trùng theo (BIÊN BẢN + TIÊU ĐỀ), không chỉ theo tên biên bản: một
    biên bản đi qua NHIỀU mốc khách cần biết ("đã duyệt trả" rồi "đã thu
    hồi"), chặn theo mình tên chứng từ sẽ nuốt mất mốc thứ hai.

    Không bao giờ ném lỗi — các endpoint gọi hàm này (`kiem_hang_duyet_tra`,
    `kiem_hang_tu_choi`) đã đổi trạng thái THẬT rồi; một trục trặc ở khâu
    thông báo không được phép làm hỏng thao tác đó.
    """
    try:
        nguoi_nhan = _portal_users_cua_khach(doc.customer)
        if not nguoi_nhan:
            _log_khong_co_tai_khoan_cong(doc.customer, doc.name)
            return 0

        chu_de = f"{TIEN_TO_KIEM_HANG}: {tieu_de} — {doc.name}"
        dem = 0
        for u in nguoi_nhan:
            if frappe.db.exists("Notification Log", {"subject": chu_de, "for_user": u}):
                continue
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": chu_de,
                "for_user": u,
                "type": "Alert",
                "document_type": "Portal Delivery Inspection",
                "document_name": doc.name,
                "email_content": noi_dung,
            }).insert(ignore_permissions=True)
            dem += 1
        return dem
    except Exception:
        try:
            frappe.log_error(
                title="Kiểm hàng: lỗi khi báo khách kết quả xử lý",
                message=frappe.get_traceback(with_context=True),
                reference_doctype="Portal Delivery Inspection",
                reference_name=doc.name,
            )
        except Exception:
            pass
        return 0


def bao_hen_giao_lai(so, loai: str, ngay_moi, ly_do: str) -> int:
    """Miyano hẹn lại lịch giao → báo khách.

    Chống trùng theo (ĐƠN + LOẠI + NGÀY), KHÔNG chỉ theo tên đơn: một đơn có
    thể bị hẹn lại nhiều lần (hàng vẫn chưa về), và mỗi lần hẹn là một tin
    khách CẦN biết. Chặn theo mình tên đơn sẽ nuốt mọi lần hẹn từ lần thứ hai
    — đúng loại im lặng tệ nhất ở đây, vì khách đang chờ chính con số đó.
    """
    try:
        nguoi_nhan = _portal_users_cua_khach(so.customer)
        if not nguoi_nhan:
            _log_khong_co_tai_khoan_cong(so.customer, so.name)
            return 0

        ngay_vi = frappe.utils.formatdate(ngay_moi)
        chu_de = f"{TIEN_TO_HEN_GIAO}: {so.name} — {loai} {ngay_vi}"
        noi_dung = (
            f"Miyano thông báo về đơn hàng <b>{so.name}</b>: <b>{loai.lower()}</b>, "
            f"dự kiến giao ngày <b>{ngay_vi}</b>.<br>"
            f"Lý do: {frappe.utils.escape_html(ly_do)}"
        )
        dem = 0
        for u in nguoi_nhan:
            if frappe.db.exists("Notification Log", {"subject": chu_de, "for_user": u}):
                continue
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": chu_de,
                "for_user": u,
                "type": "Alert",
                "document_type": "Sales Order",
                "document_name": so.name,
                "email_content": noi_dung,
            }).insert(ignore_permissions=True)
            dem += 1
        return dem
    except Exception:
        try:
            frappe.log_error(
                title="Hẹn giao: lỗi khi gửi thông báo cho khách",
                message=frappe.get_traceback(with_context=True),
                reference_doctype="Sales Order",
                reference_name=so.name,
            )
        except Exception:
            pass
        return 0
