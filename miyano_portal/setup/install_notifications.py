import frappe

TEN_TB_BAO_GIA = "Portal - Yêu cầu báo giá sẵn sàng"
TEN_TB_BAO_GIA_TU_CHOI = "Portal - Yêu cầu báo giá bị từ chối"

DEFS = [
    {
        # Brief 2026-08-15 (trang thông báo) Phần 1 — CỐ Ý KHÔNG bật
        # `send_system_notification` ở đây: sự kiện "New" xảy ra ĐÚNG lúc
        # khách vừa tự bấm đặt hàng trên cổng — không phải tin gì MỚI với họ
        # (họ vừa làm ra chính sự kiện đó), khác "Đơn xác nhận"/"Đơn bị từ
        # chối"/"Xuất giao"/"Hoá đơn phát hành"/"Báo giá sẵn sàng" bên dưới,
        # đều là việc Miyano LÀM và khách cần được báo. Ba Notification
        # "Portal Item Request" phía dưới cũng giữ nguyên 0 vì lý do khác —
        # xem chú thích tại chỗ.
        "name": "Portal - Đơn mới",
        "subject": "Đơn hàng {{ doc.name }} đã được ghi nhận",
        "document_type": "Sales Order",
        "event": "New",
        "condition": "doc.custom_nguon_don == 'Client Portal'",
        "message": "Kính gửi Quý khách,\n\nĐơn hàng {{ doc.name }} đã được ghi nhận và đang chờ Miyano xác nhận.",
    },
    {
        "name": "Portal - Đơn xác nhận",
        "subject": "Đơn hàng {{ doc.name }} đã được xác nhận",
        "document_type": "Sales Order",
        "event": "Submit",
        "condition": "doc.custom_nguon_don == 'Client Portal'",
        # Thời gian giao hàng (09/10/2026) — nêu ngày giao dự kiến TỪNG mặt
        # hàng, đúng con số cổng hiện ở cột "Dự kiến giao" (`Sales Order
        # Item.delivery_date`). Mỗi mặt hàng một gạch đầu dòng, không dùng
        # bảng: thư này là Markdown và phải đọc được cả ở dạng chữ thuần.
        # `la_dong_giu_cho` — dòng giữ chỗ nội bộ đã bị lọc khỏi cổng, thư
        # không được phơi nó ra bằng đường khác.
        "message": (
            "Kính gửi Quý khách,\n\nĐơn hàng {{ doc.name }} đã được Miyano xác nhận "
            "và chuyển sang xử lý.\n\nThời gian giao hàng dự kiến:\n"
            "{% for row in doc.items %}{% if not la_dong_giu_cho(row.item_code) %}"
            # Mã → Tên, cùng thứ tự với cổng, Desk và mẫu in (`ten_hang.py`).
            "\n- {{ row.item_code }} — {{ row.item_name or row.item_code }}: "
            "{{ frappe.utils.formatdate(row.delivery_date or doc.delivery_date, 'dd/MM/yyyy') }}"
            "{% endif %}{% endfor %}"
            "\n\nNếu lịch giao thay đổi, Miyano sẽ thông báo lại trên cổng khách hàng."
        ),
        # Brief 2026-08-15 (trang thông báo) — sự kiện HƯỚNG VỀ KHÁCH: bật kèm
        # System Notification (Notification Log) để hiện trên trang Thông báo
        # cổng, cùng khuôn "Portal - Báo giá sẵn sàng" đã bật từ v1_14. Bản ghi
        # ĐÃ CÀI trên site cần patch riêng cập nhật (`install_portal_notifications()`
        # bỏ qua bản ghi đã tồn tại) — xem `patches/v1_19`.
        "send_system_notification": 1,
    },
    {
        "name": "Portal - Đơn bị từ chối",
        "subject": "Đơn hàng {{ doc.name }} đã bị từ chối",
        "document_type": "Sales Order",
        "event": "Value Change",
        "value_changed": "workflow_state",
        "condition": "doc.custom_nguon_don == 'Client Portal' and doc.workflow_state == 'Từ chối'",
        "message": "Kính gửi Quý khách,\n\nĐơn hàng {{ doc.name }} đã bị Miyano từ chối. Vui lòng liên hệ để biết thêm chi tiết.",
        "send_system_notification": 1,
    },
    {
        "name": "Portal - Xuất giao",
        "subject": "Hàng đã xuất giao cho phiếu {{ doc.name }}",
        "document_type": "Delivery Note",
        "event": "Submit",
        "condition": "",
        # Thời gian giao hàng (09/10/2026) — `custom_thoi_gian_giao` do Miyano
        # nhập trên phiếu (hook `validate` đã điền khi để trống, nên tới lúc
        # ghi sổ nó luôn có); `{% if %}` chỉ để một phiếu bất thường không
        # in ra dòng "Thời gian giao hàng:" trống.
        "message": (
            "Kính gửi Quý khách,\n\nĐơn hàng của Quý khách đã được xuất giao theo "
            "phiếu giao hàng {{ doc.name }}."
            "{% if doc.custom_thoi_gian_giao %}\n\nThời gian giao hàng: "
            "{{ frappe.utils.format_datetime(doc.custom_thoi_gian_giao, 'dd/MM/yyyy HH:mm') }}."
            "{% endif %}"
        ),
        "send_system_notification": 1,
    },
    {
        "name": "Portal - Hoá đơn phát hành",
        "subject": "Hoá đơn {{ doc.name }} đã được phát hành",
        "document_type": "Sales Invoice",
        "event": "Submit",
        "condition": "",
        "message": "Kính gửi Quý khách,\n\nHoá đơn {{ doc.name }} đã được phát hành. Quý khách có thể xem chi tiết trên cổng khách hàng.",
        "send_system_notification": 1,
    },
    # E6/US-E6.3 — email xác nhận yêu cầu hàng hoá. `Portal Item Request`
    # không có field `contact_email` (không phải doctype ERPNext bán hàng);
    # người nhận là chính field `nguoi_yeu_cau` (email khách gõ lúc gửi yêu
    # cầu) — xem `recipient_field` bên dưới và `install_portal_notifications()`.
    #
    # Brief 2026-08-15 Phần 1 — ba Notification "Portal Item Request" dưới
    # đây CỐ Ý giữ `send_system_notification` mặc định 0, dù hai cái sau là
    # tin Miyano chủ động báo cho khách (đáng lẽ thuộc diện bật): `nguoi_yeu_
    # cau` là một Ô TEXT khách tự gõ khi gửi yêu cầu, KHÔNG đảm bảo trùng
    # tài khoản cổng đang đăng nhập — bật system notification ở đây là nhân
    # rộng đúng điểm giòn mà brief yêu cầu xử lý (contact_email không khớp
    # User), chỉ đổi tên field. Ngoài phạm vi việc thêm nhỏ này.
    {
        "name": "Portal - Yêu cầu hàng hoá đã ghi nhận",
        "subject": "Yêu cầu hàng hoá {{ doc.name }} đã được ghi nhận",
        "document_type": "Portal Item Request",
        "event": "New",
        "condition": "",
        "message": (
            "Kính gửi Quý khách,\n\nYêu cầu hàng hoá {{ doc.name }} "
            "({{ doc.ten_hang }}) đã được ghi nhận. Miyano sẽ phản hồi trong "
            "thời gian SLA quy định."
        ),
        "recipient_field": "nguoi_yeu_cau",
    },
    # BR-Y2 — email PHẢI mang đúng lý do, không phải câu chung chung. Cùng
    # khuôn "Portal - Đơn bị từ chối" ở trên (US-E2.2): message nhúng thẳng
    # field lý do bằng Jinja, không diễn giải lại.
    {
        "name": "Portal - Yêu cầu không đáp ứng được",
        "subject": "Yêu cầu hàng hoá {{ doc.name }} không đáp ứng được",
        "document_type": "Portal Item Request",
        "event": "Value Change",
        "value_changed": "trang_thai",
        "condition": "doc.trang_thai == 'Không đáp ứng được'",
        "message": (
            "Kính gửi Quý khách,\n\nMiyano rất tiếc chưa thể đáp ứng yêu cầu "
            "{{ doc.name }} ({{ doc.ten_hang }}).\n\nLý do: "
            "{{ doc.ly_do_khong_dap_ung }}"
        ),
        "recipient_field": "nguoi_yeu_cau",
    },
    # NL-11.3 — khách nhận email khi Miyano cần thêm thông tin. Việc TRẢ LỜI
    # (comment 2 chiều, tự chuyển "Đang tìm nguồn") nằm ở
    # api/portal.py::portal_yeu_cau_tra_loi; trigger email này độc lập với
    # đường trả lời đó.
    {
        "name": "Portal - Yêu cầu cần thêm thông tin",
        "subject": "Yêu cầu hàng hoá {{ doc.name }} cần bổ sung thông tin",
        "document_type": "Portal Item Request",
        "event": "Value Change",
        "value_changed": "trang_thai",
        "condition": "doc.trang_thai == 'Cần thêm thông tin'",
        "message": (
            "Kính gửi Quý khách,\n\nMiyano cần thêm thông tin để xử lý yêu "
            "cầu {{ doc.name }} ({{ doc.ten_hang }}). Vui lòng liên hệ nhân "
            "viên phụ trách hoặc trả lời email này để cung cấp thêm thông "
            "tin.\n\n{{ doc.phan_hoi or '' }}"
        ),
        "recipient_field": "nguoi_yeu_cau",
    },
    # "Portal - Báo giá sẵn sàng" của Sales Order đã bỏ (patch v1_44): đơn
    # không còn vòng báo giá, khách đồng ý giá trên Quotation.
    {
        # Spec 2026-10-12 §7 — thông báo báo giá sẵn sàng, trên Quotation.
        # `attach_print`/`print_format` do patch v1_42 đặt SAU khi mẫu in đã
        # có: `print_format` là Link, được kiểm ngay lúc insert.
        "name": TEN_TB_BAO_GIA,
        "subject": "Báo giá {{ doc.name }} đã sẵn sàng",
        "document_type": "Quotation",
        "event": "Value Change",
        "value_changed": "workflow_state",
        "condition": (
            "doc.custom_nguon_don == 'Client Portal' and "
            "doc.workflow_state == 'Chờ khách đồng ý'"
        ),
        "message": (
            "Kính gửi Quý khách,\n\nMiyano đã gửi báo giá {{ doc.name }}, tổng giá "
            "trị {{ frappe.utils.fmt_money(doc.grand_total, currency='VND') }}.\n\n"
            "{% if doc.valid_till %}Báo giá có hiệu lực đến hết ngày "
            "{{ frappe.utils.formatdate(doc.valid_till, 'dd/mm/yyyy') }}. Sau thời "
            "hạn này, nếu Quý khách chưa phản hồi, báo giá sẽ tự động đóng.\n\n"
            "{% endif %}Vui lòng đăng nhập cổng khách hàng, mở tab \"Yêu cầu báo "
            "giá\" để xem chi tiết và xác nhận."
        ),
        "send_system_notification": 1,
    },
    {
        # Miyano từ chối một yêu cầu báo giá của cổng: bệnh viện phải được báo,
        # kèm đúng lý do nhân viên đã nhập (`bao_gia.kiem_ly_do_tu_choi` bắt
        # buộc có). Cùng khuôn "Portal - Đơn bị từ chối"; cùng người nhận với
        # thông báo "sẵn sàng" ở trên. Không đính kèm bản in: không có báo giá
        # nào để in. Khách tự từ chối ("Khách từ chối") không đi qua đây.
        "name": TEN_TB_BAO_GIA_TU_CHOI,
        "subject": "Yêu cầu báo giá {{ doc.name }} đã bị từ chối",
        "document_type": "Quotation",
        "event": "Value Change",
        "value_changed": "workflow_state",
        "condition": (
            "doc.custom_nguon_don == 'Client Portal' and "
            "doc.workflow_state == 'Miyano từ chối'"
        ),
        "message": (
            "Kính gửi Quý khách,\n\nMiyano rất tiếc chưa thể báo giá cho yêu cầu "
            "{{ doc.name }}.\n\nLý do: {{ doc.custom_ly_do_tu_choi }}\n\nQuý khách "
            "có thể xem chi tiết ở tab \"Yêu cầu báo giá\" trên cổng khách hàng."
        ),
        "send_system_notification": 1,
    },
]


def install_portal_notifications():
    for d in DEFS:
        if frappe.db.exists("Notification", d["name"]):
            continue
        doc = frappe.get_doc({
            "doctype": "Notification",
            "name": d["name"],
            "subject": d["subject"],
            "document_type": d["document_type"],
            "event": d["event"],
            "value_changed": d.get("value_changed"),
            "condition": d["condition"],
            "channel": "Email",
            "recipients": [
                {"receiver_by_document_field": d.get("recipient_field", "contact_email")}
            ],
            "message": d["message"],
            "enabled": 1,
            # §4.6 — "thông báo trên chính đơn đặt hàng" = system notification
            # (Notification Log) TRÊN CÙNG cơ chế Email, không phải hai luồng
            # gửi riêng. Mặc định 0 cho mọi định nghĩa cũ — hành vi các
            # Notification hiện có KHÔNG đổi.
            "send_system_notification": d.get("send_system_notification", 0),
            "attach_print": d.get("attach_print", 0),
            "print_format": d.get("print_format"),
        })
        doc.insert(ignore_permissions=True)
