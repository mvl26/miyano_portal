import frappe

QUAN_LY = "Quản lý"

THONG_DIEP_CHUA_GAN_KHACH = "Tài khoản chưa gắn với khách hàng nào."


def _thong_diep_chua_thay_khach(user: str) -> str:
    """V4 (fix-wave 2026-08-18, review tổng toàn nhánh — hệ quả R7 chưa ai
    nêu). Phân biệt HAI nguyên nhân khác nhau của cùng một câu hỏi "tài
    khoản không thấy được khách hàng nào":

    - KHÔNG có bản ghi `Portal Member` nào cho user này — lỗi cấu hình
      thật (`THONG_DIEP_CHUA_GAN_KHACH`, giữ NGUYÊN câu cũ).
    - CÓ bản ghi nhưng `active=0` — tài khoản ĐÃ được gắn khách hàng, chỉ
      CHƯA được quản lý bật. Đúng luồng cấp tài khoản R7 (task-5-report):
      `portal_provision` tạo tài khoản thứ hai trở đi của một bệnh viện ở
      dạng `Nhân viên khoa`/`active=0`, CHỜ quản lý gán khoa rồi bật — đây
      là màn hình ĐẦU TIÊN của mọi nhân viên khoa mới. Thông điệp cũ (dùng
      chung cho cả hai ca) nói SAI nguyên nhân, khiến họ gọi nhầm người
      (Miyano) thay vì đúng người sửa được (quản lý đơn vị mình).

    Không lộ thêm gì ngoài phân biệt đó: không nói active=0 là do THIẾU
    KHOA hay do QUẢN LÝ CHƯA BẤM NÚT kích hoạt — cả hai đều dẫn tới cùng
    một hành động ("liên hệ quản lý của đơn vị bạn"), và bản thân sự tồn
    tại của bản ghi `Portal Member` (không phải nội dung nó mang) là đủ để
    phân biệt, không cần đọc thêm `vai_tro`/`khoa_phong`/`customer`."""
    if frappe.db.exists("Portal Member", {"user": user}):
        return (
            "Tài khoản chưa được kích hoạt. Liên hệ quản lý của đơn vị bạn "
            "để được gán khoa phòng và kích hoạt tài khoản."
        )
    return THONG_DIEP_CHUA_GAN_KHACH


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
        raise frappe.PermissionError(_thong_diep_chua_thay_khach(user))
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


def khoa_phong_cho_don(khoa_phong_client: str | None = None, user: str | None = None) -> str | None:
    """Khoa phòng được phép đóng dấu lên đơn/phiếu của phiên hiện tại (bước 7,
    §5.5).

    Đây là phép kiểm khoa ↔ NGƯỜI GỌI — thứ mà `dat_hang.tao_sales_order`
    (kiểm khoa ↔ KHÁCH HÀNG, qua tham số `customer` khi tra `Blanket
    Order`/`Customer Department`) và `portal_order_place` bản trước Task 7
    (suy khoa THẲNG từ `Portal Member.khoa_phong` của phiên, không kiểm gì
    thêm) đều KHÔNG làm: không đâu trong hai chỗ đó hỏi "người đang gọi có
    được phép đóng dấu ĐÚNG khoa này không".

    - Nhân viên khoa: BỎ QUA HOÀN TOÀN `khoa_phong_client` — luôn trả khoa
      của chính họ (`Portal Member.khoa_phong`). Nhận giá trị từ client ở
      đây sẽ cho nhân viên khoa A tự đóng dấu đơn thành khoa B, đúng lỗ mà
      C1 (bình luận cũ ở `portal_order_place`) từng chặn — chặn tiếp tục ở
      ĐÂY, chỉ đổi chỗ đứng.
    - Quản lý: được CHỌN, vì họ nhìn xuyên mọi khoa (`la_quan_ly()`). Nhưng
      khoa chọn vẫn phải THUỘC bệnh viện của họ (`Customer Department.
      customer == Portal Member.customer`) và đang `active` — một khoa đã
      giải thể/sáp nhập hoặc của bệnh viện khác không được phép nhận đơn
      mới, cùng lý do `pham_vi_don()`/`dat_hang.tao_sales_order` đã kiểm
      `active` ở các đường khác. `khoa_phong_client` rỗng/`None` = "Toàn
      viện" (§5.5), hợp lệ — không phải lỗi.
    """
    tv = get_portal_member(user)
    if tv.vai_tro != QUAN_LY:
        return tv.khoa_phong
    if not khoa_phong_client:
        return None
    kp = frappe.db.get_value(
        "Customer Department", khoa_phong_client, ["customer", "active"], as_dict=True
    )
    if not kp or kp.customer != tv.customer or not kp.active:
        raise frappe.PermissionError(
            f'Khoa phòng "{khoa_phong_client}" không thuộc đơn vị của bạn '
            "hoặc đã ngừng hoạt động."
        )
    return khoa_phong_client


