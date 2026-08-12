import frappe


def get_allowed_customers(user: str | None = None) -> list[str]:
    """Customers linked to the user's Contact (Dynamic Link -> Customer)."""
    user = user or frappe.session.user
    contacts = frappe.get_all(
        "Contact",
        filters={"user": user},
        pluck="name",
    )
    if not contacts:
        return []
    customers = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Contact",
            "parent": ["in", contacts],
            "link_doctype": "Customer",
        },
        pluck="link_name",
    )
    return list(dict.fromkeys(customers))


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
