import frappe

QUAN_LY = "Quản lý"


def get_portal_member(user: str | None = None) -> frappe._dict:
    """Bản ghi thành viên cổng của user. Ném PermissionError nếu không có.

    Đây là NGUỒN DUY NHẤT — không có nhánh dự phòng đọc `Contact`. Một
    `Contact` có `user` mà không có `Portal Member` là LỖI CẤU HÌNH (patch
    v1_23 điền cho tài khoản cũ, `portal_provision` tạo cho tài khoản mới),
    không phải một trường hợp hợp lệ cần đỡ. Đỡ nó chính là dựng lại hai
    nguồn sự thật mà việc chuyển đổi này tồn tại để dẹp.
    """
    user = user or frappe.session.user
    tv = frappe.db.get_value(
        "Portal Member", {"user": user, "active": 1},
        ["name", "customer", "vai_tro", "khoa_phong"], as_dict=True,
    )
    if not tv:
        raise frappe.PermissionError("Tài khoản chưa gắn với khách hàng nào.")
    return tv


def get_allowed_customers(user: str | None = None) -> list[str]:
    """Khách hàng của user, đọc từ `Portal Member`.

    Giữ NGUYÊN chữ ký trả `list[str]` (dù mỗi user đúng một khách hàng — một
    user không thể thuộc hai `Portal Member` nhờ ràng buộc unique trên field
    `user`) để mọi lời gọi hiện có (permissions.py, kho/permissions.py, các
    hook has_permission/query_condition...) không phải đổi theo.
    """
    user = user or frappe.session.user
    cust = frappe.db.get_value(
        "Portal Member", {"user": user, "active": 1}, "customer"
    )
    return [cust] if cust else []


def la_quan_ly(user: str | None = None) -> bool:
    """Có quyền quản lý (nhìn xuyên mọi khoa phòng) TẠI THỜI ĐIỂM NÀY.

    Hàm này PHỤ THUỘC THỜI GIAN. Bước 7 của đề án thêm uỷ quyền tạm thời và
    vế thứ hai sẽ mọc ra ở đây — mọi nơi gọi PHẢI hỏi hàm này, KHÔNG được tự
    đọc `vai_tro` (kể cả qua `get_portal_member().vai_tro`): người được uỷ
    quyền vẫn mang vai trò "Nhân viên khoa" trong hồ sơ nhưng phải nhìn
    xuyên mọi khoa trong thời gian uỷ quyền — tự đọc `vai_tro` sẽ bỏ sót vế
    đó ngay khi nó được thêm vào.
    """
    try:
        return get_portal_member(user).vai_tro == QUAN_LY
    except frappe.PermissionError:
        return False


def pham_vi_don(user: str | None = None) -> dict:
    """Điều kiện lọc đơn hàng theo khoa phòng cho user hiện tại.

    `{}` = không giới hạn theo khoa (Quản lý, hoặc — sau bước 7 — người đang
    được uỷ quyền). Vẫn phải kết hợp với giới hạn theo khách hàng
    (`get_allowed_customers`/`get_portal_customer`) ở chỗ gọi — hàm này CHỈ
    trả lời câu hỏi "trong nội bộ một khách hàng, còn giới hạn thêm theo
    khoa phòng nào không", không tự nó giới hạn khách hàng.

    VÒNG SỬA 3 (F5, review độc lập, Important): FAIL-CLOSED khi một `Nhân
    viên khoa` `active=1` mà `khoa_phong` rỗng — ném `PermissionError` thay
    vì trả `{"custom_khoa_phong": None}`. Bản trước trả một BỘ LỌC nhìn như
    hợp lệ nhưng vô nghĩa: tuỳ cách chỗ gọi ghép điều kiện, `None` hoặc lọt
    TOÀN BỘ đơn CHƯA gắn khoa của khách hàng đó (tức toàn bộ lịch sử đơn có
    TRƯỚC khi đề án này tồn tại — âm thầm mở toang) hoặc khớp không ai (một
    dạng "chết lặng lẽ" khác). `khoa_phong` rỗng ở `active=1` không nên xảy
    ra qua `PortalMember.validate()` (được `_chan_vai_tro_va_khoa_phong`
    canh) — nhưng validate() có GIỚI HẠN ĐÃ BIẾT bị đi vòng qua
    `frappe.db.set_value()`/`doc.db_set()` (xem `_chan_hai_quan_ly` trong
    `portal_member.py`), nên chỗ ĐỌC này phải tự vệ, không được tin việc
    ghi luôn đúng."""
    if la_quan_ly(user):
        return {}
    khoa_phong = get_portal_member(user).khoa_phong
    if not khoa_phong:
        raise frappe.PermissionError("Tài khoản chưa được gán khoa phòng.")
    return {"custom_khoa_phong": khoa_phong}