# VÒNG SỬA 2 (C3 — CRITICAL), CHUYỂN VÀO ĐÂY Ở VÒNG SỬA 3 (V2, Important).
# Cache CẤP TIẾN TRÌNH — không phải `None` nghĩa là "chưa biết", `True`/
# `False` là kết quả đã kiểm. Nhớ Ở ĐÂY (không hỏi lại `information_schema`/
# Redis mỗi lần) vì hàm dùng biến này chạy trên MỌI truy vấn Sales Order/
# Delivery Note/Sales Invoice của MỌI Website User — không phải một lần
# mỗi request.
#
# Đặt ở `portal_context.py` (không phải `permissions.py`, nơi hàm này SINH
# RA ở Vòng sửa 2) để CẢ HAI bên dùng chung được MỘT nguồn kiểm tra: hook
# framework (`permissions.py`, import module này) LẪN các endpoint whitelist
# (`api/portal.py`/`dam_bao_xem_duoc` ngay dưới đây, cùng module này) —
# `permissions.py` không import được ngược lại từ `api/portal.py` (vòng
# import), nên vị trí TRUNG LẬP này là chỗ duy nhất cả hai phía cùng chạm
# tới mà không tạo vòng.
_cot_khoa_ton_tai: bool | None = None


def _cot_khoa_phong_ton_tai() -> bool:
    """Có cột `Sales Order.custom_khoa_phong` THẬT trong CSDL không.

    Vòng sửa 1 (C2) đưa `custom_khoa_phong` vào `permission_query_
    conditions`/`has_permission` (`permissions.py`) — tức MỌI đường đọc
    Sales Order/Delivery Note/Sales Invoice của MỌI khách cổng. Nếu patch
    `v1_23/them_khoa_phong_vao_don_hang` CHƯA THỰC SỰ chạy trên site đích,
    SQL sinh ra tham chiếu một cột không tồn tại → MariaDB ném lỗi 1054
    (unknown column) → CỔNG KHÁCH SẬP HOÀN TOÀN, không phải suy giảm êm.

    Đây KHÔNG phải rủi ro lý thuyết: `install_app` trên dự án này từng ghi
    nhận "hoàn thành giả" patch — ghi Patch Log mà không thực sự chạy DDL
    (xem memory `miyano-portal-install-patch-trap`). Một dòng trong
    `patches.txt` không phải bằng chứng cột đã tồn tại.

    VÒNG SỬA 3 (V2, review độc lập, Important) — bản Vòng sửa 2 chỉ gọi hàm
    này từ `permissions.py` (tầng hook: `frappe.client.*`, reportview,
    `/printview`, REST). Nhưng phần lớn traffic cổng THẬT đi qua 21 hàm
    whitelist ở `api/portal.py`, và khoảng 13 trong số đó gọi THẲNG
    `dam_bao_xem_duoc()`/`_ten_don_trong_pham_vi()` — hai hàm đó đọc
    `custom_khoa_phong` qua `frappe.db.get_value`/`frappe.get_all` mà KHÔNG
    hề qua tầng hook. Thiếu cột thì đường đó vẫn ăn lỗi CSDL thô, đúng chỗ
    docstring bản Vòng sửa 2 (sai) khẳng định đã được che. `dam_bao_xem_
    duoc()` giờ gọi hàm NÀY trước khi chạm cột — lưới an toàn giờ phủ CẢ
    HAI tầng bằng CÙNG một nguồn kiểm tra, không phải hai bản sao lệch nhau.

    SỬA (fix-wave 2026-08-18, V2 — Important): "phủ CẢ HAI tầng" ở trên
    liệt kê THIẾU — `api/portal.py::_pham_vi_filters()` (nuôi `portal_
    order_history`/`portal_dashboard_kpi`, hai endpoint traffic cao nhất)
    cũng tham chiếu THẲNG `custom_khoa_phong` mà KHÔNG qua hàm này, cùng
    một lỗ với `dam_bao_xem_duoc()`/`_ten_don_trong_pham_vi()` trước Vòng
    sửa 3. Đã thêm lưới vào `_pham_vi_filters()` — giờ MỌI nơi ở tầng
    endpoint tham chiếu `custom_khoa_phong` (ba hàm) đều gọi hàm NÀY
    trước, cùng một nguồn kiểm tra với tầng hook.

    Hàm này là LƯỚI AN TOÀN CHO LÚC TRIỂN KHAI, KHÔNG PHẢI giấy phép để
    deploy mà không chạy `bench migrate`: thiếu cột thì MỌI Website User bị
    fail-closed (không thấy gì, an toàn) thay vì gặp lỗi CSDL thô, nhưng
    cổng vẫn "câm" với đúng người lẽ ra phải thấy dữ liệu của mình — vá
    triệu chứng, không thay được `bench migrate`."""
    global _cot_khoa_ton_tai
    if _cot_khoa_ton_tai is None:
        _cot_khoa_ton_tai = bool(frappe.db.has_column("Sales Order", "custom_khoa_phong"))
        if not _cot_khoa_ton_tai:
            frappe.log_error(
                title="Thiếu cột Sales Order.custom_khoa_phong",
                message=(
                    "Phân quyền theo khoa phòng (miyano_portal.portal_context/"
                    "permissions/api.portal) đang chạy trên một site CHƯA có "
                    "cột Sales Order.custom_khoa_phong. Mọi Website User đang "
                    "bị chặn fail-closed trên Sales Order/Delivery Note/Sales "
                    "Invoice thay vì gặp lỗi CSDL — cổng \"câm\" thay vì sập, "
                    "nhưng khách không thấy được đơn của chính họ. Chạy `bench "
                    "--site <site> migrate` để thêm cột (patch miyano_portal."
                    "patches.v1_23.them_khoa_phong_vao_don_hang)."
                ),
            )
    return _cot_khoa_ton_tai


LOI_KHONG_THAY = "Không tìm thấy chứng từ."


def dam_bao_xem_duoc(
    doctype: str, name: str, user: str | None = None, pham_vi: dict | None = None
) -> None:
    """Chặn ở mọi endpoint ĐỌC MỘT chứng từ theo phạm vi khoa phòng (bước 8).

    `user` — VÒNG SỬA 1 (C2, review độc lập): các hook `has_permission` ở
    `permissions.py` nhận một `user` TƯỜNG MINH từ framework (có thể khác
    `frappe.session.user`, xem `_has_customer_permission` đã làm y hệt cho
    lớp khách hàng) — hàm này giờ xuyên đúng `user` đó xuống `pham_vi_don()`
    thay vì luôn đọc phiên hiện tại, để MỘT nguồn logic phục vụ được CẢ tầng
    endpoint (`api/portal.py`, luôn gọi mặc định `user=None` = phiên hiện
    tại) LẪN tầng hook permission.

    `pham_vi` — truyền sẵn nếu người gọi đã tự tính `pham_vi_don()` MỘT LẦN
    cho cả một danh sách (tránh hỏi lại CSDL mỗi dòng); mặc định `None` =
    tự tính từ `user`/phiên hiện tại như trước.

    Thông báo lỗi CỐ Ý giống hệt cho hai trường hợp "không có thật" và "của
    khoa khác": phân biệt hai cái đó là để lộ sự tồn tại của chứng từ, và
    trong bệnh viện thì "khoa Dược có đơn mã X" đã là thông tin. Việc này chỉ
    làm được vì `frappe.db.get_value`/`frappe.db.sql` trả rỗng cho một `name`
    không tồn tại thay vì ném lỗi — nên "không có thật" tự rơi vào NHÁNH SO
    SÁNH giống hệt "của khoa khác" (cả hai đều cho `cua != pham_vi[...]`),
    KHÔNG PHẢI hai đường code riêng cùng chung một câu chữ.

    Đây là kiểm phạm vi THEO KHOA — hoàn toàn KHÔNG thay cho kiểm phạm vi
    THEO KHÁCH HÀNG (`so.check_permission("read")`/so sánh `customer` đã có
    sẵn ở từng endpoint): với Quản lý (`pham_vi_don()` trả `{}`), hàm này
    return ngay và chốt khách hàng vẫn hoàn toàn dựa vào phép kiểm cũ đó —
    ĐỪNG xoá phép kiểm `customer` đã có khi thêm hàm này vào một endpoint.

    `Sales Order` mang `custom_khoa_phong` trực tiếp; `Delivery Note`/`Sales
    Invoice` quy về đơn cha qua bảng dòng (`against_sales_order`/
    `sales_order`) — MỘT nguồn sự thật, không nhân bản field khoa phòng đi
    các nơi (xem docstring patch `them_khoa_phong_vao_don_hang`). Một chứng
    từ nối tới NHIỀU đơn thuộc NHIỀU khoa khác nhau (biên bản gộp — chưa gặp
    trong luồng hiện tại, các hàm `make_delivery_note`/`make_sales_invoice`
    của ERPNext chỉ map từ MỘT đơn) bị coi là MƠ HỒ và ĐÓNG, không phải MỞ:
    `cua` = `None` trong trường hợp đó, không khớp bất kỳ khoa thật nào.
    """
    if pham_vi is None:
        pham_vi = pham_vi_don(user)
    if not pham_vi:
        return
    # VÒNG SỬA 3 (V2, review độc lập, Important) — kiểm TRƯỚC khi chạm bất
    # kỳ SQL nào tham chiếu `custom_khoa_phong` ở dưới. Một Quản lý
    # (`pham_vi` rỗng, đã `return` ở trên) không bao giờ chạm cột này qua
    # đây — chỉ Nhân viên khoa (đường CÓ giới hạn) mới cần lưới an toàn.
    # Thiếu cột thì FAIL-CLOSED bằng ĐÚNG thông điệp `LOI_KHONG_THAY` (không
    # tiết lộ nguyên nhân thật cho khách — "cột CSDL bị thiếu" không phải
    # thứ một khách hàng cần/được biết), không phải để MariaDB 1054 lộ ra.
    if not _cot_khoa_phong_ton_tai():
        raise frappe.PermissionError(LOI_KHONG_THAY)
    if doctype == "Sales Order":
        cua = frappe.db.get_value("Sales Order", name, "custom_khoa_phong")
    elif doctype == "Delivery Note":
        hang = frappe.db.sql(
            """select distinct so.custom_khoa_phong
               from `tabDelivery Note Item` dni
               inner join `tabSales Order` so on so.name = dni.against_sales_order
               where dni.parent = %s""",
            (name,),
        )
        cua = hang[0][0] if len(hang) == 1 else None
    elif doctype == "Sales Invoice":
        hang = frappe.db.sql(
            """select distinct so.custom_khoa_phong
               from `tabSales Invoice Item` sii
               inner join `tabSales Order` so on so.name = sii.sales_order
               where sii.parent = %s""",
            (name,),
        )
        cua = hang[0][0] if len(hang) == 1 else None
    else:
        raise NotImplementedError(
            f"dam_bao_xem_duoc chưa biết quy {doctype} về đơn cha — "
            "thêm nhánh ở đây, đừng viết điều kiện lọc rời tại endpoint."
        )
    if cua != pham_vi["custom_khoa_phong"]:
        raise frappe.PermissionError(LOI_KHONG_THAY)


def get_portal_customer(user: str | None = None) -> str:
    customers = get_allowed_customers(user)
    if not customers:
        # V4 (fix-wave 2026-08-18) — phân biệt "chưa gắn" với "có Portal
        # Member nhưng active=0", xem docstring _thong_diep_chua_thay_khach.
        raise frappe.PermissionError(_thong_diep_chua_thay_khach(user or frappe.session.user))
    return customers[0]


def get_portal_kho(user: str | None = None) -> str:
    """Tên Customer Warehouse của khách đang đăng nhập.

    Mỗi khách đúng một kho, nên hàm này trả về một chuỗi chứ không phải danh
    sách. Mọi endpoint kho đều phải đi qua đây thay vì nhận tên kho từ client.
    """
    customers = get_allowed_customers(user)
    if not customers:
        # V4 (fix-wave 2026-08-18) — cùng phân biệt như get_portal_customer().
        raise frappe.PermissionError(_thong_diep_chua_thay_khach(user or frappe.session.user))
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