def get_portal_customer(user: str | None = None) -> str:
    customers = get_allowed_customers(user)
    if not customers:
        raise frappe.PermissionError("Tài khoản chưa gắn với khách hàng nào.")
    return customers[0]


def get_portal_kho(user: str | None = None) -> str:
    """Tên Customer Warehouse của khách đang đăng nhập.

    Mỗi khách đúng một kho, nên hàm này trả về một chuỗi chứ không phải danh
    sách. Mọi endpoint kho đều phải đi qua đây thay vì nhận tên kho từ client.
    """
    customers = get_allowed_customers(user)
    if not customers:
        raise frappe.PermissionError("Tài khoản chưa gắn với khách hàng nào.")
    kho = frappe.db.get_value(
        "Customer Warehouse",
        {"customer": ["in", customers], "active": 1},
        "name",
    )
    if not kho:
        raise frappe.PermissionError(
            "Đơn vị của bạn chưa được mở kho trên cổng. Vui lòng liên hệ "
            "nhân viên kinh doanh Miyano."
        )
    return kho


def get_allowed_khos(user: str | None = None) -> list[str]:
    """Mọi kho mà user được phép thấy. Dùng cho các hook phân quyền.

    Lọc `active: 1` GIỐNG HỆT get_portal_kho(). Bản trước không lọc, nên một
    kho đã tắt vẫn nằm trong danh sách của tầng phân quyền trong khi API từ
    chối nó — hai câu trả lời khác nhau cho cùng một câu hỏi "kho này còn mở
    không", đúng kiểu bất đối xứng sinh ra lỗ sau này.

    Chiều thu hẹp là chiều đúng, và nó KHÔNG làm dữ liệu lộ sang khách khác:
    mọi chỗ dùng hàm này (`_kho_condition`, `_child_condition`,
    `kho_child_has_permission`, `voucher_item_readable`) đều coi kết quả như
    một DANH SÁCH CHO PHÉP — bớt một kho chỉ có thể siết chặt thêm, không thể
    nới ra, và danh sách rỗng render thành "1=0". Lịch sử của một kho đã tắt
    vì thế không thuộc về ai ở tầng phân quyền của Website User; nhân viên
    Miyano ngồi desk vẫn thấy đủ vì `_is_restricted_user` cho họ đi thẳng
    trước khi hàm này được gọi.
    """
    customers = get_allowed_customers(user)
    if not customers:
        return []
    return frappe.get_all(
        "Customer Warehouse",
        filters={"customer": ["in", customers], "active": 1},
        pluck="name",
    )


def han_muc_con(blanket_order: str, item_code: str) -> tuple[float | None, float]:
    """Hạn mức còn lại của một mặt hàng trong HĐNT, và số đã đặt luỹ kế.

    Trả `(None, da_dat)` khi dòng hợp đồng khai `qty = 0`: theo QĐ-8 / BR-O15
    đó là quy ước **KHÔNG GIỚI HẠN**, không phải "hết hạn mức".

    Phân biệt được ba trạng thái là toàn bộ lý do hàm này trả tuple thay vì
    một con số:

    - `(None, n)` — không giới hạn, đã đặt n
    - `(0.0, n)`  — hết hạn mức, hoặc mặt hàng không có trong hợp đồng
    - `(x, n)`    — còn x

    Bản cũ (`remaining_qty`) trả `qty - ordered_qty` nên gộp hai trạng thái
    đầu vào cùng một con số ≤ 0. Với dòng khai 0 đã đặt 30 nó ra **-30**, và
    `portal_order_place` so `qty > rem` khiến mọi số lượng đều bị chặn kèm
    thông báo "vượt hạn mức (còn -30)" — mặt hàng khai hạn mức 0 không đặt
    được, đúng ngược quy ước.
    """
    row = frappe.get_all(
        "Blanket Order Item",
        filters={"parent": blanket_order, "item_code": item_code},
        fields=["qty", "ordered_qty"],
        limit=1,
    )
    if not row:
        # Không có trong hợp đồng = không đặt được. CỐ Ý khác `None`: gộp hai
        # thứ này là cách mở toang hạn mức cho mọi mặt hàng lạ.
        return 0.0, 0.0
    tong = float(row[0].qty or 0)
    da_dat = float(row[0].ordered_qty or 0)
    if tong == 0:
        return None, da_dat
    return tong - da_dat, da_dat


def remaining_qty(blanket_order: str, item_code: str) -> float:
    """Chữ ký cũ, giữ cho mã và test đã có.

    KHÔNG phân biệt được "không giới hạn" — nó trả `inf`, đủ để mọi phép so
    `qty > rem` đi qua, nhưng chỗ nào cần biết ĐÓ LÀ không giới hạn (để bỏ
    `against_blanket_order`, để loại khỏi mẫu số phần trăm) thì phải gọi
    thẳng `han_muc_con`.
    """
    con_lai, _ = han_muc_con(blanket_order, item_code)
    return float("inf") if con_lai is None else con_lai
