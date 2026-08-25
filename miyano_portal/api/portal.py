import frappe
from miyano_portal import dat_hang, einvoice, gia_hdnt
from miyano_portal.dat_hang import (
    _customer_addresses,
    _insert_so_idempotent,
    _resolve_item_warehouse,
)
from miyano_portal.portal_bao_gia import gui_email_khach_huy
from miyano_portal.portal_context import (
    _cot_khoa_phong_ton_tai,
    dam_bao_duoc_sua_don_da_duyet,
    dam_bao_xem_duoc,
    get_portal_customer,
    get_portal_member,
    han_muc_con,
    khoa_phong_cho_don,
    la_quan_ly,
    pham_vi_don,
)
from miyano_portal.ma_de_xuat import sinh_ma
from miyano_portal.portal_mua_le import (
    ITEM_GIU_CHO,
    TRANG_THAI_CHO_KHACH,
    cap_nhat_yeu_cau_goc,
    di_vong_bao_gia,
    han_hieu_luc_bao_gia,
    items_san_sang_giao,
    items_thuoc_hdnt_hieu_luc,
    la_dong_giu_cho,
    qua_han_hieu_luc,
    trang_thai_hang,
)
from miyano_portal.portal_hen_giao import hen_giao_cua_don
from miyano_portal.miyano_portal.doctype.portal_delivery_inspection.portal_delivery_inspection import (
    TT_TU_CHOI,
)
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
    TRANG_THAI_CHO_DUYET,
    TRANG_THAI_CHO_DUYET_SUA,
    TRANG_THAI_DA_DUYET,
    TRANG_THAI_DA_HUY,
    TRANG_THAI_NHAP,
    TRANG_THAI_TU_CHOI,
    nguon_gia_theo_ma_cho_khach,
)
from miyano_portal.portal_kiem_hang import (
    bien_ban_cua_dn,
    dong_tu_delivery_note,
)
from miyano_portal.portal_thong_bao import (
    bao_khach_sua_so_luong,
    bao_yeu_cau_ho_tro_hddt,
)

# `_customer_addresses`, `_insert_so_idempotent`, `_resolve_item_warehouse`
# đã chuyển sang `dat_hang.py` (lõi đặt hàng, xem module đó). Import lại ở
# đây vì chỗ khác trong file này vẫn dùng trực tiếp: `portal_me()` gọi
# `_customer_addresses`, `portal_order_sua_so_luong()` gọi
# `_resolve_item_warehouse`, và `tests/test_e1_idempotency.py` patch
# `frappe.db.get_value` rồi gọi thẳng `portal._insert_so_idempotent(...)` —
# đổi tên thuộc tính này trên module `portal` là phá test đó.


def _get_outstanding(customer: str) -> float:
    """Sum of unpaid GL Entry balance for this customer across companies.

    Customer.outstanding_amount is not a real field/column in this build,
    so compute it directly from GL Entry instead of frappe.db.get_value.
    """
    total = frappe.db.sql(
        """select sum(debit_in_account_currency) - sum(credit_in_account_currency)
           from `tabGL Entry`
           where party_type='Customer' and party=%s and is_cancelled=0""",
        customer,
    )[0][0]
    return float(total or 0)


@frappe.whitelist()
def portal_me() -> dict:
    customer = get_portal_customer()
    cust = frappe.db.get_value(
        "Customer", customer, ["customer_name", "tax_id"], as_dict=True
    ) or {}
    # Man luong duyet (Task 1) — Frontend cần biết vai trò để gating menu
    # (màn Duyệt chỉ cho người có quyền duyệt). `la_quan_ly` là khoá RIÊNG,
    # không để client tự suy từ `vai_tro`: kế hoạch C thêm uỷ quyền tạm
    # thời, khi đó một Nhân viên khoa ĐANG ĐƯỢC UỶ QUYỀN phải thấy menu
    # Duyệt — client tự suy `vai_tro === "Quản lý"` sẽ bỏ sót đúng ca đó.
    # `la_quan_ly()` (portal_context) là NGUỒN DUY NHẤT được hỏi, KHÔNG tự
    # so `tv.vai_tro == "Quản lý"` ở đây.
    tv = get_portal_member()
    return {
        "customer": customer,
        # Task 3 (màn /de-xuat) — `frontend/src/de-xuat-actions.js` cần
        # phân biệt CHỦ PHIẾU để hiện "Gửi duyệt"/"Xoá", nhưng không có
        # nguồn nào khác lộ session user ra frontend (đã kiểm: không
        # frappe.session/window.frappe/boot.user nào trong frontend/src).
        # Không phải rò rỉ: `frappe.session.user` chính là email người
        # ĐANG GỌI endpoint này, tức người đã đăng nhập bằng chính email
        # đó — trả lại cho họ không lộ gì họ chưa biết.
        "user": frappe.session.user,
        "customer_name": cust.get("customer_name"),
        "tax_id": cust.get("tax_id"),
        "outstanding": _get_outstanding(customer),
        "addresses": _customer_addresses(customer),
        # BR-R1 bỏ hẳn 21/08 (task-1-brief.md mục a) — không còn cờ nào để
        # trả, mọi khách đều mua lẻ được, `cho_phep_mua_le` xoá khỏi phong
        # bì này.
        "vai_tro": tv.vai_tro,
        "khoa_phong": tv.khoa_phong or None,
        "la_quan_ly": la_quan_ly(),
    }


@frappe.whitelist()
def portal_contracts() -> list:
    customer = get_portal_customer()
    today = frappe.utils.today()
    rows = frappe.get_all(
        "Blanket Order",
        filters={
            "customer": customer,
            "blanket_order_type": "Selling",
            # review M-1 (E6 phần B) — thêm `docstatus: 1` + `from_date <=
            # hôm nay`: trước bản này danh sách "hợp đồng của tôi" có thể lẫn
            # một Blanket Order còn NHÁP (chưa ai ký ở Desk) hoặc chưa tới
            # ngày hiệu lực, khiến khách tưởng mình đã có hợp đồng đang chạy.
            # Cùng bộ điều kiện với `portal_mua_le.items_thuoc_hdnt_hieu_luc`
            # (BR-R7) — hai nơi định nghĩa "HĐNT còn hiệu lực" PHẢI khớp
            # nhau: lệch nhau nghĩa là khách thấy hợp đồng ở màn này nhưng
            # BR-R7 lại không (hoặc ngược lại) coi mặt hàng của nó là "thuộc
            # HĐNT hiệu lực" ở màn mua lẻ.
            "docstatus": 1,
            "from_date": ["<=", today],
            "to_date": [">=", today],
        },
        fields=["name", "from_date", "to_date"],
        order_by="to_date asc",
    )
    for r in rows:
        # `qty > 0` là điểm mấu chốt (BR-O15): dòng khai 0 = KHÔNG GIỚI HẠN
        # nên không có mẫu số. Để nó vào thì % ra một con số vô nghĩa và cảnh
        # báo "đã dùng ≥ 80% hạn mức" sẽ báo động sai.
        agg = frappe.db.sql(
            """select sum(qty) q, sum(ordered_qty) o
               from `tabBlanket Order Item` where parent=%s and qty > 0""",
            r["name"],
        )[0]
        total, ordered = float(agg[0] or 0), float(agg[1] or 0)
        r["used_pct"] = round(ordered / total * 100, 1) if total else 0
        # Số mặt hàng vẫn đếm ĐỦ, kể cả dòng không giới hạn — khách vẫn đặt
        # được chúng, chỉ là không có trần.
        r["item_count"] = frappe.db.count("Blanket Order Item", {"parent": r["name"]})
    return rows


@frappe.whitelist()
def portal_catalog(contract: str) -> list:
    customer = get_portal_customer()
    # isolation: the contract must belong to the caller's customer
    if frappe.db.get_value("Blanket Order", contract, "customer") != customer:
        raise frappe.PermissionError("Hợp đồng không thuộc đơn vị của bạn.")
    price_list = frappe.db.get_value("Customer", customer, "default_price_list")
    out = []
    for row in frappe.get_all(
        "Blanket Order Item",
        filters={"parent": contract},
        fields=["item_code", "rate", "qty", "ordered_qty"],
    ):
        item = frappe.db.get_value(
            "Item", row["item_code"], ["item_name", "stock_uom", "item_group"], as_dict=True
        )
        # QĐ-G12 (Task 12) — TRƯỚC đây chỗ này tra `Item Price` rồi mới rơi
        # về `row["rate"]`, tức THỨ TỰ NGƯỢC với đường đặt hàng. Sau QĐ-G12
        # đơn lấy giá HỢP ĐỒNG trước, nên để nguyên là dựng lại đúng điểm
        # lệch cả kế hoạch này sinh ra để xoá: khách nhìn một giá trên danh
        # mục, đơn mang một giá khác (VD hợp đồng 88.000 / bảng giá 55.000).
        # `or 0` giữ nguyên hành vi cũ khi không tra được gì ở đâu cả —
        # `row["rate"]` lúc đó cũng là 0.
        rate = gia_hdnt.gia_dong_hop_dong(row["item_code"], contract, price_list) or 0
        con_lai, da_dat = han_muc_con(contract, row["item_code"])
        out.append({
            "item_code": row["item_code"],
            "item_name": item.item_name if item else row["item_code"],
            "uom": item.stock_uom if item else "",
            "item_group": (item.item_group if item else "") or "",
            "rate": float(rate),
            "vat_pct": 0,
            "total": float(row["qty"] or 0),
            "used": da_dat,
            # `None` chứ không phải 0: giao diện phải phân biệt "không giới
            # hạn" (NL-1.11) với "hết hạn mức" (NL-1.2) — bản cũ trả
            # `max(total - used, 0.0)` nên hai trạng thái này trông y hệt
            # nhau, và mặt hàng khai 0 hiện ra là "Hết hạn mức".
            "remaining": None if con_lai is None else max(con_lai, 0.0),
            "khong_gioi_han": con_lai is None,
            "boi_so_dat": int(
                frappe.db.get_value("Item", row["item_code"], "custom_boi_so_dat") or 0
            ),
        })
    return out


@frappe.whitelist()
def portal_catalog_ban_le(tim_kiem=None, nhom=None, start=0, limit=50) -> dict:
    """API Spec §2.2 / thiết kế lại mua lẻ §4.1 — danh mục mua lẻ = TOÀN BỘ
    `Item` đang hoạt động, KHÔNG còn là tập tuyển chọn.

    BR-R1/NL-10.1 (chốt "phải bật cờ `Customer.custom_cho_phep_mua_le` mới
    xem được danh mục") đã BỎ HẲN 21/08 — chủ đầu tư chốt 19/08: nghiệp vụ
    này áp dụng cho toàn bộ khách hàng, không còn khách nào bị chặn ở đây.

    §4.1 — "Bỏ bộ lọc `custom_ban_le_portal`": nguyên tắc chủ dự án đặt ra
    "khách không cần biết Miyano có gì; họ đặt hàng, Miyano có trách nhiệm
    gửi hàng" — filter cũ buộc khách phải biết trước Miyano có mặt hàng đó
    hay không. Hệ quả trực tiếp: KHÔNG còn gọi `price_list_ban_le()`/`_gia_
    hien_hanh` ở đây — danh mục không hiện giá (mọi phiếu mua lẻ đều đi qua
    báo giá, §4.5), nên VĐ-12 ("Price List bán lẻ phải chuẩn hoá trước khi
    bật nhánh A") tự tan cho đường ĐỌC này.

    Phân trang PHÍA SERVER (§4.1) — bắt buộc, không phải tối ưu: danh mục cũ
    là vài chục mã tuyển chọn, danh mục mới là TOÀN BỘ `tabItem` của Miyano,
    có thể vài nghìn dòng. `start`/`limit` cùng khuôn `portal_order_history`
    (api/portal.py) — KHÔNG dùng khuôn `trang`/`so_dong_moi_trang` của
    `kho/dutru.py`: hàm đó dựng toàn bộ danh sách trong Python rồi cắt lát
    (chấp nhận được cho vài trăm dòng kho của MỘT khách), ở đây phải cắt lát
    NGAY TRONG TRUY VẤN SQL (`limit_start`/`limit_page_length`) để không tải
    toàn bộ `tabItem` vào bộ nhớ mỗi lần gọi.
    """
    customer = get_portal_customer()

    # review C-1 — `ITEM_GIU_CHO` (`HANG-DAT-NGOAI`) là item KỸ THUẬT NỘI BỘ:
    # `disabled=0`, `is_sales_item=1` (patch v1_15 cần vậy để đơn "toàn hàng
    # chưa có mã" lưu được, §3.4) nên nếu không loại tường minh ở đây, nó lọt
    # thẳng vào danh mục như một sản phẩm khách duyệt được — đúng thứ nguyên
    # tắc nền "khách không cần biết Miyano có gì" cấm. Loại bằng `name` (==
    # `item_code` chính tắc), KHÔNG lọc qua `is_sales_item`/`disabled`: hai cờ
    # đó phục vụ mục đích khác (bật/tắt bán, còn kinh doanh hay không) và có
    # thể đổi độc lập với việc đây là item giữ chỗ hay không.
    filters = {"disabled": 0, "name": ["!=", ITEM_GIU_CHO]}
    if nhom:
        filters["item_group"] = nhom
    or_filters = None
    if tim_kiem:
        # Tìm theo cả mã lẫn tên — `filters` của `get_all` AND với nhau, nên
        # điều kiện "khớp mã HOẶC tên" phải đi qua `or_filters`.
        or_filters = [
            ["item_code", "like", f"%{tim_kiem}%"],
            ["item_name", "like", f"%{tim_kiem}%"],
        ]
    start = max(0, int(start or 0))
    limit = max(1, int(limit or 50))

    # `frappe.db.count` KHÔNG nhận `or_filters` — phải đếm qua `get_all` với
    # ĐÚNG bộ filters/or_filters của truy vấn trang dưới, nếu không `tong`
    # sẽ lặng lẽ bỏ qua điều kiện tìm kiếm khi `tim_kiem` có giá trị.
    tong = frappe.get_all(
        "Item", filters=filters, or_filters=or_filters,
        fields=["count(name) as tong"],
    )[0].tong

    rows = frappe.get_all(
        "Item", filters=filters, or_filters=or_filters,
        fields=["item_code", "item_name", "description", "stock_uom"],
        # `item_name` không unique — thêm `name` làm tiebreak để thứ tự
        # TẤT ĐỊNH giữa hai trang (không có nó, hai mã cùng tên có thể rơi
        # vào CẢ HAI trang hoặc KHÔNG trang nào tuỳ thứ tự trả về của MariaDB).
        order_by="item_name asc, name asc",
        limit_start=start, limit_page_length=limit,
    )

    thuoc_hdnt = items_thuoc_hdnt_hieu_luc(customer)
    # review I-3 — tín hiệu "chưa sẵn sàng giao" NGAY TẠI DANH MỤC, một truy
    # vấn cho cả trang thay vì gọi resolve_ban_le_company() N lần. Chỉ tính
    # cho ĐÚNG các dòng của trang hiện tại — không phải toàn bộ danh mục.
    san_sang = items_san_sang_giao([r.item_code for r in rows])

    out = []
    for r in rows:
        # review M-3 — `Item.description` là Text Editor (HTML) và ERPNext
        # TỰ ĐỘNG chép `item_name` vào đây làm giá trị khởi tạo khi tạo
        # Item — bản trước trả thẳng `r.description or ""` nên cột "Quy
        # cách" trên danh mục lẻ thường hiện lại CHÍNH TÊN HÀNG (hoặc một
        # đoạn `<div>…</div>` thô nếu ai đó gõ mô tả có định dạng), sai loại
        # dữ liệu khách nhìn thấy. Bóc HTML rồi bỏ nếu nó chỉ là bản sao của
        # tên hàng — thà trống còn hơn thông tin sai.
        quy_cach = frappe.utils.strip_html(r.description or "").strip()
        if quy_cach == (r.item_name or "").strip():
            quy_cach = ""
        out.append({
            "item_code": r.item_code,
            "ten": r.item_name,
            "quy_cach": quy_cach,
            "dvt": r.stock_uom,
            "trang_thai_hang": trang_thai_hang(r.item_code),
            # BR-R7/§4.2 — GIỮ NGUYÊN cờ này (chốt an ninh của E1, không
            # được nới): mặt hàng đang thuộc HĐNT còn hiệu lực của khách
            # vẫn hiện ra (khác trước: KHÔNG còn biến mất im lặng), nhưng
            # client phải hiện mờ kèm lý do "Có trong HĐNT — đặt ở chế độ
            # Theo HĐNT" và khoá nút thêm giỏ Mua lẻ cho dòng này.
            "thuoc_hdnt": r.item_code in thuoc_hdnt,
            # review I-3 — False: admin CHƯA khai Item Default (company/kho)
            # cho mặt hàng này. Phần C nên khoá nút thêm giỏ và hiện "Miyano
            # đang cập nhật, vui lòng liên hệ" thay vì để khách điền hết giỏ
            # mới nhận lỗi ở bước Xác nhận.
            "san_sang_ban": r.item_code in san_sang,
        })
    return {"items": out, "tong": tong, "start": start, "limit": limit}


@frappe.whitelist()
def portal_catalog_gop(tu_khoa=None, contract=None, start=0, limit=50) -> dict:
    """Task 3 (gộp luồng đặt hàng, 21/08/2026) — MỘT endpoint tìm kiếm gộp
    BA TẦNG cho màn Lập phiếu (`LapPhieu.vue`, Task 8, chạy song song).
    Hình dạng trả về ĐÃ ĐÓNG BĂNG (`hop-dong-endpoint-tim-kiem.md`, Task 8
    code thẳng vào nó) — KHÔNG tự đổi khoá/kiểu dữ liệu ở đây:

        {"rows": [{item_code, item_name, dvt, tang, don_gia,
                   blanket_order, boi_so,
                   trang_thai_hang, total, used, remaining,
                   khong_gioi_han}], "tong": int}

    `tang` chỉ nhận `"hop_dong"` hoặc `"cho_bao_gia"`. `don_gia`/
    `blanket_order`/`boi_so` là `None` (KHÔNG phải `0`) khi không áp dụng —
    `0` là một giá/bội số HỢP LỆ, dùng nó làm "rỗng" sẽ không phân biệt
    được đúng lúc cần phân biệt nhất. Tầng 3 (hàng chưa có mã) KHÔNG đến từ
    đây — đó là dòng khách gõ tay, đi qua bảng "đặt ngoài" của phiếu.

    Ruling P14 — tầng suy THEO DÒNG, đối chiếu MỌI Blanket Order còn hiệu
    lực của khách đang đăng nhập (`nguon_gia_theo_ma_cho_khach()`, module
    `portal_de_xuat_mua`, CÙNG hàm `PortalDeXuatMua._suy_nguon_gia()` gọi —
    KHÔNG viết một bản suy giá thứ hai ở đây: luật này quyết định giá, hai
    bản lệch nhau sớm muộn cũng ra hai giá khác nhau cho cùng một mặt
    hàng). Tham số `contract`, nếu truyền, CHỈ thu hẹp DANH SÁCH mã hàng
    hiện ra (mã phải thuộc đúng hợp đồng đó) — nó KHÔNG tắt việc tra hợp
    đồng: không truyền `contract` không có nghĩa "đừng suy tầng", tầng vẫn
    luôn suy customer-wide.

    Cách ly (BR — vai trò khách): `get_portal_customer()` suy khách từ
    CHÍNH phiên đăng nhập, không nhận `customer` từ client — cùng khuôn
    `portal_catalog`/`portal_catalog_ban_le` ở trên. `role Customer` có
    ZERO DocPerm trên `Item`/`Blanket Order` nên dùng `frappe.get_all`/
    `frappe.db.*` (không `frappe.get_list`/`doc.check_permission()` — hai
    đường đó ném `PermissionError` cho một Website User trước khi chạy tới
    đây).

    Phân trang PHÍA SERVER, NGAY TRONG TRUY VẤN SQL (`limit_start`/
    `limit_page_length`, cùng khuôn `portal_order_history`/`portal_catalog_
    ban_le`) — KHÔNG dựng toàn bộ danh mục trong Python rồi cắt lát:
    `tabItem` là TOÀN BỘ danh mục Miyano.

    Task 10 (gộp "Đặt hàng" và "Lập phiếu", 21/08/2026) — BỔ SUNG, không
    đổi khoá cũ:

    * `trang_thai_hang` — ĐÚNG cơ chế màn mua lẻ đang dùng (`portal_mua_le.
      trang_thai_hang`, đọc tồn Miyano thật ở `tabBin`), KHÔNG dựng cơ chế
      thứ hai: hai cách trả lời "còn hàng không" sớm muộn cũng trả lời khác
      nhau cho cùng một mã.
    * `total`/`used`/`remaining`/`khong_gioi_han` — hạn mức còn lại cho
      dòng TẦNG 1, dùng LẠI `portal_context.han_muc_con()` (nguồn duy nhất
      của luật hạn mức) và ĐÚNG bộ khoá `portal_catalog` đã trả cho màn cũ,
      để giao diện không phải học hai phương ngữ cho cùng một thứ.
      `remaining is None` + `khong_gioi_han is True` = khai `qty = 0`, quy
      ước KHÔNG GIỚI HẠN (QĐ-8/BR-O15); `remaining == 0.0` = HẾT hạn mức —
      gộp hai trạng thái này là cách chắc chắn hiện sai một trong hai.
      Dòng tầng 2 không thuộc hợp đồng nào nên cả bốn khoá đều rỗng
      (`None`/`False`), không phải "không giới hạn".
    * THỨ TỰ — QĐ-G10: hàng trong hợp đồng của CHÍNH khách đứng TRƯỚC, hết
      rồi mới tới danh mục chung. Làm bằng HAI truy vấn phân đôi (`name in`
      / `name not in` tập mã hợp đồng), mỗi truy vấn vẫn cắt trang trong
      SQL — KHÔNG nhét `CASE WHEN` vào `order_by` (`DatabaseQuery.validate_
      order_by_and_group_by` của Frappe soi từng vế theo tên cột, một biểu
      thức sẽ bị từ chối) và KHÔNG kéo cả danh mục về Python để sắp xếp.
      `tong` là tổng hai nửa — hai nửa là một PHÂN HOẠCH của đúng bộ lọc cũ
      nên con số không đổi so với bản một truy vấn.
    """
    customer = get_portal_customer()
    start = max(0, int(start or 0))
    limit = max(1, int(limit or 50))

    # Cùng khuôn `portal_catalog_ban_le` — loại item KỸ THUẬT NỘI BỘ
    # (`HANG-DAT-NGOAI`) khỏi danh mục khách nhìn thấy. Dùng danh sách
    # điều kiện (không phải dict) vì `contract` bên dưới có thể thêm một
    # điều kiện THỨ HAI trên cùng field `name` — dict filters của
    # `frappe.get_all` không biểu diễn được hai điều kiện trên một field.
    filters = [["disabled", "=", 0], ["name", "!=", ITEM_GIU_CHO]]
    or_filters = None
    if tu_khoa:
        or_filters = [
            ["item_code", "like", f"%{tu_khoa}%"],
            ["item_name", "like", f"%{tu_khoa}%"],
        ]

    if contract:
        # Isolation — cùng chốt `portal_catalog`: hợp đồng truyền vào phải
        # thuộc chính khách đang đăng nhập.
        if frappe.db.get_value("Blanket Order", contract, "customer") != customer:
            raise frappe.PermissionError("Hợp đồng không thuộc đơn vị của bạn.")
        ma_thuoc_hop_dong = frappe.get_all(
            "Blanket Order Item", filters={"parent": contract}, pluck="item_code",
        )
        # `or [""]` — mảng rỗng cho `["name", "in", []]` không tất định
        # trên mọi bản Frappe; một hợp đồng không mặt hàng nào thì kết quả
        # phải là RỖNG, không phải "bỏ qua điều kiện".
        filters.append(["name", "in", ma_thuoc_hop_dong or [""]])

    # MỘT truy vấn cho CẢ TRANG (không lặp theo từng dòng) — hợp đồng
    # thắng cuộc của khách là customer-wide, không phụ thuộc từ khoá tìm.
    # Phải tính TRƯỚC phần truy vấn danh mục: chính tập mã này chia danh
    # mục làm hai nửa (QĐ-G10).
    thang_cuoc = nguon_gia_theo_ma_cho_khach(customer)
    price_list = frappe.db.get_value("Customer", customer, "default_price_list")
    ma_hop_dong = sorted(thang_cuoc)

    COT = ["item_code", "item_name", "stock_uom", "custom_boi_so_dat"]
    # `item_name` không unique — thêm `name` làm tiebreak để thứ tự
    # TẤT ĐỊNH giữa hai trang, cùng lý do `portal_catalog_ban_le`.
    THU_TU = "item_name asc, name asc"

    def _dem(dk):
        # `frappe.db.count` KHÔNG nhận `or_filters` — đếm qua `get_all` với
        # ĐÚNG bộ filters/or_filters của truy vấn trang dưới (cùng lý do
        # `portal_catalog_ban_le` đã ghi), nếu không `tong` sẽ lặng lẽ bỏ
        # qua điều kiện tìm kiếm khi `tu_khoa` có giá trị.
        return frappe.get_all(
            "Item", filters=dk, or_filters=or_filters, fields=["count(name) as tong"],
        )[0].tong

    def _trang(dk, bat_dau, so_dong):
        if so_dong <= 0:
            return []
        return frappe.get_all(
            "Item", filters=dk, or_filters=or_filters, fields=COT, order_by=THU_TU,
            limit_start=bat_dau, limit_page_length=so_dong,
        )

    if ma_hop_dong:
        dk_hop_dong = filters + [["name", "in", ma_hop_dong]]
        dk_chung = filters + [["name", "not in", ma_hop_dong]]
        tong_hop_dong = _dem(dk_hop_dong)
        tong = tong_hop_dong + _dem(dk_chung)
        if start < tong_hop_dong:
            rows = _trang(dk_hop_dong, start, limit)
            # Nửa hợp đồng đã hết giữa chừng trang này → phần còn lại của
            # trang lấy từ ĐẦU nửa danh mục chung (offset 0, không phải
            # `start`): đó đúng là dòng kế tiếp trong thứ tự gộp.
            rows += _trang(dk_chung, 0, limit - len(rows))
        else:
            rows = _trang(dk_chung, start - tong_hop_dong, limit)
    else:
        # Khách chưa có hợp đồng nào còn hiệu lực — không có nửa nào để tách.
        # CỐ Ý không đi qua `["name", "not in", []]`: mảng rỗng trong toán tử
        # tập hợp không tất định trên mọi bản Frappe (cùng bẫy `or [""]` ở
        # nhánh `contract` phía trên).
        tong = _dem(filters)
        rows = _trang(filters, start, limit)

    out = []
    for r in rows:
        bo = thang_cuoc.get(r.item_code)
        # Ruling P16 — `0`/chưa khai đều nghĩa là "không ràng buộc bội số",
        # trả `None` (KHÔNG phải `0`) để khớp quy ước "0 là giá trị hợp lệ"
        # của cả hợp đồng đóng băng lẫn `kiem_boi_so()` (`portal_dat_hang.py`).
        boi_so = int(r.custom_boi_so_dat or 0) or None
        dong = {
            "item_code": r.item_code, "item_name": r.item_name, "dvt": r.stock_uom,
            "boi_so": boi_so,
            "trang_thai_hang": trang_thai_hang(r.item_code),
        }
        if bo:
            # ĐÚNG nguồn giá cả bốn nơi dùng (`gia_hdnt.gia_dong_hop_dong`,
            # QĐ-G12) — bốn đường tra giá khác nhau sớm muộn cũng lệch. Màn
            # Lập phiếu phải hiện ĐÚNG con số mà đơn sẽ mang: trước Task 12
            # nó hiện `null` cho mọi mã chỉ có giá trên hợp đồng, rồi cổng
            # chặn đơn ở bước gửi — mâu thuẫn khách không tự giải thích được.
            don_gia = gia_hdnt.gia_dong_hop_dong(r.item_code, bo, price_list)
            con_lai, da_dat = han_muc_con(bo, r.item_code)
            dong.update({
                "tang": "hop_dong",
                "don_gia": float(don_gia) if don_gia is not None else None,
                "blanket_order": bo,
                # Cùng bộ khoá `portal_catalog` — xem docstring. `remaining`
                # `None` CHỈ khi không giới hạn, và `khong_gioi_han` là khoá
                # phân định, không phải suy từ `remaining` ở tầng hiển thị.
                "total": float(con_lai + da_dat) if con_lai is not None else 0.0,
                "used": da_dat,
                "remaining": None if con_lai is None else max(con_lai, 0.0),
                "khong_gioi_han": con_lai is None,
            })
        else:
            dong.update({
                "tang": "cho_bao_gia", "don_gia": None, "blanket_order": None,
                "total": None, "used": None, "remaining": None,
                "khong_gioi_han": False,
            })
        out.append(dong)
    return {"rows": out, "tong": tong}


@frappe.whitelist()
def portal_order_place(
    contract=None, items=None, po=None, delivery_date=None, note=None, address=None,
    request_id=None, mode="hdnt", dat_ngoai=None, khoa_phong=None,
) -> dict:
    """API Spec §1.1 — `mode`: `"hdnt"` (mặc định, [Hiện có]) | `"ban_le"`
    (E6 phần B, [MỚI]). Tham số vẫn tên `contract` (không phải `hdnt` như
    JSON mẫu của API Spec) để KHÔNG đổi chữ ký mà `frontend/src/views/
    Cart.vue` (đã chạy thật) đang gọi — đổi tên tham số ở đây là đổi API mà
    không có gì buộc phần C phải đổi theo, một chỗ lệch tài liệu đã có từ
    trước E6, không phải lỗi tạo mới ở đây.

    Vỏ mỏng (bước 1, tách lõi đặt hàng — xem `dat_hang.py`): xác định khách
    hàng từ PHIÊN ĐĂNG NHẬP rồi giao toàn bộ việc tạo Sales Order cho
    `dat_hang.tao_sales_order`, KHÔNG ĐỔI. Task 7 (§5.5) thêm ĐÚNG hai việc
    quanh lõi đó, không đụng vào chính nó:

    C1 (review vòng sửa 1, CRITICAL — SỬA LẠI ở Task 7, bình luận cũ ở đây
    nói SAI thực tế mới, xem QĐ điều phối viên 19/08/2026 trong
    `task-7-report.md`): bản TRƯỚC Task 7 chặn bằng cách "không có tham số
    `khoa_phong` trong chữ ký". Nhưng §5.5 đòi giỏ hàng của QUẢN LÝ có ô
    chọn khoa (mặc định "Toàn viện") — nên tham số `khoa_phong` giờ CÓ mặt,
    và phép chặn A-đóng-dấu-thành-B chuyển sang `portal_context.
    khoa_phong_cho_don()`, hàm role-aware DUY NHẤT được phép đọc/ghi
    `khoa_phong` cho đường ghi này:
      * Nhân viên khoa KHÔNG được gọi endpoint này chút nào nữa (chặn ở
        dòng đầu, xem dưới) — họ đi qua `de_xuat_gui_duyet` để quản lý
        duyệt. Gọi thẳng vẫn bị từ chối rõ ràng, không phải lỗi khó hiểu.
      * Quản lý ĐƯỢC chọn khoa qua `khoa_phong`, nhưng `khoa_phong_cho_don()`
        tự kiểm khoa đó thuộc ĐÚNG bệnh viện của họ và đang `active` —
        không nhận thẳng giá trị client gửi mà không kiểm.

    §5.5 (thân bài, "mọi đơn trên hệ thống đều có đúng MỘT chứng từ đề nghị
    đứng sau") — sau khi `dat_hang.tao_sales_order` tạo xong Sales Order,
    hàm này GHI một `Portal De Xuat Mua` "Đã duyệt" đứng sau, `nguoi_duyet`
    là chính quản lý. CỐ Ý KHÔNG route qua `de_xuat_duyet.duyet_va_tao_don`
    (QĐ điều phối viên 19/08 — SỬA LẠI ở review M3, chữ dùng lần đầu SAI,
    xem `task-7-report.md`): CẢ HAI đường đều NÉM (`frappe.throw`, đều
    `ValidationError`) khi vượt hạn mức — không phải một MỀM một CỨNG.
    Khác biệt thật là dữ liệu ĐI KÈM lúc ném: `dat_hang.tao_sales_order`
    (nhánh HĐNT) ghi `frappe.local.response["loi"]` — danh sách CÓ CẤU
    TRÚC theo từng dòng hàng (`item_code`/`ly_do`/`thong_diep`) — TRƯỚC khi
    throw, mà nhiều test (`test_e1_loi_co_cau_truc.py` và các test E1
    khác) đọc trực tiếp từ `frappe.local.response["loi"]` sau khi bắt
    `ValidationError` từ kết quả hàm NÀY. `_kiem_han_muc` (bên trong
    `duyet_va_tao_don`) chỉ `frappe.throw` một câu văn xuôi PHẲNG, không
    ghi gì vào `frappe.local.response`. Route qua `duyet_va_tao_don` sẽ mất
    dữ liệu có cấu trúc đó cho MỌI người gọi, không riêng nhân viên khoa —
    trong khi sáu tài khoản đang chạy thật đều là quản lý và đi qua đúng
    đường này mỗi ngày. (`bi_loai`/`ly_do` là khoá của MỘT HÀM KHÁC hẳn,
    `portal_reorder` — không liên quan gì tới đường này; đừng nhầm.)
    """
    if not la_quan_ly():
        # §5.5 câu cuối — chặn HẲN, không phải một lỗi CSDL/hạn mức khó
        # hiểu lộ ra từ tầng dưới. Chặn TRƯỚC khi chạm bất kỳ thứ gì khác
        # (customer, khoa_phong_cho_don, dat_hang) — không để lỡ tạo ra bất
        # kỳ chứng từ nào rồi mới từ chối.
        frappe.throw(
            "Nhân viên khoa không đặt hàng trực tiếp qua giỏ hàng được. "
            "Vui lòng tạo phiếu đề xuất và gửi duyệt để quản lý phê duyệt.",
            frappe.ValidationError,
        )
    customer = get_portal_customer()
    khoa = khoa_phong_cho_don(khoa_phong)
    kq = dat_hang.tao_sales_order(
        customer,
        mode=mode, contract=contract, items=items, dat_ngoai=dat_ngoai,
        po=po, delivery_date=delivery_date, note=note, address=address,
        request_id=request_id, khoa_phong=khoa,
    )
    kq["de_xuat"] = _dam_bao_phieu_tu_duyet(
        customer=customer, khoa_phong=khoa, mode=mode, contract=contract,
        dat_ngoai=dat_ngoai, delivery_date=delivery_date, address=address,
        note=note, request_id=request_id,
        sales_order=kq["sales_order"], da_ton_tai=bool(kq.get("da_ton_tai")),
    )
    return kq


def _dam_bao_phieu_tu_duyet(
    customer, khoa_phong, mode, contract, dat_ngoai, delivery_date, address,
    note, request_id, sales_order, da_ton_tai,
) -> str | None:
    """§5.5 — một `Portal De Xuat Mua` "Đã duyệt" đứng sau MỌI đơn quản lý
    đặt trực tiếp, `nguoi_duyet` là chính họ, `tu_duyet = 1`.

    KHÔNG dùng `PortalDeXuatMua.gui_duyet()`/`.duyet()` (Task 3): hai
    phương thức đó gắn CỨNG vào máy trạng thái Nháp → Chờ duyệt → Đã duyệt
    (phiếu này SINH RA đã "Đã duyệt", không có ai chờ duyệt) và `gui_duyet()`
    bắt buộc `sinh_ma()` không được lỗi — điều đó ĐÚNG cho nhân viên GỬI
    DUYỆT (guard cấp tài khoản đã bắt buộc Mã ngắn từ trước), nhưng SAI cho
    đường đặt trực tiếp của quản lý (QĐ điều phối viên 19/08): xem carve-out
    thiếu Mã ngắn ngay dưới.

    `da_ton_tai=True` (BR-O12, bấm lại) — KHÔNG tạo phiếu thứ hai, tìm phiếu
    đã đứng sau `sales_order` đó mà trả về. Một `sales_order` cũ TRƯỚC
    Task 7 (đặt thẳng, không qua đường này) có thể không có phiếu nào đứng
    sau — trả `None`, đúng tinh thần "102 đơn cũ không có phiếu đề xuất"
    (`TestDeXuatMaTraCuuTrenDonHang`), không tự bịa một phiếu cho quá khứ.
    """
    if da_ton_tai:
        # Lọc CẢ `request_id` — `sales_order` một mình không phải khoá định
        # danh của lần bấm này, chỉ là hệ quả của nó. `request_id` mới thật
        # sự là thứ BR-O12 dùng để nhận ra "đây là cú bấm lại", nên đây mới
        # là điều kiện CHÍNH XÁC, không phải suy đoán qua kết quả phụ.
        return frappe.db.get_value(
            "Portal De Xuat Mua",
            {"sales_order": sales_order, "request_id": request_id},
            "name",
        )

    # Đọc lại dòng hàng THẬT từ chính Sales Order vừa tạo — canonical hoá
    # item_code + gộp dòng trùng đã được `dat_hang.tao_sales_order` làm rồi
    # (BR-R… chuẩn hoá case/khoảng trắng), không viết lại lần hai ở đây.
    # Bỏ dòng giữ chỗ kỹ thuật `ITEM_GIU_CHO` — nó không phải một mặt hàng
    # khoa "đề xuất", chỉ để ERPNext lưu được đơn toàn dòng đặt ngoài.
    dong = [
        {
            "item_code": r.item_code,
            "so_luong_de_xuat": r.qty,
            "so_luong_duyet": r.qty,
        }
        for r in frappe.get_all(
            "Sales Order Item", filters={"parent": sales_order},
            fields=["item_code", "qty"],
        )
        if r.item_code != ITEM_GIU_CHO
    ]

    nguoi = frappe.session.user
    gio = frappe.utils.now_datetime()
    doc = frappe.get_doc({
        "doctype": "Portal De Xuat Mua",
        "customer": customer, "khoa_phong": khoa_phong,
        # Task 2 (gộp luồng đặt hàng) — `loai_don` đã xoá khỏi doctype.
        # `PortalDeXuatMua._suy_nguon_gia()` (validate(), chạy ngay trong
        # `.insert()` bên dưới) tự suy `nguon_gia` từng dòng từ `hdnt`,
        # không cần khai "loại đơn" ở đây nữa.
        "hdnt": contract if mode == "hdnt" else None,
        "ngay_can": delivery_date, "dia_chi_giao": address,
        "request_id": request_id, "sales_order": sales_order,
        "items": dong, "dat_ngoai": frappe.parse_json(dat_ngoai) if isinstance(
            dat_ngoai, str
        ) else (dat_ngoai or []),
        "ghi_chu": note,
        "ly_do_yeu_cau": "Đặt hàng trực tiếp qua giỏ hàng quản lý (tự động duyệt).",
        "trang_thai": TRANG_THAI_DA_DUYET,
        "thoi_diem_gui": gio, "thoi_diem_duyet": gio,
        "nguoi_duyet": nguoi, "duyet_voi_tu_cach": "Quản lý chính",
        # `tu_duyet` KHÔNG khai tay ở đây — `PortalDeXuatMua._suy_tu_duyet()`
        # (validate(), Task 7 review M4) tự tính từ `nguoi_duyet == owner`
        # ngay khi `insert()` chạy (`owner` đã là `frappe.session.user` từ
        # trước validate()); giữ tay ở đây sẽ là hai nơi cùng viết một sự
        # thật, đúng thứ `.duyet()` (Task 3) đã tự nhắc mình tránh.
    })
    try:
        doc.ma_de_xuat = sinh_ma(customer, khoa_phong)
    except frappe.ValidationError:
        # QĐ điều phối viên 19/08 ("Blocker 2") — thiếu `Customer.
        # custom_ma_ngan` KHÔNG được chặn đơn trực tiếp của quản lý (khác
        # nhân viên GỬI DUYỆT, nơi guard cấp tài khoản đã bắt buộc Mã ngắn
        # từ trước khi có tài khoản `Nhân viên khoa`). Mã tra cứu là tiện
        # ích đối chiếu, không phải điều kiện đúng đắn của một đơn hàng —
        # không bao giờ để nó chặn một bệnh viện mua hàng. Để rỗng, không
        # throw.
        doc.ma_de_xuat = None
    doc.insert(ignore_permissions=True)

    frappe.db.set_value("Sales Order", sales_order, {
        "custom_de_xuat": doc.name,
        "custom_ma_tra_cuu": doc.ma_de_xuat,
    })
    return doc.name


def _so_status_vi(so_status, per_delivered=None):
    """Vietnamese label for a Sales Order, delivery-aware.

    Per the BA doc the progression is:
      Chờ xác nhận -> Đang xử lý -> Đang giao -> Hoàn thành
    Raw ERPNext status alone conflates "Đang xử lý" and "Đang giao": both
    "To Deliver and Bill" and "To Bill" can appear while a delivery has
    already started (per_delivered > 0). So once delivery has started but
    the order isn't Completed/Cancelled/Closed, show "Đang giao" regardless
    of the raw status string.
    """
    if so_status == "Completed":
        return "Hoàn thành"
    if so_status == "Closed":
        # NL-2.8 — đóng sớm KHÁC huỷ: phần đã giao vẫn là hàng khách đã nhận.
        # Gộp chung vào "Đã huỷ" khiến khách tưởng không nhận được gì.
        # TODO(VĐ-7): phần chưa giao hiện KHÔNG được hoàn vào hạn mức Blanket
        # Order. Chỉ làm khi chủ đầu tư chốt cơ chế — xem BA §VĐ-7.
        return "Hoàn thành (đóng sớm)"
    if so_status == "Cancelled":
        return "Đã huỷ"
    if float(per_delivered or 0) > 0:
        return "Đang giao"
    if so_status == "Draft":
        return "Chờ xác nhận"
    # To Deliver and Bill / To Bill / To Deliver, all with 0 delivered so far.
    return "Đang xử lý"


# Ba `workflow_state` của Sales Order mà CỔNG phải đọc riêng, vì chúng
# ĐÈ LÊN `so.status` gốc của ERPNext:
#   * `Khách huỷ` / `Báo giá hết hạn` — cổng tự ghi (`portal_order_huy`,
#     `portal_bao_gia.quet_bao_gia_het_han`), `docstatus` VẪN 0;
#   * `Từ chối` — state THẬT của máy trạng thái `Sales Order - Client
#     Portal` (`setup/install_workflow.py`), Sales User bấm từ "Chờ Miyano
#     xác nhận", cũng `doc_status = 0`.
# Đặt tên MỘT LẦN ở đây, ngay trên hàm đọc chúng: trước bản này ba chuỗi
# nằm rải ở `_so_status_vi_full`, `_TRANG_THAI_GHI_DE_WORKFLOW` và khối SQL
# của `_sql_giai_doan` — và đúng chỗ rải đó là nơi `Từ chối` bị bỏ sót.
WF_KHACH_HUY = "Khách huỷ"
WF_BAO_GIA_HET_HAN = "Báo giá hết hạn"
WF_TU_CHOI = "Từ chối"


def _so_status_vi_full(so_status, per_delivered, workflow_state) -> str:
    """`_so_status_vi` chỉ đọc từ điển trạng thái GỐC của ERPNext
    (`so.status`), không biết gì về `workflow_state` của Client Portal.
    Job daily `portal_bao_gia.quet_bao_gia_het_han` chuyển `workflow_state`
    sang "Báo giá hết hạn" nhưng `docstatus` VẪN 0 (nháp không submit) —
    không bọc ở đây thì một đơn ĐÃ CHẾT đọc ra y hệt "Chờ xác nhận" đang
    sống, ở CẢ danh sách đơn (`portal_order_history`) lẫn chi tiết đơn
    (`portal_order_track`). Một hàm DÙNG CHUNG ở cả hai, không phải hai lần
    viết tay điều kiện này — lệch nhau là đúng kiểu lỗi đã bắt ở
    `portal_mua_le.han_hieu_luc_bao_gia`.
    """
    if workflow_state == WF_BAO_GIA_HET_HAN:
        return "Báo giá đã hết hiệu lực"
    # Việc 2/brief 2026-08-15 — cùng lý do trên: `portal_order_huy` huỷ THẬT
    # (workflow_state = "Khách huỷ") nhưng KHÔNG submit/cancel ERPNext
    # (`docstatus` vẫn 0 — chỉ Sales Manager mới "Mở lại" được, không phải
    # cancel hồi phục kiểu ERPNext chuẩn). Không bọc ở đây thì đơn khách vừa
    # tự huỷ đọc ra y hệt "Chờ xác nhận" đang sống — ĐÚNG lỗi brief mở đầu
    # đã nêu ("khách bấm huỷ xong đơn vẫn hiện 'chờ bạn đồng ý' -> tưởng
    # chưa ăn"), chỉ khác chỗ đứng (trước ở `portal_request_cancel`, giờ ở
    # đây). Dùng lại đúng nhãn "Đã huỷ" mà `_so_status_vi` đã dùng cho
    # `so_status == "Cancelled"` — cùng badge đỏ `b-red` ở frontend
    # (`format.js::statusBadge`), không cần sửa gì bên đó.
    if workflow_state == WF_KHACH_HUY:
        return "Đã huỷ"
    # Review vòng 1 Task 11 (Important) — CÙNG lỗ hổng với hai nhánh trên,
    # chỉ khác chỗ nó xuất phát: `Từ chối` không do cổng ghi mà là state
    # THẬT của máy trạng thái (Sales User bấm từ "Chờ Miyano xác nhận",
    # `doc_status = 0`). Thiếu nhánh này, một đơn Miyano ĐÃ TỪ CHỐI đọc ra
    # "Chờ xác nhận" — y hệt một đơn đang sống — và khoa chờ vô hạn một lô
    # hàng không bao giờ tới. Đo được trên site: `MD-HUYETHOC-260821-01`,
    # khoa `KP-00002`, đúng khoa của tài khoản nghiệm thu.
    #
    # Nhãn nêu rõ AI từ chối: "Từ chối" trần trùi trùng nghĩa với trạng thái
    # phiếu đề xuất (quản lý BỆNH VIỆN từ chối) — hai sự kiện khác hẳn nhau
    # về người ra quyết định và về việc khoa phải làm tiếp.
    if workflow_state == WF_TU_CHOI:
        return "Miyano đã từ chối"
    return _so_status_vi(so_status, per_delivered)


# Sales Invoice uses a different status vocabulary than Sales Order, so it needs
# its own Vietnamese map (a "Draft" invoice must not read "Chờ xác nhận").
INVOICE_STATUS_VI = {
    "Draft": "Nháp",
    "Unpaid": "Chưa thanh toán",
    "Unpaid and Discounted": "Chưa thanh toán",
    "Partly Paid": "TT một phần",
    "Partially Paid": "TT một phần",
    "Partly Paid and Discounted": "TT một phần",
    "Paid": "Đã thanh toán",
    "Overdue": "Quá hạn",
    "Overdue and Discounted": "Quá hạn",
    "Return": "Trả hàng",
    "Credit Note Issued": "Đã phát hành giấy báo có",
    "Submitted": "Đã ghi sổ",
    "Cancelled": "Đã huỷ",
}


def _invoice_status_vi(status):
    return INVOICE_STATUS_VI.get(status, status)


def _phieu_nhap_trang_thai_vi(docstatus: int, co_chenh_lech) -> str:
    """US-E3.4 (FormSpec F-07 khối đợt giao): ba trạng thái đúng nguyên văn
    AC — "Nháp" (client tự ghép thành "Phiếu nhập PNK-xxx — Nháp, chờ kiểm
    nhận" kèm link), "Đã ghi sổ", hoặc "Có chênh lệch ⚠" (docstatus=1 VÀ
    co_chenh_lech — ghi đè "Đã ghi sổ" vì đây là tín hiệu khách CẦN thấy
    ngay, không phải một chi tiết phụ). docstatus=2 (đã huỷ) không tới được
    hàm này — receipts_by_dn ở portal_order_track chỉ lấy docstatus < 2."""
    if docstatus == 0:
        return "Nháp"
    return "Có chênh lệch ⚠" if co_chenh_lech else "Đã ghi sổ"


# Brief 2026-08-16 (vá hồi quy phân trang) — trước bản này, chip lọc trạng
# thái ở Orders.vue lọc PHÍA CLIENT trên đúng MỘT trang đã tải: khách chọn
# "xem 10" rồi bấm "Chờ xác nhận" thấy TRỐNG dù đơn khớp nằm ở trang 2 —
# khách kết luận SAI là mình không có đơn nào đang chờ. `status_vi` (nhãn
# khách nhìn thấy) là GIÁ TRỊ SUY RA từ `status`/`per_delivered`/
# `workflow_state` qua `_so_status_vi_full`, không phải cột DB — hàm dưới
# đây dịch NGƯỢC mỗi nhãn trong `FILTERS` (Orders.vue) thành đúng bộ
# filters/or_filters SQL tương đương, để lọc được NGAY TRONG TRUY VẤN, dùng
# CHUNG cho cả `portal_order_history` (lọc + đếm `tong`) và
# `portal_dashboard_kpi` (đếm KPI) — viết tay điều kiện này hai lần là đúng
# kiểu lệch nhau đã từng bắt ở `_so_status_vi`/`_so_status_vi_full`.
# Đúng ba state mà `_so_status_vi_full` ghi đè `so.status` — dựng TỪ chính
# ba hằng đó, không chép lại chuỗi. Một state được thêm nhãn ở hàm kia mà
# quên thêm vào đây thì hai tầng nói hai điều khác nhau về CÙNG một đơn:
# danh sách hiện "Miyano đã từ chối" trong khi chip/KPI vẫn đếm nó là "Chờ
# xác nhận". Đó chính là cách `Từ chối` lọt lưới ở bản đầu Task 11.
#
# (Không có chip nào của `_dieu_kien_loc_trang_thai_don` LỌC RA đơn bị từ
# chối — cố ý: `portal_order_history` nay chỉ nuôi khối tóm tắt ở Dashboard
# và phép đếm KPI, không còn màn danh sách có chip nào. Chỗ tìm lại một yêu
# cầu đã chết là chip "Từ chối" của `portal_yeu_cau_cua_toi`.)
_TRANG_THAI_GHI_DE_WORKFLOW = [WF_BAO_GIA_HET_HAN, WF_KHACH_HUY, WF_TU_CHOI]


def _dieu_kien_loc_trang_thai_don(trang_thai: str) -> tuple:
    """Trả `(filters, or_filters)` khớp ĐÚNG nhánh của `_so_status_vi_full`
    ứng với nhãn `trang_thai` (một trong các chip của `Orders.vue`, KHÔNG
    kể "Tất cả"). Ném lỗi nếu nhãn lạ — không âm thầm trả về "không lọc gì"
    khi frontend gửi một chip mà backend chưa biết."""
    if trang_thai == "Đã huỷ":
        # `workflow_state == "Khách huỷ"` ĐÈ lên MỌI `status` (kể cả khi
        # `status` chưa phải "Cancelled" — huỷ qua cổng không submit/cancel
        # ERPNext, xem `_so_status_vi_full`) — OR thuần, không cần AND gì
        # thêm, nên đi qua `or_filters` (nếu nhét vào `filters` sẽ bị AND
        # nhầm với chính nó).
        return [], [["status", "=", "Cancelled"], ["workflow_state", "=", "Khách huỷ"]]

    khong_ghi_de = [["workflow_state", "not in", _TRANG_THAI_GHI_DE_WORKFLOW]]
    if trang_thai == "Chờ xác nhận":
        return khong_ghi_de + [["status", "=", "Draft"], ["per_delivered", "<=", 0]], None
    if trang_thai == "Đang xử lý":
        return khong_ghi_de + [
            ["status", "not in", ["Completed", "Closed", "Cancelled", "Draft"]],
            ["per_delivered", "<=", 0],
        ], None
    if trang_thai == "Đang giao":
        return khong_ghi_de + [
            ["status", "not in", ["Completed", "Closed", "Cancelled"]],
            ["per_delivered", ">", 0],
        ], None
    if trang_thai == "Hoàn thành":
        return khong_ghi_de + [["status", "=", "Completed"]], None
    frappe.throw(f"Trạng thái lọc không hợp lệ: {trang_thai}")


def _pham_vi_filters() -> list:
    """`pham_vi_don()` (dict `{"custom_khoa_phong": ...}` hoặc `{}`) đổi
    sang khuôn `filters` kiểu LIST mà `frappe.get_list` trên `Sales Order`
    đang dùng ở file này (`_dieu_kien_loc_trang_thai_don` trả cùng khuôn) —
    một hàm chuyển khuôn DÙNG CHUNG, không phải mỗi endpoint tự viết
    `["custom_khoa_phong", "=", ...]` một kiểu riêng.

    Nuôi `portal_order_history`/`_dem_don_theo_trang_thai` (nên cả `portal_
    dashboard_kpi`) — HAI endpoint traffic cao nhất của cổng.

    SỬA (fix-wave 2026-08-18, V2 — Important): bản trước xây filter tham
    chiếu THẲNG `custom_khoa_phong` mà KHÔNG qua `_cot_khoa_phong_ton_tai()`
    — khác với `_ten_don_trong_pham_vi()`/`dam_bao_xem_duoc()` (đã có lưới
    từ Vòng sửa 3). Kết quả CUỐI CÙNG của `frappe.get_list` vẫn an toàn
    trên site test hôm nay nhờ tầng hook (`permissions.sales_query`) CŨNG
    chặn — nhưng đó là hai lớp AND lại che mất khoảng hở của nhau, không
    phải bằng chứng lớp này tự an toàn: filter do hàm này sinh ra bị AND
    thẳng vào WHERE cùng điều kiện hook, và MariaDB phải phân giải tên cột
    `custom_khoa_phong` lúc PARSE — không có short-circuit theo giá trị
    runtime của vế còn lại. Trên một site CHƯA chạy patch (cột thật sự
    không tồn tại), câu đó vẫn ném 1054 thô bất kể hook có trả `"1=0"` hay
    không. Thiếu cột thì FAIL-CLOSED (một filter không khớp bản ghi nào,
    cùng sentinel `__khong_don_nao__` mà `_loc_qua_don_cha` đã dùng), KHÔNG
    được để lỗi CSDL thô lọt ra."""
    pham_vi = pham_vi_don()
    if not pham_vi:
        return []
    if not _cot_khoa_phong_ton_tai():
        return [["name", "in", ["__khong_don_nao__"]]]
    return [["custom_khoa_phong", "=", v] for v in pham_vi.values()]


@frappe.whitelist()
def portal_order_history(limit=20, start=0, trang_thai=None) -> dict:
    """Brief 2026-08-15 (phân trang) — hình dạng trả về ĐỔI từ list sang
    `{"rows": [...], "tong": N}` (khuôn `portal_catalog_ban_le`), LUÔN
    LUÔN — endpoint này không nuôi dropdown nào (khác ba endpoint kiêm-
    hai-vai của api/kho.py), chỉ nguồn cho đúng màn Orders.vue + preview ở
    Dashboard.vue. Đã cập nhật MỌI caller (Dashboard.vue, test_e2e_flow.py,
    test_e6_mua_le.py, test_tracking.py) sang đọc `.rows`.

    `trang_thai` (brief 2026-08-16, vá hồi quy) — nhãn tiếng Việt của MỘT
    chip lọc (Orders.vue `FILTERS`), lọc PHÍA SERVER qua
    `_dieu_kien_loc_trang_thai_don` thay vì client tự lọc mảng đã tải.
    `None`/rỗng = không lọc, giữ NGUYÊN hành vi cũ cho mọi caller không
    truyền tham số này.

    Đếm `tong` qua `frappe.get_list` (không phải `frappe.db.count`/
    `frappe.get_all`) — Sales Order được scoping theo khách hàng qua
    `permission_query_conditions` (hooks.py), `get_all`/`db.count` BỎ QUA
    tầng đó và sẽ đếm lẫn đơn của khách khác. `frappe.db.count` cũng KHÔNG
    nhận `or_filters` (cần cho nhánh "Đã huỷ" ở trên) — `get_list` nhận cả
    hai, và vẫn tôn trọng scoping.
    """
    filters, or_filters = [], None
    if trang_thai:
        filters, or_filters = _dieu_kien_loc_trang_thai_don(trang_thai)
    # Bước 8 — Nhân viên khoa chỉ thấy đơn của khoa mình; Quản lý
    # (`pham_vi_don() == {}`) không bị lọc thêm gì ở đây.
    filters = filters + _pham_vi_filters()

    tong = frappe.get_list(
        "Sales Order", filters=filters, or_filters=or_filters,
        fields=["count(name) as tong"],
    )[0].tong
    rows = frappe.get_list(
        "Sales Order",
        filters=filters, or_filters=or_filters,
        # review (Phần C báo thiếu) — custom_loai_don/workflow_state/
        # custom_yeu_cau_goc: danh sách đơn không phân biệt được đơn "Mua
        # lẻ" với "Theo HĐNT" (badge/icon giỏ 2 ngăn), và không biết đơn nào
        # đang "Chờ khách đồng ý" để hiện banner ngay trên danh sách thay vì
        # bắt khách mở từng đơn.
        fields=["name", "transaction_date", "grand_total", "status", "per_delivered",
                "custom_loai_don", "workflow_state", "custom_yeu_cau_goc",
                "custom_ma_tra_cuu"],
        # tiebreak `name` — `transaction_date`/`creation` không đủ duy
        # nhất giữa hai trang (brief 2026-08-15).
        order_by="transaction_date desc, creation desc, name desc",
        limit_page_length=int(limit), limit_start=int(start),
    )
    for r in rows:
        r["status_vi"] = _so_status_vi_full(r.pop("status"), r.get("per_delivered"), r.get("workflow_state"))
        # Đổi tên khoá `custom_loai_don` -> `loai_don`: KHÔNG rò tiền tố nội
        # bộ `custom_` của Frappe ra response công khai, và khớp đúng tên
        # khoá `portal_order_track` đã dùng cho CÙNG khái niệm — hai endpoint
        # trả hai tên khác nhau cho một field là bẫy tiếp theo đang chờ xảy
        # ra (client đọc đúng ở màn này, sai ở màn kia).
        r["loai_don"] = r.pop("custom_loai_don") or "Theo HĐNT"
        r["yeu_cau_goc"] = r.pop("custom_yeu_cau_goc") or ""
        # Task 6, QĐ-A4 — mã của khách (`DXA-HUYETHOC-260819-01`), CẠNH
        # `name` (SAL-ORD-*, mã hệ thống), không THAY nó: khách đọc mã của
        # họ, Miyano đối chiếu bằng SAL-ORD-*. Đơn CŨ chưa từng đi qua một
        # phiếu đề xuất để trống — hợp lệ, không phải lỗi.
        r["ma_tra_cuu"] = r.pop("custom_ma_tra_cuu") or ""
    return {"rows": rows, "tong": tong}


# ---- Task 11 (QĐ-G11) — MỘT danh sách, MỘT dòng đời ---------------------
#
# Trước bản này một yêu cầu của khoa nằm ở "Đề xuất mua" khi còn là phiếu
# rồi NHẢY sang "Đơn hàng của tôi" sau khi quản lý duyệt. Để tìm lại yêu
# cầu của chính mình, nhân viên phải biết trước nó đang ở giai đoạn NỘI BỘ
# nào — tức phải học sơ đồ kiến trúc của hệ thống.
#
# `giai_doan` là dòng đời DUY NHẤT mà người dùng nhìn thấy. Nó KHÔNG thay
# hai từ điển trạng thái đang có (`Portal De Xuat Mua.trang_thai` và
# `_so_status_vi_full`) — nó là một lớp THÔ HƠN phủ lên cả hai, đủ để trả
# lời đúng câu người dùng hỏi ("yêu cầu của tôi tới đâu rồi?"). Nhãn chi
# tiết của đơn vẫn đi kèm ở `trang_thai_don` để màn danh sách không nuốt
# mất tín hiệu "đang chờ CHÍNH BẠN đồng ý".
#
# Ba `WF_*` mà câu SQL bên dưới dùng khai ở TRÊN `_so_status_vi_full` — một
# nguồn duy nhất cho cả hàm suy nhãn chi tiết, danh sách trạng thái ghi đè,
# và khối CASE này. Ba bản sao chuỗi là đúng cách `Từ chối` lọt lưới lần
# đầu: nó được đặc biệt hoá ở cấp phiếu mà quên ở cấp đơn.
GIAI_DOAN_NHAP = "Nháp"
GIAI_DOAN_CHO_DUYET = "Chờ duyệt"
GIAI_DOAN_DA_DUYET = "Đã duyệt"
GIAI_DOAN_CHO_BAO_GIA = "Chờ báo giá"
GIAI_DOAN_DA_GIAO = "Đã giao"
GIAI_DOAN_TU_CHOI = "Từ chối"
GIAI_DOAN_DA_HUY = "Đã huỷ"

# Năm giai đoạn của QĐ-G11 + HAI ngõ cụt. Hai ngõ cụt KHÔNG phải phần thừa:
# chúng là trạng thái THẬT mà chính người dùng đưa yêu cầu của mình vào
# (bấm Huỷ, hoặc bị quản lý từ chối), và người vừa làm việc đó là người đi
# tìm lại nó ngay sau đó — đúng bài học "Việc (d)" của `DeXuatList.vue`.
GIAI_DOAN_HOP_LE = (
    GIAI_DOAN_NHAP, GIAI_DOAN_CHO_DUYET, GIAI_DOAN_DA_DUYET,
    GIAI_DOAN_CHO_BAO_GIA, GIAI_DOAN_DA_GIAO,
    GIAI_DOAN_TU_CHOI, GIAI_DOAN_DA_HUY,
)


def _sql_giai_doan(tt: str, so: str) -> str:
    """Biểu thức SQL suy `giai_doan`. `tt` là cột trạng thái của PHIẾU
    (hoặc `null` cho nhánh đơn-không-qua-đề-xuất), `so` là alias bảng
    `tabSales Order`.

    ĐỊNH NGHĨA MỘT LẦN, dùng cho CẢ lọc, CẢ đếm `tong`, CẢ hiển thị — nếu
    lọc ở SQL còn nhãn suy ở Python thì hai vế sẽ trôi khỏi nhau, đúng lỗi
    `_so_status_vi`/`_so_status_vi_full` đã phải gộp lại một lần rồi.

    Thứ tự nhánh là CÓ CHỦ Ý: trạng thái PHIẾU thắng trước. Một phiếu đang
    "Chờ duyệt sửa" đã có đơn đứng sau, nhưng thứ nó đang CHỜ là quản lý,
    không phải Miyano — hiện "Đã duyệt" ở đó là nói sai ai đang giữ việc.

    HAI ngõ cụt được xét ở CẢ HAI cấp, không riêng cấp phiếu (review vòng 1,
    Important): `Từ chối` là state THẬT của Sales Order (`setup/
    install_workflow.py` — Sales User bấm từ "Chờ Miyano xác nhận"), và
    trước bản vá nó rơi qua hết mọi nhánh vào `else` → một đơn Miyano đã
    huỷ đọc ra "Đã duyệt", khoa chờ vô hạn. Một ngõ cụt không tìm lại được
    thì hai giai đoạn ngõ cụt của QĐ-G11 trở thành trang trí.

    Ruling P42 — "Đã giao" đòi `per_delivered >= 100`, KHÔNG phải `> 0`.
    Giao 25% mà báo "Đã giao" là sai với khoa đang chờ nốt 75%, và nó cãi
    nhau với nhãn phụ "Đang giao" đứng ngay cạnh trên CÙNG một dòng. Không
    thêm giai đoạn thứ sáu (QĐ-G11 chốt năm) — nhãn phụ và thanh tiến độ
    đã nói đủ phần còn lại; đổi lại, đơn giao gần đủ nằm ở "Đã duyệt" lâu
    hơn, chấp nhận được.

    "Chờ báo giá" = đơn đang mắc ở vòng BÁO GIÁ (`Chờ khách đồng ý` — báo
    giá đã ra, chờ khách chốt; `Báo giá hết hạn` — chốt muộn, phải xin lại
    giá). Đây là hai trạng thái quan sát được DUY NHẤT giữa lúc duyệt và
    lúc giao hàng, nên chip này TỚI ĐƯỢC chứ không phải một chip luôn rỗng.
    `null` trên `{tt}` (nhánh đơn) làm mọi phép so sánh trạng thái phiếu ra
    NULL — falsy trong SQL — nên nhánh đó rơi thẳng xuống các luật đơn hàng
    mà không cần một biểu thức riêng.
    """
    return f"""case
        when {tt} = '{TRANG_THAI_NHAP}' then '{GIAI_DOAN_NHAP}'
        when {tt} in ('{TRANG_THAI_CHO_DUYET}', '{TRANG_THAI_CHO_DUYET_SUA}')
            then '{GIAI_DOAN_CHO_DUYET}'
        when {tt} = '{TRANG_THAI_TU_CHOI}' then '{GIAI_DOAN_TU_CHOI}'
        when {tt} = '{TRANG_THAI_DA_HUY}' then '{GIAI_DOAN_DA_HUY}'
        when {so}.name is null then '{GIAI_DOAN_DA_DUYET}'
        when {so}.docstatus = 2 or {so}.status = 'Cancelled'
             or {so}.workflow_state = '{WF_KHACH_HUY}'
            then '{GIAI_DOAN_DA_HUY}'
        when {so}.workflow_state = '{WF_TU_CHOI}' then '{GIAI_DOAN_TU_CHOI}'
        when {so}.status in ('Completed', 'Closed') or {so}.per_delivered >= 100
            then '{GIAI_DOAN_DA_GIAO}'
        when {so}.workflow_state in ('{TRANG_THAI_CHO_KHACH}', '{WF_BAO_GIA_HET_HAN}')
            then '{GIAI_DOAN_CHO_BAO_GIA}'
        else '{GIAI_DOAN_DA_DUYET}'
    end"""


@frappe.whitelist()
def portal_yeu_cau_cua_toi(limit=20, start=0, giai_doan=None) -> dict:
    """QĐ-G11 — danh sách HỢP NHẤT phiếu đề xuất + đơn hàng, MỘT dòng cho
    mỗi yêu cầu, ở bất kỳ giai đoạn nào của dòng đời.

    Rào cản kỹ thuật của việc gộp đã tự mất từ Task 9: đơn hàng mang thẳng
    mã đề xuất, và phiếu giữ `sales_order` trỏ sang đơn — trên CẢ HAI đường
    sinh đơn (`de_xuat_duyet.duyet_va_tao_don` cho luồng duyệt, và
    `_dam_bao_phieu_tu_duyet` cho giỏ hàng quản lý). Gộp vì thế là một phép
    NOT EXISTS trên `sales_order`, không phải một phép khớp mã bằng tay.

    KHÔNG dùng `frappe.get_list`: role `Customer` có ZERO DocPerm trên
    `Portal De Xuat Mua`, nên `get_list` ném `PermissionError` cho MỌI
    Website User TRƯỚC KHI hook phạm vi kịp chạy (xem docstring
    `api/de_xuat.py`). Đường sống là hàm này, và nó phải TỰ hỏi đúng chốt
    phạm vi mà tầng hook hỏi — `get_portal_member()` cho trục khách hàng,
    `pham_vi_don()` cho trục khoa. Hệ quả: điều kiện `permission_query_
    conditions` (`permissions.sales_query`) KHÔNG tự áp lên SQL thô ở đây,
    nên nhánh đơn hàng phải mang bộ lọc khoa của chính nó — đó là lý do
    `dk_don` tồn tại thay vì tin vào tầng hook.

    Cắt trang TRONG SQL (`limit`/`offset` trên truy vấn đã gộp), và `tong`
    đếm SAU khi gộp + SAU khi lọc: đếm trước khi gộp thì phiếu-đã-thành-đơn
    bị tính hai lần, trang cuối rỗng, và khách thấy một con số không khớp
    số dòng đếm được. Lọc `giai_doan` cũng ở SQL, không ở client — lọc trên
    ĐÚNG MỘT trang đã tải chính là hồi quy đã phải vá cho `Orders.vue`
    (brief 2026-08-16).

    "Duyệt" (`/duyet`) KHÔNG gộp vào đây: đó là HÀNG CHỜ VIỆC của quản lý,
    khác mục đích với *danh sách của tôi*.
    """
    if giai_doan and giai_doan not in GIAI_DOAN_HOP_LE:
        frappe.throw(
            f"Giai đoạn không hợp lệ: {giai_doan}", frappe.ValidationError
        )

    tv = get_portal_member()
    tham_so = {"kh": tv.customer}
    khoa = pham_vi_don().get("custom_khoa_phong")

    dk_phieu = "p.customer = %(kh)s"
    dk_don = "so.customer = %(kh)s"
    if khoa:
        tham_so["khoa"] = khoa
        dk_phieu += " and p.khoa_phong = %(khoa)s"
        dk_don += " and so.custom_khoa_phong = %(khoa)s"

    # Lưới an toàn lúc triển khai, cùng nguồn kiểm tra với
    # `_pham_vi_filters()`/`permissions._khoa_query_condition`: trên một
    # site CHƯA chạy patch v1_23, cột `Sales Order.custom_khoa_phong` không
    # tồn tại và MariaDB ném 1054 ngay lúc PARSE — không có short-circuit
    # theo giá trị runtime. Thiếu cột thì nhánh ĐƠN HÀNG bị bỏ hẳn với nhân
    # viên khoa (fail-closed: thà câm còn hơn rò đơn của mọi khoa kèm tổng
    # tiền). Nhánh PHIẾU không phụ thuộc cột custom nào nên vẫn tới đúng
    # người — câm đúng chỗ, không câm cả màn.
    co_cot_khoa = _cot_khoa_phong_ton_tai()
    cot_khoa_don = "so.custom_khoa_phong" if co_cot_khoa else "null"
    co_nhanh_don = co_cot_khoa or not khoa

    nhanh_phieu = f"""
        select 'phieu' as nguon, p.name as de_xuat, p.sales_order as sales_order,
               -- `ma` là MÃ CỦA KHÁCH, KHÔNG rơi về `p.name`: tên nội bộ
               -- (`DXM-2026-000xx`, naming_series) là mã hệ thống, không
               -- phải thứ khoa đọc. Phiếu Nháp chưa có mã (mã cấp lúc Gửi
               -- duyệt) → rỗng, và tầng hiển thị nói thẳng "(chưa gửi
               -- duyệt)" — đúng cách `DeXuatList.vue` đã làm trước khi gộp.
               coalesce(nullif(p.ma_de_xuat, ''), '') as ma,
               p.khoa_phong as khoa_phong, p.creation as thoi_diem,
               p.trang_thai as trang_thai_phieu, p.owner as owner,
               so.status as so_status, so.per_delivered as per_delivered,
               so.workflow_state as workflow_state, so.grand_total as grand_total,
               p.name as khoa_sap_xep,
               {_sql_giai_doan("p.trang_thai", "so")} as giai_doan
        from `tabPortal De Xuat Mua` p
        left join `tabSales Order` so on so.name = p.sales_order
        where {dk_phieu}
    """
    # Đơn KHÔNG đứng sau phiếu nào — đơn cũ (có trước luồng duyệt) và đơn
    # của sáu tài khoản quản lý đang chạy thật. `not exists` trên
    # `sales_order` là ĐÚNG mối nối mã thật ghi, và nó cũng nuốt luôn ca
    # `custom_de_xuat` trỏ vào một phiếu đã bị xoá.
    nhanh_don = f"""
        select 'don', null, so.name, so.name,
               {cot_khoa_don}, so.creation, null, null,
               so.status, so.per_delivered, so.workflow_state, so.grand_total,
               so.name, {_sql_giai_doan("null", "so")}
        from `tabSales Order` so
        where {dk_don}
          and not exists (
              select 1 from `tabPortal De Xuat Mua` p2
              where p2.customer = %(kh)s and p2.sales_order = so.name
          )
    """
    trong = nhanh_phieu + (f" union all {nhanh_don}" if co_nhanh_don else "")

    dk_giai_doan = ""
    if giai_doan:
        tham_so["gd"] = giai_doan
        dk_giai_doan = " where t.giai_doan = %(gd)s"

    tong = frappe.db.sql(
        f"select count(*) from ({trong}) t{dk_giai_doan}", tham_so
    )[0][0]
    rows = frappe.db.sql(
        f"""select * from ({trong}) t{dk_giai_doan}
            order by t.thoi_diem desc, t.khoa_sap_xep desc
            limit %(limit)s offset %(start)s""",
        {**tham_so, "limit": int(limit), "start": int(start)},
        as_dict=True,
    )
    for r in rows:
        so_status = r.pop("so_status")
        workflow_state = r.pop("workflow_state")
        r["sales_order"] = r.get("sales_order") or ""
        r["de_xuat"] = r.get("de_xuat") or ""
        r["khoa_phong"] = r.get("khoa_phong") or ""
        r["trang_thai_phieu"] = r.get("trang_thai_phieu") or ""
        # `owner` nuôi đúng một việc ở màn danh sách: có hiện nút "Sửa" cho
        # một phiếu Nháp hay không (`de_xuat_luu_nhap` cho owner HOẶC quản
        # lý). Cùng điều kiện `DeXuatList.vue::coTheSuaNhap` đã dùng —
        # client đoán khác server thì khách gõ xong mới ăn "Phiếu này không
        # phải của bạn" và mất sạch công sửa.
        r["owner"] = r.get("owner") or ""
        # Nhãn CHI TIẾT của đơn — dùng lại ĐÚNG hàm mà `portal_order_
        # history`/`portal_order_track` dùng, không viết bản thứ ba.
        r["trang_thai_don"] = _so_status_vi_full(
            so_status, r.get("per_delivered"), workflow_state
        ) if r["sales_order"] else ""
        r["per_delivered"] = float(r.get("per_delivered") or 0)
        r["grand_total"] = float(r.get("grand_total") or 0)
    return {"rows": rows, "tong": int(tong)}


def _dem_don_theo_trang_thai(trang_thai: str) -> int:
    filters, or_filters = _dieu_kien_loc_trang_thai_don(trang_thai)
    filters = filters + _pham_vi_filters()
    return frappe.get_list(
        "Sales Order", filters=filters, or_filters=or_filters,
        fields=["count(name) as n"],
    )[0].n


@frappe.whitelist()
def portal_dashboard_kpi() -> dict:
    """Brief 2026-08-16 (vá hồi quy phân trang) — Dashboard.vue trước đây
    suy 3 ô KPI (đơn chờ xác nhận/đang giao, hoá đơn chưa thanh toán) từ
    DANH SÁCH ĐÃ PHÂN TRANG (`portal_order_history`/`portal_invoices`, limit
    mặc định 10/20). Với `limit=10`, một khách có 15 đơn "Chờ xác nhận" thật
    chỉ thấy ô hiện một con số nhỏ hơn — SAI trên đúng màn đầu tiên khách
    nhìn thấy mỗi lần đăng nhập, hỏng niềm tin vào toàn bộ số liệu của cổng.

    Ba con số ở đây LUÔN đếm trên TOÀN BỘ dữ liệu của khách (không limit/
    start), độc lập với cỡ trang khách đang chọn ở Orders.vue/Invoices.vue.
    "Tổng công nợ" KHÔNG có ở đây — `portal_me().outstanding` đã là một truy
    vấn tổng hợp riêng từ trước, không suy từ danh sách phân trang, nên
    không phải hồi quy của đợt này.

    Đếm qua `frappe.get_list` (không phải `get_all`/`db.count`) — Sales
    Order/Sales Invoice được scoping theo khách hàng qua
    `permission_query_conditions` (hooks.py); `get_all`/`db.count` bỏ qua
    tầng đó và sẽ đếm lẫn dữ liệu khách khác.
    """
    return {
        "don_cho_xac_nhan": _dem_don_theo_trang_thai("Chờ xác nhận"),
        "don_dang_giao": _dem_don_theo_trang_thai("Đang giao"),
        "hoa_don_chua_thanh_toan": frappe.get_list(
            "Sales Invoice",
            filters=[["outstanding_amount", ">", 0]]
            + _loc_qua_don_cha("Sales Invoice Item", "sales_order"),
            fields=["count(distinct `tabSales Invoice`.name) as n"],
        )[0].n,
    }


def _kiem_hang_tom_tat(r) -> dict | None:
    """Tóm tắt biên bản kiểm hàng cho một đợt giao, hoặc None nếu khách chưa
    lập. Client dùng để chọn giữa nút "Kiểm hàng" và một badge trạng thái."""
    if not r:
        return None
    return {
        "name": r.name,
        "trang_thai": r.trang_thai,
        "co_hang_hong": bool(r.co_hang_hong),
        "da_gui": int(r.docstatus) == 1,
    }


def _hoa_don_cua_don(order: str) -> list:
    """Hoá đơn phát sinh từ CHÍNH đơn hàng này.

    Khoảng trống đã nêu trong đối chiếu 2026-08-16: cổng có mốc "Hoá đơn"
    bật/tắt và một trang Hoá đơn TOÀN CỤC, nhưng không có đường nào từ một
    đơn tới hoá đơn của nó — khách phải tự dò. Nối qua `Sales Invoice Item.
    sales_order`, đúng cách ERPNext ghi liên kết đó.

    `docstatus < 2` — hoá đơn đã huỷ không còn là hoá đơn của đơn này.
    KHÔNG đụng `portal_invoices` (hình dạng trả về của nó là hợp đồng API đã
    có người dùng).
    """
    ten = frappe.get_all(
        "Sales Invoice Item",
        filters={"sales_order": order, "docstatus": ["<", 2]},
        pluck="parent",
    )
    ten = list(dict.fromkeys(ten))
    if not ten:
        return []
    rows = frappe.get_all(
        "Sales Invoice",
        filters={"name": ["in", ten], "docstatus": ["<", 2]},
        fields=["name", "posting_date", "due_date", "status",
                "grand_total", "outstanding_amount"],
        order_by="posting_date asc",
    )
    return [
        {
            "name": r.name,
            "ngay": r.posting_date,
            "han_thanh_toan": r.due_date,
            "trang_thai": r.status,
            "tong_tien": float(r.grand_total or 0),
            "con_no": float(r.outstanding_amount or 0),
        }
        for r in rows
    ]


@frappe.whitelist()
def portal_order_track(order) -> dict:
    # Bước 8 — chặn theo KHOA trước tiên: `dam_bao_xem_duoc` tự no-op cho
    # Quản lý (pham_vi_don() == {}) và ném CÙNG một thông báo cho "đơn không
    # có thật" lẫn "đơn của khoa khác" (không có gì để `frappe.get_doc`
    # đụng vào rồi mới ném DoesNotExistError với văn xuôi khác).
    dam_bao_xem_duoc("Sales Order", order)
    so = frappe.get_doc("Sales Order", order)
    # frappe.get_doc does not auto-check permissions on load; check_permission()
    # is what actually invokes the has_permission hook (Task 5) that scopes
    # this to the caller's own customer — kiểm KHÁCH HÀNG, KHÔNG thay cho
    # kiểm khoa phòng ở trên.
    so.check_permission("read")
    delivered = (so.per_delivered or 0) > 0
    billed = (so.per_billed or 0) > 0
    # "Soạn hàng" (order-preparation): done once the goods have been picked
    # for this SO (a Pick List exists) or delivery has already started.
    preparing_done = bool(frappe.db.exists("Pick List Item", {"sales_order": order})) or delivered
    milestones = [
        {"key": "ordered", "label": "Đặt hàng", "done": True},
        {"key": "confirmed", "label": "Xác nhận", "done": so.docstatus == 1},
        {"key": "preparing", "label": "Soạn hàng", "done": preparing_done},
        {"key": "delivering", "label": "Giao hàng", "done": delivered},
        {"key": "invoiced", "label": "Hoá đơn", "done": billed},
    ]

    # Delivery Notes fulfilling this Sales Order. Delivery Note Item carries
    # against_sales_order; distinct parents give the batches ("đợt giao"). The
    # SO was already permission-checked above, so its own DNs are in scope.
    # order_by=creation: so "Đợt n" (array index, see OrderDetail.vue) reads
    # in the order the DNs actually happened, not arbitrary row order.
    #
    # `docstatus = 1` và `is_return = 0` — hai vế BẮT BUỘC, và bản trước
    # thiếu CẢ HAI (lỗi đo được 18/08/2026, xem
    # `docs/superpowers/specs/2026-08-17-himedic-5-yeu-cau-design.md` §2b):
    #
    #   * `docstatus < 2` cho phiếu NHÁP đi qua → khách thấy một phiếu chưa
    #     ghi sổ như một đợt ĐÃ giao (đo thật: MAT-DN-2026-00022 còn nháp vẫn
    #     hiện thành "Đợt 2" trên màn Bạch Mai).
    #   * `make_return_doc` chép nguyên `against_sales_order` sang phiếu TRẢ
    #     HÀNG, và dòng hàng của nó mang `qty` ÂM → phiếu trả hiện thành một
    #     đợt giao với phần trăm âm (đo thật: "Đợt 4: -10.0%").
    #
    # Đây là CÙNG quy ước `portal_hen_giao._da_giao_sau()` đã dùng từ trước,
    # không phải một luật mới. Cờ `is_return` nằm trên chứng từ CHA nên phải
    # nối bảng — không có lối lọc nào bằng `frappe.get_all` trên riêng bảng
    # con, đúng lý do `_da_giao_sau` cũng viết SQL tay.
    total_qty = sum(float(i.qty or 0) for i in so.items) or 0
    dn_names = [
        r[0]
        for r in frappe.db.sql(
            """select dni.parent
               from `tabDelivery Note Item` dni
               inner join `tabDelivery Note` dn on dn.name = dni.parent
               where dni.against_sales_order = %s
                 and dn.docstatus = 1
                 and ifnull(dn.is_return, 0) = 0
               group by dni.parent
               order by min(dni.creation) asc""",
            (so.name,),
        )
    ]

    # E7b — cờ "đợt giao này đã có hoá đơn nháp", MỘT truy vấn cho cả danh
    # sách (không hỏi từng phiếu trong vòng lặp bên dưới). Chỉ là CỜ; nội
    # dung đầy đủ lấy qua `portal_einvoice_nhap` khi khách bấm xem — nhét sẵn
    # dòng hàng của mọi đợt giao vào đây sẽ phình response chi tiết đơn.
    #
    # Bọc lỗi CỐ Ý, cùng nguyên tắc với khối HĐĐT ở `portal_invoices` và
    # `delivery_hook._chay_an_toan`: module HĐĐT là của team khác — nó hỏng
    # thì mất CÁI CỜ, không được mất cả trang chi tiết đơn hàng. Bọc ở đây
    # (ngoài vòng lặp) nên một lần hỏng ghi đúng MỘT log, không N log.
    try:
        dn_co_nhap = einvoice.dn_co_hoa_don_nhap(dn_names, so.customer)
    except Exception:
        frappe.log_error(title=f"HĐĐT: không kiểm được hoá đơn nháp cho đơn {so.name}")
        dn_co_nhap = set()

    # US-E3.4 — trạng thái phiếu nhập chỉ hiện khi khách CÓ kho (không dùng
    # get_portal_kho(): hàm đó ném PermissionError khi khách chưa mở kho, mà
    # phần lớn khách hàng portal KHÔNG có kho — đây không phải một tình huống
    # ngoại lệ cho endpoint này). `active: 1` khớp đúng định nghĩa "có kho"
    # mà get_portal_kho()/delivery_hook._kho_cua_khach() đã dùng ở mọi nơi
    # khác trong app — một kho đã tắt được coi như "không có kho" ở đây,
    # nhất quán với việc hook cũng ngừng tự sinh phiếu cho kho đó.
    kho = frappe.db.get_value("Customer Warehouse", {"customer": so.customer, "active": 1}, "name")
    # Biên bản kiểm hàng — MỘT truy vấn cho cả danh sách (không hỏi từng
    # phiếu trong vòng lặp bên dưới), cùng khuôn `dn_co_nhap`. KHÔNG phụ
    # thuộc `kho`: biên bản chạy cho mọi khách, kể cả khách chưa mở kho.
    bien_ban_by_dn = {}
    if dn_names:
        for r in frappe.get_all(
            "Portal Delivery Inspection",
            filters={"delivery_note": ["in", dn_names], "docstatus": ["<", 2]},
            fields=["name", "delivery_note", "docstatus", "trang_thai", "co_hang_hong"],
        ):
            bien_ban_by_dn[r.delivery_note] = r

    receipts_by_dn = {}
    if kho and dn_names:
        for r in frappe.get_all(
            "Customer Stock Receipt",
            filters={"kho": kho, "delivery_note": ["in", dn_names], "docstatus": ["<", 2]},
            fields=["name", "delivery_note", "docstatus", "co_chenh_lech", "so_dot"],
        ):
            receipts_by_dn[r.delivery_note] = r

    # `deliveries` (đã có [Hiện có]) và `dot_giao` (mới, đúng chữ ký
    # `30_API_Spec` §1.2) dựng từ CÙNG một vòng lặp/CÙNG một nguồn — hai key
    # riêng trên response, không phải `"dot_giao": deliveries` (alias thẳng
    # object sẽ dính bug nếu một bên bị sửa tại chỗ sau này) và KHÔNG PHẢI
    # hai khối UI song song: OrderDetail.vue chỉ đọc `deliveries` (đã mở
    # rộng thêm so_dot/phieu_nhap ở đó), `dot_giao` tồn tại để đúng hợp đồng
    # API cho các bên gọi khác (client tương lai, kiểm thử theo đặc tả).
    deliveries = []
    dot_giao = []
    for dn_name in dn_names:
        dn = frappe.db.get_value(
            "Delivery Note", dn_name,
            ["name", "posting_date", "status", "lr_no", "transporter_name"],
            as_dict=True,
        )
        if not dn:
            continue
        dn_qty = frappe.db.sql(
            """select sum(qty) from `tabDelivery Note Item`
               where parent=%s and against_sales_order=%s""",
            (dn_name, so.name),
        )[0][0]
        pct = round(float(dn_qty or 0) / total_qty * 100, 1) if total_qty else 0

        receipt = receipts_by_dn.get(dn_name)
        # so_dot lưu DB thành 0 khi "không xác định" (Int không nullable —
        # bàn giao Phần A), không phải "đợt 0" — trả None cho client thay vì
        # con số 0 gây hiểu lầm.
        so_dot = (receipt.so_dot or None) if receipt else None
        phieu_nhap = None
        if receipt:
            phieu_nhap = {
                "name": receipt.name,
                "trang_thai": _phieu_nhap_trang_thai_vi(int(receipt.docstatus), receipt.co_chenh_lech),
                "co_chenh_lech": bool(receipt.co_chenh_lech),
            }

        row = {
            "name": dn["name"],
            "posting_date": dn.get("posting_date"),
            "status": dn.get("status"),
            "percent": pct,
            "carrier": dn.get("transporter_name") or "",
            "awb": dn.get("lr_no") or "",
            "co_hoa_don_nhap": dn_name in dn_co_nhap,
            "kiem_hang": _kiem_hang_tom_tat(bien_ban_by_dn.get(dn_name)),
        }
        if receipt:
            row["so_dot"] = so_dot
            row["phieu_nhap"] = phieu_nhap
        deliveries.append(row)

        dot = {
            "so_dot": so_dot,
            "delivery_note": dn["name"],
            "ngay": dn.get("posting_date"),
            "phan_tram": pct,
            "van_chuyen": dn.get("transporter_name") or "",
            "awb": dn.get("lr_no") or "",
            "co_hoa_don_nhap": dn_name in dn_co_nhap,
            "kiem_hang": _kiem_hang_tom_tat(bien_ban_by_dn.get(dn_name)),
        }
        if phieu_nhap:
            dot["phieu_nhap"] = phieu_nhap
        dot_giao.append(dot)

    # US-E6.5 / `30_API_Spec` §1.2 — banner "Chờ bạn đồng ý" (F-07) cần biết
    # hạn hiệu lực để hiện "Báo giá hiệu lực đến dd/mm/yyyy"; chỉ có ý nghĩa
    # khi đơn ĐANG ở trạng thái này, các trạng thái khác trả `None`.
    #
    # review I-2(b) — `can_dong_y` KHÔNG được là `True` vô điều kiện: đơn có
    # thể vẫn còn `workflow_state == "Chờ khách đồng ý"` (job daily CHƯA kịp
    # quét) nhưng đã quá `han_hieu_luc` — client phải biết để tắt nút Đồng ý
    # ngay, không đợi đến khi khách bấm rồi mới nhận 417.
    # review I-2(c) — `han_hieu_luc`/hết hạn chỉ có ý nghĩa với đơn ĐI VÒNG
    # BÁO GIÁ (BR-R5 nằm trong QT10); đơn thuần hợp đồng ở "Chờ khách đồng ý"
    # (luồng E2 gốc) không có khái niệm hiệu lực N ngày.
    #
    # Task 6 (QĐ-G2b) — hỏi `di_vong_bao_gia()`, KHÔNG so chuỗi
    # `custom_loai_don == "Mua lẻ"` tại chỗ: từ Task 4, "Mua lẻ" nghĩa là
    # "còn dòng chưa có giá", nên so chuỗi ở đây đọc như một câu hỏi khác
    # với câu nó thật sự hỏi.
    di_bao_gia = di_vong_bao_gia(so)
    chap_nhan = None
    if so.get("workflow_state") == "Chờ khách đồng ý":
        het_han = di_bao_gia and qua_han_hieu_luc(so)
        chap_nhan = {
            "can_dong_y": not het_han,
            "han_hieu_luc": str(han_hieu_luc_bao_gia(so)) if di_bao_gia else None,
        }

    # `_so_status_vi_full` bọc đúng tình huống job daily chuyển
    # `workflow_state` sang "Báo giá hết hạn" mà `docstatus` vẫn 0 — dùng
    # CHUNG với `portal_order_history`, không viết tay điều kiện này hai lần.
    status_vi = _so_status_vi_full(so.status, so.per_delivered, so.get("workflow_state"))

    return {
        "order": so.name,
        "status_vi": status_vi,
        "order_date": so.transaction_date,
        "po_khach": so.get("custom_so_po_khach") or "",
        "hdnt": so.get("custom_hdnt") or "",
        # US-E2.2 — khách phải đọc được lý do ngay trên chi tiết đơn, không
        # phải đi tìm lại email.
        "ly_do_tu_choi": so.get("custom_ly_do_tu_choi") or "",
        # Task 6, QĐ-A4 — cùng khoá `ma_tra_cuu` với `portal_order_history`,
        # xem chú thích ở đó. Đơn cũ không có phiếu đề xuất đứng sau: rỗng.
        "ma_tra_cuu": so.get("custom_ma_tra_cuu") or "",
        # review (Phần C báo thiếu)
        "loai_don": so.get("custom_loai_don") or "Theo HĐNT",
        "workflow_state": so.get("workflow_state") or "",
        "yeu_cau_goc": so.get("custom_yeu_cau_goc") or "",
        "chap_nhan": chap_nhan,
        "milestones": milestones,
        # §3.4 — LỌC dòng giữ chỗ khỏi phía khách. Khách không gõ ra nó,
        # không đặt nó, và nó không phải hàng: để nó lọt ra cổng là phơi một
        # chi tiết kỹ thuật nội bộ ra đúng chỗ nguyên tắc nền cấm.
        "items": [
            # `name` — Việc 1 (brief 2026-08-15) — `portal_order_sua_so_luong`
            # khớp dòng payload khách gửi lên với dòng THẬT trên đơn qua
            # `item_code` (duy nhất trong MỘT đơn, xem `_xay_don_ban_le`
            # aggregate theo item_code khi tạo đơn); `name` đi kèm ở đây để
            # client có thể tham chiếu nếu cần, cùng khuôn với `dat_ngoai`
            # bên dưới (dat_ngoai không có khoá tự nhiên nào khác).
            {"name": i.name, "item_code": i.item_code,
             "item_name": i.item_name or frappe.db.get_value("Item", i.item_code, "item_name"),
             "qty": i.qty, "delivered_qty": i.delivered_qty,
             "rate": float(i.rate or 0), "uom": i.uom, "amount": float(i.amount or 0)}
            for i in so.items
            if i.item_code != ITEM_GIU_CHO
        ],
        # §3.4 — nhóm "hàng chưa có mã". `item_khop`/`da_xu_ly` để client
        # tách được dòng Miyano đã tìm ra nguồn khỏi dòng còn đang chờ.
        "dat_ngoai": [
            # `name` — Việc 1 (brief 2026-08-15): dòng đặt ngoài KHÔNG có
            # khoá nghiệp vụ tự nhiên nào khác (ten_hang/dvt có thể trùng
            # giữa hai dòng) — `portal_order_sua_so_luong` khớp payload sửa
            # số lượng theo `name` của chính child row này.
            {"name": d.name, "ten_hang": d.ten_hang, "dvt": d.dvt, "so_luong": float(d.so_luong or 0),
             "ghi_chu": d.ghi_chu or "", "da_xu_ly": bool(d.da_xu_ly),
             "item_khop": d.item_khop or ""}
            for d in (so.get("custom_dat_ngoai") or [])
        ],
        "deliveries": deliveries,
        # `30_API_Spec` §1.2 — cùng dữ liệu với `deliveries`, đúng tên field
        # đặc tả yêu cầu (xem ghi chú ngay phía trên vòng lặp).
        "dot_giao": dot_giao,
        "hoa_don": _hoa_don_cua_don(so.name),
        # Miyano hẹn lại lịch giao (2026-08-16, vai nhân viên). `None` khi
        # chưa có lời hẹn nào — client ẩn hẳn khối, không hiện một khung rỗng.
        "hen_giao": hen_giao_cua_don(so),
    }


def _ten_don_trong_pham_vi() -> list | None:
    """`None` = không giới hạn theo khoa (Quản lý). Ngược lại: danh sách tên
    `Sales Order` thuộc ĐÚNG khoa của người gọi (có thể rỗng).

    VÒNG SỬA 3 (V2, review độc lập, Important) — `frappe.get_all` bên dưới
    tham chiếu THẲNG `custom_khoa_phong`, cùng lưới an toàn với
    `dam_bao_xem_duoc` (`portal_context.py`, dùng CHUNG `_cot_khoa_phong_
    ton_tai()`, không viết lại phép kiểm cột thứ hai): Quản lý (`pham_vi`
    rỗng) không bao giờ chạm cột này — chỉ Nhân viên khoa mới cần. Thiếu
    cột thì trả `[]` (KHÔNG phải `None`) — `_loc_qua_don_cha` bên dưới coi
    `None` là "không giới hạn" (Quản lý) và một danh sách rỗng là "giới hạn
    nhưng không khớp gì" (sentinel `__khong_don_nao__`); trả nhầm `None` ở
    đây sẽ MỞ TOANG danh sách cho đúng người lẽ ra phải bị chặn."""
    pham_vi = pham_vi_don()
    if not pham_vi:
        return None
    if not _cot_khoa_phong_ton_tai():
        return []
    return frappe.get_all(
        "Sales Order", filters={"custom_khoa_phong": pham_vi["custom_khoa_phong"]},
        pluck="name",
    )


def _loc_qua_don_cha(child_doctype: str, link_field: str) -> list:
    """Filter kiểu LIST cho `frappe.get_list` trên một doctype DẪN XUẤT
    (Delivery Note/Sales Invoice) — lọc QUA ĐƠN CHA bằng cách nối bảng dòng
    (`child_doctype`), KHÔNG có field khoa phòng riêng trên chính doctype đó
    (một nguồn sự thật, xem docstring `dam_bao_xem_duoc`). `[]` (không lọc
    gì thêm) cho Quản lý; một sentinel không khớp bản ghi nào khi khoa CHƯA
    có đơn nào (danh sách `_ten_don_trong_pham_vi()` rỗng — `["in", []]`
    không đáng tin cậy trên mọi bản Frappe nên tự đóng bằng một giá trị
    không bao giờ khớp thay vì phó mặc).

    SỬA (review vòng sửa 2, C4) — mô tả trước đây ở đây SAI, và sai đúng chỗ
    nguy hiểm nhất (vị trí ranh giới an ninh thật). Bản Vòng sửa 1 bảo bộ
    lọc NÀY khoan dung hơn `_dieu_kien_khoa_qua_don_cha` (permissions.py,
    C2 — chỉ đòi "CÓ ÍT NHẤT MỘT dòng khớp khoa", không đòi "KHÔNG dòng nào
    khác khoa"), nên một Delivery Note/Sales Invoice trộn hai khoa "có thể
    XUẤT HIỆN trên danh sách rồi 403 khi mở". Điều đó ĐÚNG cho riêng hàm
    NÀY, nhưng SAI cho kết quả THẬT khách nhận được: `portal_deliveries`/
    `portal_invoices` (hai nơi DUY NHẤT gọi hàm này) gọi `frappe.get_list`
    KHÔNG `ignore_permissions=True` — nên `permission_query_conditions`
    (`delivery_query`/`invoice_query`, đã có vế khoa CHẶT từ C2) tự động
    ANDED vào CHÍNH truy vấn đó bởi framework, không phải một bước lọc
    riêng sau này. Kết quả cuối là GIAO của bộ lọc lỏng ở đây và bộ lọc
    chặt của hook — tức CHẶT (hook thắng). Danh sách khách thấy đã ĐÚNG
    NGAY từ đầu, không có khoảng hở "hiện ra rồi 403" trong thực tế.

    Bộ lọc lỏng ở ĐÂY vẫn hữu ích (thu hẹp SQL sớm, đỡ join thừa khi hook
    còn phải chạy lại chính phép join tương tự) nhưng KHÔNG PHẢI ranh giới
    an ninh — ranh giới an ninh THẬT là hook (`permissions.py`), luôn luôn.
    Ràng buộc ngầm PHẢI giữ: hai hàm gọi filter này TUYỆT ĐỐI không được
    thêm `ignore_permissions=True` — làm vậy sẽ tắt hẳn hook và biến bộ lọc
    lỏng ở đây thành tuyến phòng thủ DUY NHẤT, đúng lúc đó mô tả "khoan
    dung hơn, có thể lộ tên chứng từ" ở trên mới thành sự thật. `test_
    portal_deliveries_khop_chinh_xac_voi_frappe_get_list_qua_hook`/`test_
    portal_invoices_...` (`tests/test_cach_ly_khoa_phong.py`, C6) ghim
    đúng bất biến "kết quả endpoint == kết quả frappe.get_list thô qua
    hook" — đỏ ngay nếu ai đó phá ràng buộc này."""
    so_names = _ten_don_trong_pham_vi()
    if so_names is None:
        return []
    return [[child_doctype, link_field, "in", so_names or ["__khong_don_nao__"]]]


@frappe.whitelist()
def portal_deliveries(limit=20, start=0) -> list:
    filters = _loc_qua_don_cha("Delivery Note Item", "against_sales_order")
    return frappe.get_list(
        "Delivery Note",
        filters=filters,
        # `distinct` — một phiếu giao có THỂ có nhiều dòng cùng trỏ về một
        # đơn (nhiều mặt hàng); không có nó, phép nối bảng dòng ở trên nhân
        # bản CHÍNH phiếu giao đó trên danh sách, hỏng cả số lượng lẫn phân
        # trang một cách im lặng.
        distinct=True,
        fields=["name", "posting_date", "status"],
        order_by="posting_date desc",
        limit_page_length=int(limit), limit_start=int(start),
    )


@frappe.whitelist()
def portal_invoices(limit=20, start=0) -> dict:
    """Brief 2026-08-15 (phân trang) — hình dạng trả về ĐỔI từ list sang
    `{"rows": [...], "tong": N, "qua_han_thanh_toan": ..., "sap_den_han_
    so_luong": ...}`, LUÔN LUÔN (endpoint này không nuôi dropdown nào). Đã
    cập nhật MỌI caller (Dashboard.vue, Invoices.vue, test_portal_read.py,
    test_e7_hddt.py) sang đọc `.rows`.

    `qua_han_thanh_toan`/`sap_den_han_so_luong` (bản trước Invoices.vue tự
    tính từ TOÀN BỘ `invoices.value` client-side) giờ tính Ở SERVER trên
    TOÀN BỘ hoá đơn còn nợ của khách — không phải chỉ trang đang xem, nếu
    không hai con số này sẽ đổi theo trang khách đang lật, một hồi quy im
    lặng đúng kiểu brief cảnh báo. Cùng công thức `daysUntil()`
    (frontend/src/format.js): quá hạn = hạn TT đã qua hôm nay; sắp đến hạn
    = còn 0-7 ngày VÀ còn nợ.
    """
    # Bước 8 — CẢ BA truy vấn dưới đây phải cùng một bộ lọc khoa phòng: đây
    # là đúng bẫy "hồi quy im lặng" mà docstring hàm này đang cảnh báo (phân
    # trang) áp cho một trục khác — lọc mỗi `rows` mà bỏ sót `tong`/
    # `qua_han_thanh_toan`/`sap_den_han_so_luong` thì nhân viên khoa vẫn đọc
    # được TỔNG CÔNG NỢ TOÀN BỆNH VIỆN ngay trên khối KPI, dữ liệu vẫn rò dù
    # danh sách chi tiết đã lọc đúng.
    pham_vi_hd = _loc_qua_don_cha("Sales Invoice Item", "sales_order")

    tong = frappe.get_list(
        "Sales Invoice", filters=pham_vi_hd,
        # `count(distinct name)`, KHÔNG `distinct=True` + `count(name)`: một
        # hoá đơn khớp NHIỀU dòng của cùng một đơn (nhiều mặt hàng) sẽ bị
        # phép nối bảng dòng ở `_loc_qua_don_cha` đếm lặp nếu chỉ đếm `name`.
        fields=["count(distinct `tabSales Invoice`.name) as tong"],
    )[0].tong

    hom_nay = frappe.utils.nowdate()
    qua_han_thanh_toan = 0.0
    sap_den_han_so_luong = 0
    for r in frappe.get_list(
        "Sales Invoice", filters=[["outstanding_amount", ">", 0]] + pham_vi_hd,
        distinct=True,
        fields=["due_date", "outstanding_amount"],
    ):
        if not r.due_date:
            continue
        so_ngay = frappe.utils.date_diff(r.due_date, hom_nay)
        if so_ngay < 0:
            qua_han_thanh_toan += float(r.outstanding_amount or 0)
        elif so_ngay <= 7:
            sap_den_han_so_luong += 1

    rows = frappe.get_list(
        "Sales Invoice",
        filters=pham_vi_hd,
        distinct=True,
        # `customer` chỉ dùng NỘI BỘ để đối chiếu sở hữu bản ghi HĐĐT
        # (`einvoice.block_for` — F-08/E7), bị `pop` trước khi trả về, KHÔNG
        # phải một field mới lộ ra response.
        fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount",
                "status", "customer"],
        # tiebreak `name`.
        order_by="posting_date desc, name desc",
        limit_page_length=int(limit), limit_start=int(start),
    )
    for r in rows:
        r["status_vi"] = _invoice_status_vi(r.pop("status"))
        # E7/F-08 — khối HĐĐT đi kèm NGAY trong danh sách (đúng hành vi bản
        # mẫu: `toggleEinv()` chỉ ẩn/hiện một dòng đã có sẵn dữ liệu, không
        # gọi thêm API khi khách bấm xổ dòng). `block_for` tự đối chiếu
        # `fei.customer == r["customer"]` — một sai sót dữ liệu ở module HĐĐT
        # (kế toán gõ nhầm `sales_invoice` sang hoá đơn của khách khác) không
        # lọt ra cổng dù `Sales Invoice` này đọc được là đúng chủ.
        #
        # Bọc lỗi CỐ Ý (cùng nguyên tắc `delivery_hook._chay_an_toan`: "giao
        # hàng của Miyano không được phụ thuộc kho khách" — ở đây là "danh
        # sách hoá đơn + công nợ không được phụ thuộc module HĐĐT của team
        # khác"). Module đó đổi tên field/cấu trúc không được phép biến MẤT
        # cả danh sách hoá đơn (NL-12.1: công nợ vẫn hiển thị bình thường dù
        # HĐĐT có chuyện gì). KHÔNG bọc kiểu này ở `portal_einvoice_download`
        # — đó là hành động khách chủ động bấm, lỗi phải lộ ra chứ không được
        # nuốt thành "im lặng không tải được gì".
        customer = r.pop("customer")
        try:
            r["einvoice"] = einvoice.block_for(r["name"], customer)
        except Exception:
            frappe.log_error(title=f"HĐĐT: không dựng được khối cho {r['name']}")
            r["einvoice"] = einvoice.khoi_mac_dinh()
    return {
        "rows": rows, "tong": tong,
        "qua_han_thanh_toan": qua_han_thanh_toan,
        "sap_den_han_so_luong": sap_den_han_so_luong,
    }


def _ho_so_cua_hoa_don(invoice) -> tuple:
    """Kiểm sở hữu Sales Invoice qua phiên, rồi trả `(si, ho_so)` — `ho_so`
    là TOÀN BỘ `Fast EInvoice Document` khớp hoá đơn này, đã lọc đúng
    `customer` (review round 1, C-1: một Sales Invoice có thể khớp NHIỀU bản
    ghi — bản gốc + bản điều chỉnh/thay thế + bản lập lại sau huỷ nội bộ —
    không được chỉ lấy MỘT). Dùng chung cho cả hai endpoint bên dưới, tránh
    hai nơi tự viết lại khối kiểm quyền."""
    dam_bao_xem_duoc("Sales Invoice", invoice)
    customer = get_portal_customer()
    si = frappe.get_doc("Sales Invoice", invoice)
    # `frappe.get_doc` KHÔNG tự kiểm quyền — `check_permission` là nơi hook
    # `has_permission` (miyano_portal.permissions.generic_has_permission)
    # thực sự chạy.
    si.check_permission("read")
    if si.customer != customer:
        raise frappe.PermissionError("Hoá đơn không thuộc đơn vị của bạn.")
    ho_so = [f for f in einvoice.resolve_all(invoice) if f.customer == si.customer]
    return si, ho_so


def _dn_cua_khach(delivery_note):
    """Kiểm sở hữu MỘT phiếu giao qua phiên — khuôn giống `_ho_so_cua_hoa_don`
    (Sales Invoice). `frappe.get_doc` KHÔNG tự kiểm quyền: `check_permission`
    mới là nơi hook `has_permission` (`permissions.generic_has_permission`)
    thật sự chạy, và chốt `dn.customer` là lớp thứ hai không phụ thuộc cấu
    hình DocPerm/User Permission."""
    dam_bao_xem_duoc("Delivery Note", delivery_note)
    customer = get_portal_customer()
    dn = frappe.get_doc("Delivery Note", delivery_note)
    dn.check_permission("read")
    if dn.customer != customer:
        raise frappe.PermissionError("Phiếu giao không thuộc đơn vị của bạn.")
    return dn


def _phuc_vu_file(fei_row, field, ten_file, method):
    """Đọc một file đính kèm chứng từ HĐĐT rồi đẩy vào response.

    Dùng CHUNG cho cả bản chính thức (`official_pdf`) lẫn bản nháp
    (`draft_pdf`): hai đường gọi có chốt TRẠNG THÁI ngược nhau, nhưng phần
    "kiểm file thật sự đọc được rồi phục vụ" thì giống hệt — viết hai lần là
    hai chỗ có thể quên `make_access_log` hoặc quên lọc `attached_to_*`.

    Người gọi PHẢI tự kiểm sở hữu và trạng thái TRƯỚC khi gọi hàm này; hàm
    này không biết gì về khách của phiên.
    """
    duong_dan = fei_row.get(field)
    if not duong_dan:
        frappe.throw(
            "File đang được tạo, vui lòng thử lại sau ít phút.", frappe.ValidationError
        )

    # File có thể đã bị xoá/hỏng dù field vẫn còn giá trị cũ (NL-12.4) — kiểm
    # file THẬT SỰ đọc được, không chỉ tin field. Lọc thêm `attached_to_*`
    # (không chỉ `file_url`): Frappe gộp file trùng nội dung theo content
    # hash, nên nhiều `File` khác nhau (đính vào chứng từ HĐĐT khác nhau) có
    # thể trỏ CHUNG một `file_url` — chỉ lọc theo url sẽ tìm thấy record của
    # chứng từ KHÁC dù bản ghi của CHÍNH chứng từ này đã bị xoá (đã bắt gặp
    # thật khi hai chứng từ HĐĐT test có PDF trùng byte).
    file_doc = frappe.db.get_value(
        "File",
        {
            "file_url": duong_dan,
            "attached_to_doctype": einvoice.FEI,
            "attached_to_name": fei_row.name,
        },
        "name",
    )
    if not file_doc:
        frappe.throw(
            "File bị thiếu hoặc hỏng trên hệ thống. Vui lòng liên hệ kế toán Miyano.",
            frappe.ValidationError,
        )
    content = frappe.get_doc("File", file_doc).get_content()

    from frappe.core.doctype.access_log.access_log import make_access_log

    make_access_log(
        doctype=einvoice.FEI, document=fei_row.name, file_type="pdf", method=method,
    )
    frappe.local.response.filename = ten_file
    frappe.local.response.filecontent = content
    frappe.local.response.type = "pdf"


@frappe.whitelist()
def portal_einvoice_download(invoice, loai="pdf", fei=None) -> None:
    """US-E7.2/BR-E4 — tải file HĐĐT của một hoá đơn. `loai`:

    - `"pdf"`  — bản thể hiện hoá đơn ĐÃ PHÁT HÀNH (`official_pdf`), chốt
      trạng thái `einvoice.co_the_tai()` (06 trở đi).
    - `"nhap"` — bản in thử Fast dựng khi chứng từ còn ở 01–04 (`draft_pdf`),
      chốt trạng thái `einvoice.la_ban_nhap()` — NGƯỢC LẠI với trên.

    KHÔNG có XML: module HĐĐT không lưu XML ở đâu cả (không field nào chứa
    'xml' trên `Fast EInvoice Document`, đã kiểm JSON) — không có gì để giao.

    `fei` TUỲ CHỌN — một hoá đơn có thể khớp NHIỀU chứng từ HĐĐT (gốc + điều
    chỉnh/thay thế/lập lại), khách chọn đúng bản muốn tải từ danh sách
    `khac`/`chinh` mà `portal_invoices` đã trả. Tham số này KHÔNG BAO GIỜ
    được dùng thẳng để lấy tài liệu — chỉ dùng để LỌC trong tập
    `resolve_all(invoice)` đã tự suy từ phiên và đã lọc đúng khách; một tên
    không có trong tập đó (hoá đơn của khách khác, tên bịa) bị từ chối ngay,
    không round-trip `frappe.get_doc(FEI, ...)` với tên client gửi.

    Kiểm TỪNG LẦN tải (BR-E4, NL-12.5): hoá đơn thuộc customer của phiên +
    Fast EInvoice Document khớp thuộc ĐÚNG hoá đơn đó + trạng thái cho phép
    tải + file thật sự đọc được — không chỉ tin cờ `tai_duoc` đã tính lúc
    liệt kê (dữ liệu có thể đã đổi giữa hai lần gọi, và đây là chứng từ
    thuế). Không có URL file công khai: `/printview` hay dán link sang máy
    khác không đăng nhập đều 403 ở `check_permission`/`get_portal_customer`.
    """
    if loai not in ("pdf", "nhap"):
        frappe.throw(
            "Cổng chỉ cung cấp bản PDF thể hiện và bản nháp. Cần bản gốc XML "
            "có giá trị pháp lý, vui lòng liên hệ kế toán Miyano.",
            frappe.ValidationError,
        )

    _si, ho_so = _ho_so_cua_hoa_don(invoice)
    if not ho_so:
        frappe.throw("Chưa có hoá đơn điện tử cho chứng từ này.", frappe.ValidationError)

    if fei:
        muc = next((f for f in ho_so if f.name == fei), None)
        if not muc:
            raise frappe.PermissionError("Chứng từ HĐĐT không thuộc hoá đơn này.")
    else:
        muc = einvoice.chon_ban_ghi_chinh(ho_so)

    # Hai nhánh TÁCH BẠCH, cố ý không gộp điều kiện: chốt trạng thái của
    # chúng NGƯỢC nhau (`co_the_tai` mở từ 06, `la_ban_nhap` mở 01–04). Gộp
    # lại là sớm muộn cũng giao một bản in thử cho khách như thể nó là chứng
    # từ thuế, hoặc chặn nhầm hoá đơn thật.
    if loai == "nhap":
        if not einvoice.la_ban_nhap(muc):
            frappe.throw(
                "Chứng từ này không còn ở dạng nháp. Dùng nút tải hoá đơn điện tử.",
                frappe.ValidationError,
            )
        _phuc_vu_file(
            muc, "draft_pdf", f"Nhap_{muc.name}.pdf", "portal_einvoice_download_nhap"
        )
        return

    if not einvoice.co_the_tai(muc):
        frappe.throw(
            "Hoá đơn điện tử này chưa có file để tải. Bấm [Yêu cầu hỗ trợ] "
            "nếu cần Miyano hỗ trợ.",
            frappe.ValidationError,
        )
    _phuc_vu_file(
        muc,
        "official_pdf",
        f"{muc.fast_invoice_no or muc.name}.pdf",
        "portal_einvoice_download",
    )


@frappe.whitelist()
def portal_einvoice_nhap(delivery_note):
    """Khối "Hoá đơn nháp" của một phiếu giao — dòng hàng + tổng tiền của
    chứng từ HĐĐT kế toán vừa lập, kèm câu cảnh báo pháp lý đi CÙNG dữ liệu
    (`einvoice.CANH_BAO_NHAP`). `None` khi chưa lập.

    Neo theo Delivery Note chứ không theo Sales Invoice: bản ghi HĐĐT do
    `builder.create_from_delivery_note` sinh ra chỉ có `delivery_note`, và
    phiếu giao có thể chưa được lập hoá đơn bán hàng tại thời điểm đó."""
    dn = _dn_cua_khach(delivery_note)
    return einvoice.nhap_cho_delivery_note(dn.name, dn.customer)


@frappe.whitelist()
def portal_einvoice_nhap_pdf(delivery_note) -> None:
    """Tải bản in thử PDF theo PHIẾU GIAO — dùng ở màn chi tiết đơn hàng,
    nơi phiếu giao có thể chưa có Sales Invoice nào để bám vào.

    Cùng ràng buộc với `portal_einvoice_download`: kiểm sở hữu từng lần,
    không nhận tên chứng từ từ client, ghi `Access Log`."""
    dn = _dn_cua_khach(delivery_note)
    ban = einvoice.ban_nhap_tho(dn.name, dn.customer)
    if not ban:
        frappe.throw(
            "Phiếu giao này chưa có hoá đơn nháp. Nếu hoá đơn đã phát hành, "
            "xem ở mục Hoá đơn & công nợ.",
            frappe.ValidationError,
        )
    _phuc_vu_file(ban, "draft_pdf", f"Nhap_{dn.name}.pdf", "portal_einvoice_nhap_pdf")


@frappe.whitelist()
def portal_einvoice_ho_tro(invoice, fei=None) -> dict:
    """NL-12.4 — nút [Yêu cầu hỗ trợ] trên khối HĐĐT, tự đính mã hoá đơn.
    `fei` tuỳ chọn (cùng nguyên tắc "chỉ lọc trong tập đã resolve" của
    `portal_einvoice_download`) — khi khách bấm nút trên MỘT bản ghi cụ thể
    trong danh sách `khac`, thông báo đính đúng mã đó."""
    si, ho_so = _ho_so_cua_hoa_don(invoice)
    customer = si.customer
    fei_name = None
    if fei:
        muc = next((f for f in ho_so if f.name == fei), None)
        fei_name = muc.name if muc else None
    elif ho_so:
        fei_name = einvoice.chon_ban_ghi_chinh(ho_so).name
    bao_yeu_cau_ho_tro_hddt(customer, invoice, fei_name)
    return {"ok": True}


@frappe.whitelist()
def portal_request_cancel(order, reason) -> dict:
    dam_bao_xem_duoc("Sales Order", order)
    so = frappe.get_doc("Sales Order", order)
    so.check_permission("read")
    if so.docstatus != 0:
        frappe.throw("Chỉ yêu cầu huỷ được khi đơn còn Chờ xác nhận.")
    so.add_comment("Comment", f"[Portal] Khách yêu cầu huỷ: {reason}")
    frappe.get_doc({
        "doctype": "ToDo", "description": f"Khách yêu cầu huỷ {order}: {reason}",
        "reference_type": "Sales Order", "reference_name": order,
    }).insert(ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist()
def portal_provision(customer, email, send_invite=False) -> dict:
    # Caller-role guard: only staff (not portal customers) may provision accounts.
    if not (set(frappe.get_roles()) & {"System Manager", "Sales Manager", "Sales User"}):
        frappe.throw("Không có quyền", frappe.PermissionError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw("Không tìm thấy khách hàng.")
    # VÒNG SỬA 3 (F5, review độc lập, Important): chặn SỚM, TRƯỚC mọi side
    # effect (User/Contact/User Permission). Bản trước không kiểm điều này
    # — nếu `email` đã có `Portal Member` thuộc một khách hàng KHÁC,
    # hàm vẫn âm thầm tạo Contact + Dynamic Link + User Permission cho
    # `customer` mới rồi trả về như cấp thành công, trong khi danh tính
    # cổng (Portal Member) của user đó vẫn trỏ về khách hàng CŨ — tài khoản
    # sẽ không bao giờ nhìn thấy `customer` mới, và người cấp không thấy gì
    # bất thường để biết mà sửa.
    khach_hien_co = frappe.db.get_value("Portal Member", {"user": email}, "customer")
    if khach_hien_co and khach_hien_co != customer:
        frappe.throw(
            f'Tài khoản "{email}" đã thuộc khách hàng "{khach_hien_co}", không thể '
            f'cấp thêm cho "{customer}". Một tài khoản chỉ thuộc một khách hàng.',
            frappe.ValidationError,
        )
    if not frappe.db.exists("User", email):
        u = frappe.get_doc({
            "doctype": "User", "email": email, "first_name": customer,
            "user_type": "Website User", "send_welcome_email": int(send_invite),
        })
        u.append("roles", {"role": "Customer"})
        u.insert(ignore_permissions=True)
    contact_name = f"{customer}-{email}"
    if not frappe.db.exists("Contact", contact_name):
        ct = frappe.get_doc({"doctype": "Contact", "first_name": customer, "user": email})
        ct.name = contact_name
        ct.append("email_ids", {"email_id": email, "is_primary": 1})
        ct.append("links", {"link_doctype": "Customer", "link_name": customer})
        ct.insert(ignore_permissions=True)
    if not frappe.db.exists("User Permission", {"user": email, "allow": "Customer", "for_value": customer}):
        frappe.get_doc({
            "doctype": "User Permission", "user": email,
            "allow": "Customer", "for_value": customer,
        }).insert(ignore_permissions=True)
    # Từ 18/08/2026 `portal_context.get_allowed_customers()` chỉ đọc `Portal
    # Member`, không còn đọc `Contact`/`Dynamic Link` nữa — thiếu bước này,
    # tài khoản vừa cấp sẽ VÔ HÌNH với toàn bộ tầng phân quyền cổng ngay khi
    # hàm này trả về (Task 5, phát hiện qua test_provision.py đỏ). Đi qua
    # `doc.insert()` để `PortalMember.validate()` chạy, KHÔNG dùng
    # `frappe.db.set_value()`/`doc.db_set()` — xem giới hạn đã biết của
    # `_chan_hai_quan_ly` trong portal_member.py.
    #
    # VÒNG SỬA 2 (F5, phán quyết coordinator): chủ đầu tư mô tả luồng thật
    # là "nhân viên có tài khoản và ĐƯỢC GÁN KHOA BỞI QUẢN LÝ, nhưng tài
    # khoản sẽ được tạo ở phía Miyano" — tài khoản có TRƯỚC khoa phòng.
    # Tài khoản ĐẦU TIÊN của một bệnh viện luôn là Quản lý, kích hoạt ngay
    # (không có quản lý nào khác để chọi `_chan_hai_quan_ly`). Tài khoản
    # SAU ĐÓ — bệnh viện đã có quản lý đang hoạt động — không thể tự nó là
    # quản lý thứ hai, nên tạo dạng Nhân viên khoa CHƯA gán khoa (`active=0`
    # — chỗ giữ chỗ hợp lệ nhờ `_chan_vai_tro_va_khoa_phong`/
    # `_chan_thieu_ma_ngan` vừa nới ở vòng sửa này) và CHỜ quản lý gán khoa
    # + bật lại. Đây KHÔNG còn cùng hình với ca "hai tài khoản" của patch
    # backfill (`v1_23/backfill_portal_member.py`, vẫn tạo Quản lý+active=0
    # vì backfill không có nghiệp vụ "quản lý gán khoa sau" đứng sau nó) —
    # hai đường cố ý khác hình nhau, không phải một sai lệch cần hợp nhất.
    if frappe.db.exists("Portal Member", {"user": email}):
        cho_gan_khoa = frappe.db.get_value("Portal Member", {"user": email}, "active") == 0
    else:
        da_co_quan_ly = frappe.db.exists(
            "Portal Member", {"customer": customer, "vai_tro": "Quản lý", "active": 1}
        )
        if da_co_quan_ly:
            frappe.get_doc({
                "doctype": "Portal Member", "user": email, "customer": customer,
                "vai_tro": "Nhân viên khoa", "active": 0,
            }).insert(ignore_permissions=True)
            cho_gan_khoa = True
        else:
            frappe.get_doc({
                "doctype": "Portal Member", "user": email, "customer": customer,
                "vai_tro": "Quản lý", "active": 1,
            }).insert(ignore_permissions=True)
            cho_gan_khoa = False
    # `cho_gan_khoa`: True nghĩa là tài khoản vừa cấp CHƯA dùng được — quản
    # lý bệnh viện phải vào gán khoa phòng rồi bật `active` mới xong. Trả
    # cờ này ra để người gọi (giao diện cấp tài khoản phía Miyano) biết còn
    # một bước nữa, không để tài khoản "cấp xong nhưng chết lặng lẽ".
    return {"user": email, "cho_gan_khoa": cho_gan_khoa}


@frappe.whitelist()
def portal_document_download(doctype, name) -> None:
    if doctype not in ("Sales Order", "Delivery Note", "Sales Invoice"):
        frappe.throw("Loại chứng từ không hợp lệ.")
    # Vệ guard trên CHỈ CHO QUA đúng 3 doctype `dam_bao_xem_duoc` đã có nhánh
    # — `NotImplementedError` của hàm đó (doctype lạ) không bao giờ tới được
    # đây để lộ ra khách như một lỗi 500.
    dam_bao_xem_duoc(doctype, name)
    doc = frappe.get_doc(doctype, name)
    # frappe.get_doc does NOT auto-enforce has_permission in this build, so the
    # isolation check must be done explicitly before any data leaves the server.
    doc.check_permission("read")
    # Phiếu giao đã có BẢN SCAN ĐÃ KÝ thì khách nhận đúng bản đó, không phải
    # bản in lại chưa chữ ký. Đó là thứ khách cần khi đối chiếu công nợ hay
    # khi thanh tra hỏi "ai đã nhận hàng ngày đó": một bản in mới sinh chứng
    # minh được nội dung, không chứng minh được việc bàn giao đã xảy ra.
    # (Yêu cầu nguyên văn của chủ đầu tư và ngày nêu: xem docstring
    # `patches/v1_28/them_o_dinh_bien_ban_da_ky.py` — chép ở MỘT chỗ.)
    canh_bao = None
    if doctype == "Delivery Note":
        da_phat, canh_bao = _tra_ban_scan_da_ky(doc)
        if da_phat:
            return
    from frappe.utils.pdf import get_pdf
    from frappe.www.printview import get_html_and_style
    # Each doctype renders through its installed bilingual Miyano print
    # format (see setup/install_print_formats.py).
    PRINT_FORMATS = {
        "Sales Order": "Miyano - Xác nhận đơn hàng",
        # Nút "⬇ Phiếu giao đợt" phát ĐÚNG tờ phiếu mà hai bên ký, tức mẫu
        # 02-VT "Phiếu xuất kho kiêm biên bản bàn giao", KHÔNG phải
        # "Miyano - Phiếu giao hàng" (mẫu thương mại, một tờ giấy KHÁC).
        # Sự việc kiểm chứng được bằng SQL: site có nhiều mẫu in cho
        # `Delivery Note`, và mẫu có ô ký của HAI BÊN là mẫu 02-VT.
        #
        # Vì sao đây là lỗi chứ không phải chuyện thẩm mỹ: khách ký vào tờ A
        # tại kho, rồi lên cổng tải về tờ B với bố cục khác, thiếu cột Số lô/
        # Hạn dùng và thiếu đoạn cam kết bàn giao. Lúc đối chiếu công nợ hay
        # lúc thanh tra hỏi, hai tờ giấy cùng nói về một lần giao mà không
        # khớp nhau về hình thức là thứ không giải thích được — và không có
        # tín hiệu nào báo, vì bản thân mỗi tờ đều "đúng".
        #
        # Một chứng từ, hai trạng thái: CHƯA có bản scan → in bản 02-VT chưa
        # ký; ĐÃ đính bản scan → `_tra_ban_scan_da_ky` ở trên trả thẳng bản
        # có chữ ký. Mẫu "Miyano - Phiếu giao hàng" KHÔNG gỡ khỏi site —
        # nhân viên vẫn chọn được trên Desk khi cần một bản thương mại.
        "Delivery Note": "Miyano - Phiếu xuất kho (02-VT)",
        "Sales Invoice": "Miyano - Hoá đơn",
    }
    print_format = PRINT_FORMATS.get(doctype)
    html = get_html_and_style(
        doc=doc.as_json(), print_format=print_format, no_letterhead=0
    )["html"]
    if canh_bao:
        html = _dan_canh_bao(html, canh_bao)
    frappe.local.response.filename = f"{name}.pdf"
    frappe.local.response.filecontent = get_pdf(html)
    frappe.local.response.type = "pdf"


# Đuôi file được phép phát ra cho khách. Đuôi lấy từ TÊN FILE, mà tên file là
# văn bản tự do do người đính đặt — không phải một khai báo kiểu dữ liệu.
#
# CỐ Ý không đoán kiểu file bằng magic byte: đó là thêm một lớp suy đoán nữa
# để phục vụ một cái tên đặt sai, trong khi đường lui (in bản chưa ký) đã có
# sẵn, đã được kiểm, và cho khách một chứng từ đọc được ngay.
# Ruling P45 (chủ đầu tư chốt) — nút phiếu giao MỞ XEM ngay trong tab, không
# tải về. Chia làm hai nhóm vì "mở xem" chỉ đúng với thứ trình duyệt dựng
# được; `.tif` mở inline ra một TAB TRẮNG. Nhóm thứ hai là ĐƯỜNG THOÁT bắt
# buộc: giữ nguyên đường tải về, khách cầm được file thay vì nhìn trang trống.
_DUOI_MO_XEM = ("pdf", "jpg", "jpeg", "png", "gif", "bmp", "webp")
_DUOI_TAI_VE = ("tif", "tiff")
# `heic` CỐ Ý không nằm trong danh sách: máy Windows của bệnh viện phần lớn
# không mở được, nên phát ra một tệp HEIC là hỏng im lặng ở đầu bên kia. Ảnh
# HEIC phải được lưu lại thành JPG/PDF trước khi đính.
_DUOI_SCAN_CHO_PHEP = _DUOI_MO_XEM + _DUOI_TAI_VE

# Dán lên ĐẦU bản in khi phiếu ĐÃ CÓ bản scan đã ký mà cổng không phát được.
# Không có dòng này, khách nhận một tờ chưa ký trông hoàn toàn hợp lý trong
# khi bản đã ký vẫn tồn tại — đúng lớp "thay thế im lặng" mà cả việc này sinh
# ra để dẹp. Cảnh báo phải nằm trên CHÍNH tờ giấy khách mở ra; một dòng Error
# Log chỉ Miyano thấy.
_CANH_BAO_CHUA_KY = (
    "BẢN IN LẠI — CHƯA CÓ CHỮ KÝ. Phiếu giao này ĐÃ CÓ bản scan biên bản hai "
    "bên ký, nhưng cổng chưa phát được (lỗi tệp phía Miyano, đã có cảnh báo "
    "tự động). Vui lòng liên hệ Miyano 0988.806.848 để nhận bản đã ký."
)


def _dan_canh_bao(html: str, canh_bao: str) -> str:
    """Dán một khối cảnh báo lên đầu bản in.

    `escape_html` chứ không nối chuỗi thẳng: nội dung cảnh báo hôm nay là hằng
    số, nhưng hàm này là chỗ duy nhất chèn văn bản vào một trang sắp thành PDF
    — để ngỏ là mở sẵn một đường XSS lưu trữ cho lần sửa sau.
    """
    return (
        '<div style="border:2px solid #b00020; color:#b00020; padding:8px 10px;'
        ' margin:0 0 12px; font-weight:bold; font-size:13px; text-align:center">'
        f"⚠ {frappe.utils.escape_html(canh_bao)}</div>" + html
    )


def _tra_ban_scan_da_ky(doc) -> tuple[bool, str | None]:
    """Phiếu giao có bản scan biên bản đã ký → ĐẨY CHÍNH FILE ĐÓ ra response.

    Trả `(đã_phát, cảnh_báo)`:
      * `(True, None)`  — đã đẩy file, người gọi dừng;
      * `(False, None)` — phiếu không có bản scan nào, in bản chưa ký như cũ;
      * `(False, "...")` — phiếu CÓ bản scan nhưng không phát được. Vẫn in bản
        chưa ký (khách cầm được chứng từ đọc được ngay), NHƯNG kèm cảnh báo
        trên chính tờ giấy đó. Lui về trong im lặng ở nhánh này là đưa khách
        một tờ khác với tờ họ đã ký mà không nói gì.

    Ba chốt, mỗi chốt bịt một cách hỏng đã lường trước:

    1. **Không tin `file_url` một mình.** `custom_bien_ban_da_ky` là một ô
       `Attach`, giá trị của nó chỉ là một CHUỖI đường dẫn — sửa được từ Desk,
       và trỏ được tới bất kỳ file nào trên site (kể cả file riêng của khách
       khác). Nên phải tra `tabFile` bằng CẢ `attached_to_doctype` +
       `attached_to_name` khớp đúng phiếu giao này. Không khớp → coi như không
       có, in bản chưa ký; KHÔNG ném lỗi ra mặt khách vì đó là lỗi cấu hình
       phía Miyano, không phải việc của họ.

    2. **KHÔNG cứng `type = "pdf"`.** Bản scan thực tế phần lớn là ảnh chụp
       (JPG/PNG) chứ không phải PDF. Trả một JPG dưới đuôi `.pdf` thì máy
       khách mở ra rác — hỏng im lặng, và người báo lỗi sẽ là bệnh viện.
       Đuôi file lấy từ chính tên file đã lưu, NHƯNG chỉ trong danh sách cho
       phép (`_DUOI_SCAN_CHO_PHEP`).

    3. **Đọc nội dung qua `File.get_content()`**, không ghép đường dẫn tay:
       file riêng tư nằm ở `sites/<site>/private/files`, file công khai ở
       `public/files` — hàm của Frappe biết chỗ, phép ghép chuỗi thì không.
    """
    url = (doc.get("custom_bien_ban_da_ky") or "").strip()
    if not url:
        return False, None
    ten_file = frappe.db.get_value(
        "File",
        {
            "file_url": url,
            "attached_to_doctype": "Delivery Note",
            "attached_to_name": doc.name,
        },
        "name",
    )
    if not ten_file:
        # File không thuộc phiếu này (ô `Attach` bị sửa tay, dán nhầm đường dẫn
        # của phiếu khác). KHÔNG cảnh báo trên bản in: với phiếu NÀY thì không
        # có bản scan hợp lệ nào cả, và một cảnh báo "đã có bản ký" ở đây là
        # nói sai với khách.
        return False, None
    f = frappe.get_doc("File", ten_file)
    tach = (f.file_name or url).rsplit(".", 1)
    duoi = tach[1].lower() if len(tach) == 2 else ""
    if duoi not in _DUOI_SCAN_CHO_PHEP:
        # Tên file là văn bản tự do: một bản scan đặt tên "bien ban 25.08.2026"
        # cho ra file `.2026`, không máy nào mở được. Lui về bản in như ca file
        # mất trên đĩa — khách vẫn có chứng từ đọc được, còn Miyano đổi lại tên.
        frappe.log_error(
            "portal_document_download",
            f"Bản scan biên bản của {doc.name} có tên file không mang đuôi hợp "
            f"lệ: «{f.file_name or url}». Cổng phát bản in CHƯA KÝ cho tới khi "
            f"file được đổi tên (đuôi hợp lệ: {', '.join(_DUOI_SCAN_CHO_PHEP)}).",
        )
        return False, _CANH_BAO_CHUA_KY
    try:
        noi_dung = f.get_content()
    except Exception:
        # File đã bị xoá khỏi đĩa nhưng bản ghi còn (dọn dẹp dở dang, restore
        # thiếu thư mục files). Lui về bản in — khách vẫn có chứng từ đọc
        # được, thay vì một lỗi 500 không nói được gì.
        #
        # `frappe.log_error(title, message)` — TIÊU ĐỀ trước. Gọi ngược thì
        # `Error Log.method` (Data, 140 ký tự) nhận cả câu tiếng Việt còn
        # phần `error` chỉ còn mỗi tên hàm: dòng log tra không ra, đọc không
        # hiểu.
        frappe.log_error(
            "portal_document_download",
            f"Không đọc được bản scan biên bản của {doc.name}: {url}",
        )
        return False, _CANH_BAO_CHUA_KY
    frappe.local.response.filename = f"{doc.name}-bien-ban-da-ky.{duoi}"
    frappe.local.response.filecontent = noi_dung
    frappe.local.response.type = "download"
    # Ruling P45. `as_raw()` của Frappe lấy Content-Disposition từ
    # `display_content_as`, mặc định "attachment". Đặt TƯỜNG MINH cả hai nhánh
    # (không chỉ nhánh inline): `frappe.local.response` sống qua nhiều lời gọi
    # trong cùng một tiến trình, để sót thì giá trị của lần trước chảy sang.
    frappe.local.response.display_content_as = (
        "inline" if duoi in _DUOI_MO_XEM else "attachment"
    )
    return True, None


@frappe.whitelist()
def portal_bao_gia_pdf(order) -> None:
    """§3.6 — tải PDF báo giá của MỘT đơn mua lẻ.

    Cùng khuôn `kho_phieu_pdf`/`portal_einvoice_download` (Quyết định nền số
    8): trả file qua response, KHÔNG sinh URL công khai — người dùng cổng
    không dùng được `/printview`.

    `frappe.get_doc` KHÔNG tự kiểm quyền trong bản này, nên phải tự đối chiếu
    `customer` của đơn với khách suy từ PHIÊN (Quyết định nền số 7) — không
    nhận `customer` từ client dưới bất kỳ hình thức nào.
    """
    dam_bao_xem_duoc("Sales Order", order)
    customer = get_portal_customer()
    so = frappe.db.get_value(
        "Sales Order", order,
        ["name", "customer", "workflow_state", "custom_loai_don"],
        as_dict=True,
    )
    if not so:
        frappe.throw("Không tìm thấy đơn hàng.", frappe.DoesNotExistError)
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng này không thuộc đơn vị của bạn.")

    # review I-2 — mẫu in "Miyano - Báo giá" chỉ có nghĩa cho đơn ĐI VÒNG
    # BÁO GIÁ (§3.6 "hạn hiệu lực báo giá" là khái niệm CHỈ của nhánh này,
    # cùng lý do `condition` của Notification "Portal - Báo giá sẵn sàng" đã
    # lọc theo `custom_loai_don`). Không để đơn thuần hợp đồng tải được một
    # chứng từ đề "Hiệu lực đến..." mà không job nào thi hành.
    #
    # Task 6 (QĐ-G2b) — `di_vong_bao_gia()` đọc đúng cột `custom_loai_don`
    # đã lấy sẵn ở truy vấn phía trên, nhưng hỏi bằng TÊN của điều đang hỏi.
    if not di_vong_bao_gia(so):
        frappe.throw(
            "Đơn này không có dòng nào chờ báo giá — không có báo giá dạng "
            "PDF để tải.",
            frappe.ValidationError,
        )

    # Chỉ từ lúc báo giá ĐÃ GỬI cho khách trở đi. Trước đó `rate` là con số
    # sales đang sửa — cho tải là biến một bản nháp thành cam kết.
    if so.workflow_state not in (TRANG_THAI_CHO_KHACH, "Chờ Miyano xác nhận", "Đã xác nhận"):
        frappe.throw(
            "Báo giá cho đơn này chưa được gửi. Vui lòng đợi Miyano báo giá.",
            frappe.ValidationError,
        )

    # review Minor — nếu mẫu in "Miyano - Báo giá" chưa tồn tại (patch cài
    # đặt chưa chạy, hoặc bị xoá thủ công), `frappe.get_print` ÂM THẦM rơi
    # về mẫu Standard — mẫu đó in MỌI dòng, kể cả dòng giữ chỗ `ITEM_GIU_CHO`
    # (chỉ mẫu "Miyano - Báo giá" mới biết lọc, xem `install_print_formats.
    # py`). Kiểm tồn tại và báo lỗi rõ, không để rơi ngầm sang một chứng từ
    # sai định dạng và có thể lộ chi tiết kỹ thuật nội bộ.
    if not frappe.db.exists("Print Format", "Miyano - Báo giá"):
        frappe.throw(
            "Mẫu in báo giá chưa sẵn sàng. Vui lòng liên hệ quản trị viên hệ thống.",
            frappe.ValidationError,
        )

    pdf = frappe.get_print(
        "Sales Order", so.name, print_format="Miyano - Báo giá", as_pdf=True
    )
    frappe.local.response.filename = f"BaoGia-{so.name}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"


@frappe.whitelist()
def portal_reorder(order: str) -> dict:
    """UC-14 / US-E1.5 — điền lại giỏ theo một đơn cũ, theo GIÁ HIỆN HÀNH.

    Dòng nào không còn đặt được thì vào `bi_loai` kèm mã lý do để giao diện
    dịch sang thông điệp FormSpec §5. Im lặng bỏ bớt dòng là cách chắc chắn
    khiến khách đặt thiếu hàng mà không biết.

    Dòng còn đặt được một phần thì HẠ số lượng xuống phần còn lại chứ không
    loại cả dòng — còn 1 mà đơn cũ đặt 3 thì khách vẫn nên đặt được 1.
    """
    dam_bao_xem_duoc("Sales Order", order)
    customer = get_portal_customer()
    so = frappe.get_doc("Sales Order", order)
    # `frappe.get_doc` KHÔNG chạy hook `has_permission` ở build này — phải
    # kiểm tường minh trước khi đọc bất cứ thứ gì của tài liệu.
    so.check_permission("read")
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng không thuộc đơn vị của bạn.")

    # I-1 / Ruling P31 (review vòng 1) — SUY LẠI hợp đồng thắng cuộc THEO
    # TỪNG DÒNG, không tin `so.custom_hdnt` của đơn cũ. Hai lý do, cả hai đều
    # là lỗi thật:
    #   * `custom_hdnt` không kiểm hiệu lực. Hợp đồng hết hạn 31/12, ngày
    #     02/01 khách bấm "Đặt lại đơn cũ" → giỏ hiện giá VÀ hạn mức của một
    #     hợp đồng đã chết, rồi lúc xác nhận `_xay_don` (vốn luôn suy lại)
    #     tính theo hợp đồng kế nhiệm. Số hiện lúc xác nhận không phải số
    #     trên đơn — đường SỐNG, frontend đang gọi mỗi ngày;
    #   * `custom_hdnt` có thể là tham số CLIENT gửi lên khi đơn trải nhiều
    #     hợp đồng (xem `tao_sales_order`), nên nó không phải bằng chứng về
    #     hợp đồng của một DÒNG cụ thể.
    # Dùng ĐÚNG hàm mà `_xay_don`/`portal_catalog_gop` dùng — Ruling P28:
    # một sự thật, một nguồn. Giá và hạn mức của cùng một dòng phải hỏi
    # CÙNG một hợp đồng, nếu không giỏ lại tự mâu thuẫn với chính nó.
    thang_cuoc = nguon_gia_theo_ma_cho_khach(customer)
    price_list = frappe.db.get_value("Customer", customer, "default_price_list")
    gio_hang, bi_loai = [], []

    for dong in so.items:
        contract = thang_cuoc.get(dong.item_code)
        if not contract:
            bi_loai.append({"item_code": dong.item_code, "ly_do": "ngoai_hdnt"})
            continue

        con_lai, _ = han_muc_con(contract, dong.item_code)
        if con_lai is not None and con_lai <= 0:
            bi_loai.append({"item_code": dong.item_code, "ly_do": "het_han_muc"})
            continue

        # QĐ-G12 (Task 12) — ĐÚNG hàm mà `_xay_don` dùng. Trước Task 12 đây
        # là phép tra `Item Price` THỨ SÁU, độc lập, nên "đặt lại đơn cũ"
        # vẫn trả `thieu_gia` cho đúng mặt hàng mà đặt mới đã đặt được:
        # cùng một mã, hai câu trả lời khác nhau tuỳ khách bấm nút nào.
        # `contract` ở đây là hợp đồng THẮNG CUỘC vừa suy lại cho chính
        # dòng này (`thang_cuoc.get(...)` ngay đầu vòng lặp), KHÔNG phải
        # `so.custom_hdnt` của đơn cũ — xem khối Ruling P31 phía trên, nơi
        # giải thích vì sao không được tin `custom_hdnt`. Đó cũng đúng là
        # hợp đồng vòng lặp này vừa dùng để tính hạn mức, nên giá và hạn
        # mức của một dòng luôn hỏi CÙNG một hợp đồng.
        gia = gia_hdnt.gia_dong_hop_dong(dong.item_code, contract, price_list)
        if not gia:
            bi_loai.append({"item_code": dong.item_code, "ly_do": "thieu_gia"})
            continue

        qty = float(dong.qty)
        if con_lai is not None:
            qty = min(qty, con_lai)
        # Kèm tên và ĐVT: giỏ hàng dựng thẳng từ payload này, thiếu chúng thì
        # khách nhìn thấy mã hàng trần và không có đơn vị tính.
        gio_hang.append({
            "item_code": dong.item_code,
            "item_name": dong.item_name
            or frappe.db.get_value("Item", dong.item_code, "item_name"),
            "uom": dong.uom or "",
            "qty": qty,
            "gia_hien_hanh": float(gia),
            "remaining": None if con_lai is None else con_lai,
        })

    return {"gio_hang": gio_hang, "bi_loai": bi_loai}


LY_DO_TOI_THIEU_KHACH = 10


@frappe.whitelist()
def portal_order_accept(order, action, ly_do=None) -> dict:
    """US-E2.5 / API Spec §2.4 — khách đồng ý hoặc không đồng ý báo giá.

    Chuyển trạng thái chạy DƯỚI QUYỀN HỆ THỐNG: transition được mở cho
    `System Manager`, không phải cho role `Customer` — khách không bao giờ có
    quyền workflow trên Desk. Nhưng người bấm vẫn được ghi vào Comment, nếu
    không thì mọi thao tác đồng ý đều mang danh "Administrator" và không truy
    được ai đã đồng ý.
    """
    dam_bao_xem_duoc("Sales Order", order)
    customer = get_portal_customer()
    so = frappe.get_doc("Sales Order", order)
    # `frappe.get_doc` KHÔNG chạy hook has_permission ở build này — phải tự kiểm.
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng không thuộc đơn vị của bạn.")
    if so.get("workflow_state") != "Chờ khách đồng ý":
        frappe.throw(
            "Đơn này không ở trạng thái chờ quý khách đồng ý.", frappe.ValidationError
        )
    # US-E6.5/BR-R5 — báo giá có hiệu lực N ngày kể từ ngày lập
    # (Settings.hieu_luc_bao_gia_ngay, mặc định 7). Chặn CẢ đồng ý lẫn không
    # đồng ý: một báo giá đã hết hiệu lực không còn gì để khách phản hồi,
    # job daily (`portal_bao_gia.quet_bao_gia_het_han`) sẽ tự đóng nó —
    # khách phải gửi yêu cầu báo giá mới, không phải bấm nút trên đơn cũ.
    #
    # review I-2(c) — CHỈ áp cho đơn ĐI VÒNG BÁO GIÁ. State "Chờ khách đồng
    # ý" KHÔNG phải riêng của E6: E2 (US-E2.5, trước cả E6) đã dùng nó cho
    # MỌI loại đơn cần khách duyệt giá, không có khái niệm hiệu lực N ngày
    # nào. Thiếu điều kiện này thì một đơn thuần hợp đồng đang chờ khách
    # duyệt (luồng E2 gốc, có thể mở nhiều tuần) cũng bị chặn 417 và bị
    # `quet_bao_gia_het_han` tự đóng — một hành vi BR-R5 (nằm trong §4.10,
    # phạm vi QT10) chưa từng yêu cầu.
    #
    # Task 6 (QĐ-G2b) — hỏi qua `di_vong_bao_gia()`, xem docstring hàm đó.
    if di_vong_bao_gia(so) and qua_han_hieu_luc(so):
        han = han_hieu_luc_bao_gia(so)
        frappe.local.response["ly_do"] = "qua_han_hieu_luc"
        frappe.throw(
            f"Báo giá cho đơn {so.name} đã hết hiệu lực ngày "
            f"{frappe.utils.formatdate(han, 'dd/mm/yyyy')}. Gửi yêu cầu báo "
            f"giá mới nếu vẫn cần hàng.",
            frappe.ValidationError,
        )

    if action == "dong_y":
        hanh_dong, ghi_chu = "Khách đồng ý", ""
    elif action == "khong_dong_y":
        ly_do = (ly_do or "").strip()
        if len(ly_do) < LY_DO_TOI_THIEU_KHACH:
            frappe.throw(
                f"Vui lòng nêu lý do (tối thiểu {LY_DO_TOI_THIEU_KHACH} ký tự).",
                frappe.ValidationError,
            )
        hanh_dong, ghi_chu = "Khách không đồng ý", ly_do
    else:
        frappe.throw("Hành động không hợp lệ.", frappe.ValidationError)

    nguoi_bam = frappe.session.user
    from frappe.model.workflow import apply_workflow

    # CỐ Ý KHÔNG dùng frappe.set_user() ở đây (code review sau lần merge đầu
    # phát hiện): frappe.local.session LÀ CÙNG MỘT OBJECT với
    # Session.data trong frappe/sessions.py — set_user() ghi đè
    # local.session.sid bằng chính chuỗi username (không phải sid thật) và
    # xoá sạch local.session.data (mất csrf_token...). Session.update()
    # (app.py, cuối MỌI request thật) vẫn dùng self.sid GỐC (biến riêng của
    # Session, không đổi) làm khoá `frappe.cache.hset("session", self.sid,
    # self.data)` — nên nó ghi ĐÈ cache session THẬT của chính khách đang gọi
    # bằng self.data đã hỏng. Gọi set_user() lần hai để "trả lại" chỉ khiến
    # nó tệ hơn: sid bị đặt lại thành username (không phải sid gốc), data
    # thành dict rỗng — không phải dữ liệu session gốc. Kết quả: khách mở
    # báo giá lâu (vượt threshold update session giữa chừng) rồi bấm Đồng ý
    # thì mọi POST sau đó trên tab đang mở lỗi CSRF tới khi tải lại trang.
    #
    # apply_workflow() chỉ tra vai trò qua frappe.get_roles() ->
    # frappe.session.user (frappe/model/workflow.py, frappe/permissions.py
    # get_roles() cache theo user nên an toàn khi đổi qua đổi lại) — không
    # đọc sid hay session.data ở đâu cả. Nên chỉ cần đổi ĐÚNG MỘT thuộc tính
    # `session.user`, không đụng `sid`/`data`, là đủ để apply_workflow chạy
    # dưới quyền hệ thống mà không có gì trên session thật của khách để
    # khôi phục sai.
    session = frappe.local.session
    frappe.local.user_perms = None  # tránh dùng nhầm cache quyền của người cũ
    session.user = "Administrator"
    try:
        so = apply_workflow(so, hanh_dong)
        noi_dung = f"{hanh_dong} bởi {nguoi_bam}"
        if ghi_chu:
            noi_dung += f" — lý do: {ghi_chu}"
        so.add_comment("Comment", noi_dung)
    finally:
        # Trả phiên về NGAY, kể cả khi apply_workflow ném: bỏ finally là để
        # phần còn lại của request chạy dưới quyền Administrator. CHỈ đổi
        # lại `session.user` — `sid`/`data` của khách chưa từng bị đụng tới
        # nên không có gì để khôi phục sai (xem giải thích ở trên).
        session.user = nguoi_bam
        frappe.local.user_perms = None

    if action == "dong_y":
        # US-E6.5 — cạnh "Đã chuyển thành đơn" mà Phần A đã dựng sẵn trong
        # máy trạng thái Portal Item Request nhưng chưa ai ghi. Chạy SAU khi
        # phiên khách đã được trả lại (không cần ignore_permissions cảnh báo
        # giả — `cap_nhat_yeu_cau_goc` tự `ignore_permissions=True`), và
        # KHÔNG được để một trục trặc ở đây làm hỏng việc đồng ý đã ghi
        # nhận thành công phía trên (xem docstring của hàm).
        cap_nhat_yeu_cau_goc(so, "Đã chuyển thành đơn")
    elif action == "khong_dong_y":
        # review I-5/NL-10.4 — BA §4.10 ghi rõ "lý do lưu vào đơn VÀ yêu
        # cầu gốc". Bản trước chỉ ghi Comment lên `so` (dòng phía trên) —
        # `Portal Item Request` liên kết đứng yên ở "Đã báo giá" không dấu
        # vết, F-23 (màn chi tiết yêu cầu, đọc `binh_luan`) không có gì để
        # sales thấy khách chê gì. KHÔNG đổi `trang_thai`: máy trạng thái
        # (portal_item_request.py) không có cạnh nào rời "Đã báo giá" để
        # "sales sửa giá" — sales sửa thẳng trên SO đã liên kết, yêu cầu gốc
        # giữ nguyên "Đã báo giá", chỉ thêm dấu vết bằng Comment.
        ten_yc = so.get("custom_yeu_cau_goc")
        if ten_yc and frappe.db.exists("Portal Item Request", ten_yc):
            frappe.get_doc("Portal Item Request", ten_yc).add_comment(
                "Comment",
                f"[Portal] Khách không đồng ý báo giá {so.name} — lý do: {ghi_chu}",
            )

    return {"trang_thai_moi": so.get("workflow_state")}


@frappe.whitelist()
def portal_order_sua_so_luong(order, dong) -> dict:
    """Việc 1 / brief 2026-08-15 (bao-gia-hai-chieu) — khách SỬA SỐ LƯỢNG
    trên một đơn Mua lẻ đang "Chờ khách đồng ý".

    Quyết định chủ dự án (brief §"Quyết định của chủ dự án", mục A): đơn giá
    báo cho N hộp không còn đúng ở M hộp — giữ nguyên `rate` cũ là ràng buộc
    Miyano vào một mức giá ở sản lượng khác hẳn mà không ai đồng ý. Nên:
    đơn VỀ "Chờ xác nhận" cho sales báo giá lại, và `rate` của MỌI dòng đã
    đổi số lượng bị đặt về 0 (báo giá cũ hết hiệu lực cho dòng đó).

    Chuyển trạng thái DÙNG LẠI transition "Khách không đồng ý" ("Chờ khách
    đồng ý" -> "Chờ xác nhận", allowed "System Manager") — brief: "KHÔNG
    thêm trạng thái mới cho nhánh này". Không lộ ra khách: `apply_workflow`
    chỉ ghi Comment kiểu "Workflow" với TÊN TRẠNG THÁI ĐÍCH (`frappe/model/
    workflow.py:148`), không ghi tên action — nên việc dùng chung action với
    nhánh "Không đồng ý" không tạo ra dấu vết sai lệch nào trên timeline;
    Comment nghiệp vụ riêng (cũ -> mới) do CHÍNH hàm này ghi ngay bên dưới
    mới là thứ khách/sales đọc được.

    `dong` — JSON (hoặc dict) dạng:
        {"items": [{"item_code": str, "qty": float}, ...],
         "dat_ngoai": [{"name": str, "qty": float}, ...]}
    CHỈ đọc `item_code`/`name` (để KHỚP một dòng ĐÃ CÓ SẴN trên đơn) và
    `qty` — mọi field khác trong mỗi phần tử (`rate`, hoặc `item_code` không
    khớp dòng nào) bị bỏ qua/từ chối hoàn toàn, không có đường nào để
    payload tự thêm dòng mới hay tự đổi giá. Số lượng 0 = bỏ dòng đó.
    """
    dam_bao_xem_duoc("Sales Order", order)
    customer = get_portal_customer()
    so = frappe.get_doc("Sales Order", order)
    # `frappe.get_doc` KHÔNG tự kiểm quyền ở build này — phải tự đối chiếu
    # `customer` của đơn với khách suy từ PHIÊN, không nhận `customer` từ
    # client dưới bất kỳ hình thức nào (Quyết định nền số 7/8).
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng này không thuộc đơn vị của bạn.")
    # Task 9 (§12 Q4) — chặn theo VAI TRÒ, không chỉ theo workflow_state.
    # Đơn đã đi qua đường đề xuất và được quản lý duyệt thì nhân viên khoa
    # không sửa THẲNG số lượng ở đây nữa — họ phải xin sửa
    # (`de_xuat.de_xuat_xin_sua`) rồi để quản lý gọi lại đúng hàm này.
    dam_bao_duoc_sua_don_da_duyet(so)
    if so.get("workflow_state") != TRANG_THAI_CHO_KHACH:
        frappe.throw(
            "Đơn này không ở trạng thái chờ quý khách đồng ý.", frappe.ValidationError
        )
    # review (song song portal_order_accept) — "hiệu lực báo giá" (BR-R5)
    # CHỈ có nghĩa cho đơn đi vòng báo giá; state "Chờ khách đồng ý" cũng
    # được luồng E2 gốc dùng cho đơn thuần hợp đồng, nơi không có khái niệm
    # hiệu lực N ngày và số lượng đã chốt theo hợp đồng.
    #
    # Task 6 (QĐ-G2b) — `_kiem_don_dung_duoc_xin_sua()` của `Portal De Xuat
    # Mua` SOI GƯƠNG chốt này. Hai bên PHẢI hỏi cùng một hàm, nếu không
    # phiếu rời "Đã duyệt" rồi chết ở đây (đúng lỗi C1 ngày 19/08).
    if not di_vong_bao_gia(so):
        frappe.throw(
            "Chỉ áp dụng cho đơn có dòng chờ báo giá.", frappe.ValidationError
        )
    if qua_han_hieu_luc(so):
        han = han_hieu_luc_bao_gia(so)
        frappe.local.response["ly_do"] = "qua_han_hieu_luc"
        frappe.throw(
            f"Báo giá cho đơn {so.name} đã hết hiệu lực ngày "
            f"{frappe.utils.formatdate(han, 'dd/mm/yyyy')}. Gửi yêu cầu báo "
            f"giá mới nếu vẫn cần hàng.",
            frappe.ValidationError,
        )

    if isinstance(dong, str):
        dong = frappe.parse_json(dong)
    dong = dong or {}
    doi_items = dong.get("items") or []
    doi_dat_ngoai = dong.get("dat_ngoai") or []

    # review (I-4 tương tự _xay_don_ban_le) — dòng giữ chỗ kỹ thuật nội bộ
    # KHÔNG BAO GIỜ là một dòng khách "sửa được": không lộ ra `portal_order_
    # track` (đã lọc `ITEM_GIU_CHO`) nên khách bình thường không có cách nào
    # gõ đúng mã này, nhưng payload có thể bị sửa tay — chặn tường minh,
    # cùng lý lẽ `la_dong_giu_cho` đã dùng ở `_xay_don_ban_le`.
    for d in doi_items:
        if la_dong_giu_cho((d.get("item_code") or "").strip()):
            frappe.throw(
                f"{ITEM_GIU_CHO} là mã kỹ thuật nội bộ, không phải dòng hàng "
                "sửa được.",
                frappe.ValidationError,
            )

    # KHÔNG cho "thêm dòng" — mọi item_code/name trong payload phải khớp
    # một dòng ĐÃ CÓ trên đơn. Kiểm TRƯỚC khi đụng vào bất kỳ dòng nào (một
    # payload lẫn cả sửa hợp lệ VÀ một dòng lạ phải bị từ chối TOÀN BỘ,
    # không âm thầm áp phần hợp lệ rồi bỏ qua phần lạ).
    ma_dang_co = {i.item_code for i in so.items}
    doi_items_theo_ma: dict[str, dict] = {}
    for d in doi_items:
        ma = (d.get("item_code") or "").strip()
        if not ma:
            continue
        if ma not in ma_dang_co:
            frappe.throw(
                f"Không tìm thấy mặt hàng {ma} trong đơn — không thể thêm "
                "dòng mới qua sửa số lượng.",
                frappe.ValidationError,
            )
        doi_items_theo_ma[ma] = d

    ten_dat_ngoai_dang_co = {d.name for d in (so.get("custom_dat_ngoai") or [])}
    doi_dat_ngoai_theo_ten: dict[str, dict] = {}
    for d in doi_dat_ngoai:
        ten = d.get("name")
        if not ten:
            continue
        if ten not in ten_dat_ngoai_dang_co:
            frappe.throw(
                "Không tìm thấy dòng đặt ngoài trong đơn — không thể thêm "
                "dòng mới qua sửa số lượng.",
                frappe.ValidationError,
            )
        doi_dat_ngoai_theo_ten[ten] = d

    # review — GIỮ NGUYÊN các Document con đã có (không dựng dict tay từ
    # đầu): rebuild bằng dict tay sẽ ÂM THẦM làm rớt mọi field khác của
    # dòng (uom, conversion_factor, description...) và sinh `name`/`idx`
    # MỚI cho những dòng KHÔNG đổi gì — hỏng luôn việc khớp theo `name` ở
    # lần sửa dat_ngoai TIẾP THEO. `so.set(field, [... cùng object cũ ...])`
    # giữ nguyên name/idx (frappe `_init_child` chỉ gán idx/tên MỚI khi đối
    # tượng CHƯA có, xem `base_document.py::_init_child`).
    thay_doi: list[str] = []
    # Task 9, Step 4b (Ruling preflight C4) — số MỚI của từng dòng THẬT SỰ
    # đổi, dùng để đồng bộ ngược `so_luong_duyet` lên phiếu đề xuất đứng
    # sau (nếu có) SAU KHI đơn lưu thành công. `0.0` = dòng bị bỏ.
    doi_items_ap_dung: dict[str, float] = {}

    giu_items = []
    for i in list(so.items):
        match = doi_items_theo_ma.get(i.item_code)
        if match is None:
            giu_items.append(i)
            continue
        try:
            qty_moi = float(match.get("qty"))
        except (TypeError, ValueError):
            frappe.throw(f"{i.item_code}: số lượng không hợp lệ.", frappe.ValidationError)
        if qty_moi < 0:
            frappe.throw(f"{i.item_code}: số lượng không hợp lệ.", frappe.ValidationError)
        if qty_moi == 0:
            thay_doi.append(f"{i.item_code}: {i.qty} → bỏ dòng")
            doi_items_ap_dung[i.item_code] = 0.0
            continue
        if float(i.qty or 0) != qty_moi:
            thay_doi.append(
                f"{i.item_code}: {i.qty} → {qty_moi} (giá cũ {i.rate} không "
                "còn hiệu lực, chờ báo giá lại)"
            )
            i.qty = qty_moi
            # `rate` VÀ `price_list_rate` — cả hai về 0. Chỉ đặt `rate` mà để
            # nguyên `price_list_rate` có nguy cơ một luồng tính giá khác của
            # ERPNext coi `price_list_rate` là nguồn sự thật và ghi đè lại
            # `rate` khi lưu; đặt cả hai về 0 loại hẳn khả năng đó.
            i.rate = 0
            i.price_list_rate = 0
            doi_items_ap_dung[i.item_code] = qty_moi
        giu_items.append(i)

    giu_dat_ngoai = []
    for d in list(so.get("custom_dat_ngoai") or []):
        match = doi_dat_ngoai_theo_ten.get(d.name)
        if match is None:
            giu_dat_ngoai.append(d)
            continue
        try:
            qty_moi = float(match.get("qty"))
        except (TypeError, ValueError):
            frappe.throw(f"{d.ten_hang}: số lượng không hợp lệ.", frappe.ValidationError)
        if qty_moi < 0:
            frappe.throw(f"{d.ten_hang}: số lượng không hợp lệ.", frappe.ValidationError)
        if qty_moi == 0:
            thay_doi.append(f"{d.ten_hang} (đặt ngoài): {d.so_luong} → bỏ dòng")
            continue
        if float(d.so_luong or 0) != qty_moi:
            thay_doi.append(f"{d.ten_hang} (đặt ngoài): {d.so_luong} → {qty_moi}")
            d.so_luong = qty_moi
        giu_dat_ngoai.append(d)

    if not thay_doi:
        frappe.throw("Không có thay đổi số lượng nào để gửi.", frappe.ValidationError)

    # §3.4 — ERPNext không lưu được `items` rỗng (xem docstring
    # `_xay_don_ban_le`). Bỏ hết MỌI dòng (cả hàng thật lẫn đặt ngoài) không
    # còn gì để Miyano báo giá lại — hướng khách sang nút Huỷ (huỷ THẬT,
    # đóng đơn ngay) thay vì để endpoint này chặn mập mờ.
    giu_items_that = [i for i in giu_items if i.item_code != ITEM_GIU_CHO]
    if not giu_items_that and not giu_dat_ngoai:
        frappe.throw(
            "Đơn sẽ không còn dòng hàng nào sau khi sửa. Nếu muốn huỷ toàn "
            "bộ đơn, vui lòng dùng nút Huỷ đơn.",
            frappe.ValidationError,
        )
    if not giu_items_that and giu_dat_ngoai:
        # Giỏ hàng THẬT rỗng nhưng còn dòng đặt ngoài — cùng tình huống
        # `can_chen_giu_cho` xử lý lúc TẠO đơn: chèn dòng giữ chỗ để
        # ERPNext lưu được `items` khác rỗng.
        if not frappe.db.exists("Item", ITEM_GIU_CHO):
            frappe.throw(
                "Hệ thống chưa sẵn sàng nhận đơn toàn hàng chưa có mã. "
                "Vui lòng liên hệ Miyano.",
                frappe.ValidationError,
            )
        item_warehouse = _resolve_item_warehouse(ITEM_GIU_CHO, so.company)
        if not item_warehouse:
            frappe.throw(
                f"Không tìm thấy kho giao hàng cho mặt hàng {ITEM_GIU_CHO} "
                f"tại công ty {so.company}. Vui lòng liên hệ quản trị viên "
                "hệ thống.",
                frappe.ValidationError,
            )
        giu_items.append({
            "item_code": ITEM_GIU_CHO, "qty": 1, "rate": 0,
            "warehouse": item_warehouse, "delivery_date": so.delivery_date,
        })

    nguoi_bam = frappe.session.user
    from frappe.model.workflow import apply_workflow

    # Cùng lý do/khuôn với `portal_order_accept`: transition "Khách không
    # đồng ý" chỉ mở cho "System Manager", không phải role Customer. Đổi
    # DUY NHẤT `session.user` (KHÔNG đụng `sid`/`data`) — xem chú thích dài
    # ở `portal_order_accept` giải thích vì sao `frappe.set_user()` không an
    # toàn ở đây.
    session = frappe.local.session
    frappe.local.user_perms = None
    session.user = "Administrator"
    try:
        # Lưu thay đổi số lượng TRƯỚC — `apply_workflow()` tự gọi
        # `doc.load_from_db()` NGAY ĐẦU HÀM (frappe/model/workflow.py:102),
        # nên gọi nó trên `so` đang mang thay đổi CHƯA LƯU sẽ XOÁ SẠCH thay
        # đổi đó trước khi kịp áp dụng gì cả.
        so.set("items", [])
        for row in giu_items:
            so.append("items", row)
        so.set("custom_dat_ngoai", [])
        for row in giu_dat_ngoai:
            so.append("custom_dat_ngoai", row)
        so.save()

        so = apply_workflow(so, "Khách không đồng ý")
        noi_dung = (
            f"[Portal] Khách sửa số lượng bởi {nguoi_bam} — về \"Chờ xác "
            "nhận\" để báo giá lại:<br>" + "<br>".join(thay_doi)
        )
        so.add_comment("Comment", noi_dung)
    finally:
        session.user = nguoi_bam
        frappe.local.user_perms = None

    bao_khach_sua_so_luong(customer, so.name, thay_doi)

    # Task 9, Step 4b (Ruling preflight C4) — QUẢN LÝ sửa THẲNG (bỏ qua
    # `de_xuat_xin_sua`/`de_xuat_duyet_sua`, hoặc chính `de_xuat_duyet_sua`
    # gọi lại đúng hàm này) thì phiếu đề xuất đứng sau phải CÙNG cập nhật —
    # không có bước này, hai chứng từ nói hai số khác nhau và khối truy vết
    # §5.2 thành vô nghĩa. `so.get("custom_de_xuat")` an toàn khi cột chưa
    # tồn tại (patch chưa chạy): Document.get() trả `None`, đơn giản BỎ QUA
    # đồng bộ — đây không phải chốt phân quyền (đã qua ở
    # `dam_bao_duoc_sua_don_da_duyet`), chỉ là tiện ích giữ hai chứng từ
    # khớp nhau, nên không cần fail-closed ở đây.
    de_xuat_ten = so.get("custom_de_xuat")
    if de_xuat_ten and doi_items_ap_dung:
        _dong_bo_so_luong_duyet_ve_phieu(de_xuat_ten, doi_items_ap_dung)

    return {"trang_thai_moi": so.get("workflow_state"), "thay_doi": thay_doi}


def _dong_bo_so_luong_duyet_ve_phieu(ten_phieu: str, doi_items_ap_dung: dict[str, float]) -> None:
    """Task 9, Step 4b — ghi ngược `so_luong_duyet` lên phiếu đề xuất sau khi
    `portal_order_sua_so_luong` đã sửa Sales Order thành công.

    Chỉ chạm dòng THẬT SỰ đổi (`doi_items_ap_dung`, đã tính trong vòng lặp
    dựng `giu_items` ở trên) — không đụng field nào khác, kể cả khi `save()`
    dưới đây đi qua `_chan_sua_so_luong_de_xuat()`: guard đó chỉ khoá
    `so_luong_de_xuat`/`item_code`/xoá dòng, không khoá `so_luong_duyet`."""
    phieu = frappe.get_doc("Portal De Xuat Mua", ten_phieu)
    doi = False
    for row in phieu.items:
        if row.item_code in doi_items_ap_dung:
            row.so_luong_duyet = doi_items_ap_dung[row.item_code]
            doi = True
    if doi:
        phieu.save(ignore_permissions=True)


@frappe.whitelist()
def portal_order_huy(order, ly_do) -> dict:
    """Việc 2 / brief 2026-08-15 (bao-gia-hai-chieu) — nút Huỷ = HUỶ THẬT.

    Quyết định chủ dự án (brief, mục B): đơn ĐÓNG NGAY, email hai phía —
    khác hẳn `portal_request_cancel` cũ (chỉ ghi comment + ToDo, KHÔNG đóng
    đơn — khách bấm xong đơn vẫn hiện "chờ bạn đồng ý", tưởng chưa ăn).
    `portal_request_cancel` VẪN giữ nguyên cho đơn ĐÃ XÁC NHẬN (`docstatus`
    khác 0 không huỷ thẳng được qua đường này) — endpoint MỚI này chỉ phục
    vụ đúng đơn nháp đang "Chờ khách đồng ý".

    Chuyển sang state MỚI "Khách huỷ" (`patches/v1_18/mo_rong_workflow_
    khach_huy.py`) — KHÔNG tái dùng "Từ chối": state đó gắn Notification
    "Miyano đã từ chối đơn của bạn", dùng lại sẽ gửi sai thông điệp cho
    chính khách vừa tự huỷ (bài học đã trả giá, xem docstring patch).
    """
    dam_bao_xem_duoc("Sales Order", order)
    customer = get_portal_customer()
    so = frappe.get_doc("Sales Order", order)
    # `frappe.get_doc` KHÔNG tự kiểm quyền — phải tự đối chiếu `customer`
    # của đơn với khách suy từ PHIÊN, không nhận `customer` từ client.
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng này không thuộc đơn vị của bạn.")
    if so.get("workflow_state") != TRANG_THAI_CHO_KHACH:
        frappe.throw(
            "Chỉ huỷ được qua đây khi đơn đang chờ quý khách đồng ý. Đơn đã "
            "xác nhận, vui lòng dùng chức năng yêu cầu huỷ trên đơn.",
            frappe.ValidationError,
        )

    ly_do = (ly_do or "").strip()
    if len(ly_do) < LY_DO_TOI_THIEU_KHACH:
        frappe.throw(
            f"Vui lòng nêu lý do (tối thiểu {LY_DO_TOI_THIEU_KHACH} ký tự).",
            frappe.ValidationError,
        )

    nguoi_bam = frappe.session.user
    from frappe.model.workflow import apply_workflow

    # Cùng khuôn/lý do với `portal_order_accept` — transition "Khách huỷ"
    # chỉ mở cho "System Manager", không phải role Customer.
    session = frappe.local.session
    frappe.local.user_perms = None
    session.user = "Administrator"
    try:
        so = apply_workflow(so, "Khách huỷ")
        so.add_comment(
            "Comment", f"[Portal] Khách huỷ đơn bởi {nguoi_bam} — lý do: {ly_do}"
        )
    finally:
        session.user = nguoi_bam
        frappe.local.user_perms = None

    # US-E6.5 cùng khuôn — ghi vào cạnh "Khách huỷ" mà máy trạng thái
    # `Portal Item Request` đã dựng sẵn (CHUYEN_TRANG_THAI_HOP_LE, mọi
    # trạng thái đều cho phép chuyển sang "Khách huỷ"). Phòng thủ, không
    # ném lỗi (xem docstring `cap_nhat_yeu_cau_goc`).
    cap_nhat_yeu_cau_goc(so, "Khách huỷ")

    gui_email_khach_huy(so, ly_do)

    return {"trang_thai_moi": so.get("workflow_state")}


# ---------------------------------------------------------------- trang Thông báo
# Brief 2026-08-15 (trang thông báo) Phần 3 — dùng thẳng `Notification Log`
# có sẵn của Frappe (KHÔNG dựng doctype mới). Hai endpoint dưới đây KHÔNG
# nhận `user`/`customer` từ client — mọi thứ suy từ `frappe.session.user`.


def _lien_ket_thong_bao(document_type, document_name, customer) -> str | None:
    """Suy đường dẫn trong SPA cho một Notification Log, kiểm sở hữu CHÍNH
    chứng từ đang trỏ tới trước khi trả.

    `for_user` của Notification Log đã lọc đúng người nhận (người gọi truyền
    `customer` suy từ CHÍNH phiên đó), nhưng KHÔNG phải bằng chứng người đó
    có quyền đọc document đang trỏ tới — một bản ghi định tuyến sai (dữ liệu
    cũ, lỗi ở nơi khác) vẫn có thể mang `for_user` đúng mà `document_name`
    lại là chứng từ CỦA KHÁCH KHÁC. Đối chiếu lại `customer` của CHÍNH
    document trước khi trả link là lớp kiểm thứ hai, không phụ thuộc việc
    `for_user` đã lọc đúng hay chưa.

    Trả `None` khi không suy được / không map được loại chứng từ / không sở
    hữu — trang Thông báo vẫn hiện dòng chữ, chỉ ẩn nút đi tới chứng từ.
    """
    if not document_type or not document_name or not customer:
        return None
    try:
        if document_type == "Sales Order":
            if frappe.db.get_value("Sales Order", document_name, "customer") != customer:
                return None
            # Task 11 — đường CHÍNH TẮC của màn chi tiết đơn nay nằm dưới
            # `/yeu-cau`. `/orders/<name>` vẫn chuyển hướng đúng (router.js,
            # QĐ-G11) nên thông báo CŨ không gãy — nhưng thông báo MỚI phải
            # mang đường mới, không phải một đường sống nhờ lớp tương thích.
            return f"/yeu-cau/don/{document_name}"

        if document_type == "Sales Invoice":
            if frappe.db.get_value("Sales Invoice", document_name, "customer") != customer:
                return None
            # Cổng chưa có trang chi tiết một Sales Invoice riêng — "Hoá đơn &
            # công nợ" liệt kê tất cả, cùng khuôn brief (`v.v.` — minh hoạ,
            # không phải danh sách đóng).
            return "/invoices"

        if document_type == "Delivery Note":
            if frappe.db.get_value("Delivery Note", document_name, "customer") != customer:
                return None
            # Cổng không có trang chi tiết Delivery Note riêng — phiếu giao
            # hiện trong khối "Tiến trình giao hàng" của CHÍNH đơn hàng.
            so = frappe.db.get_value(
                "Delivery Note Item",
                {"parent": document_name, "against_sales_order": ["is", "set"]},
                "against_sales_order",
            )
            return f"/yeu-cau/don/{so}" if so else None

        if document_type == "Portal Delivery Inspection":
            r = frappe.db.get_value(
                "Portal Delivery Inspection", document_name,
                ["customer", "delivery_note"], as_dict=True,
            )
            # `not r` gộp cả "biên bản không còn tồn tại" lẫn "của khách
            # khác" — cùng khuôn nhánh Customer Stock Receipt bên dưới.
            if not r or r.customer != customer:
                return None
            return f"/kiem-hang/{r.delivery_note}"

        if document_type == "Customer Stock Receipt":
            kho = frappe.db.get_value("Customer Stock Receipt", document_name, "kho")
            # `not kho` gộp CẢ HAI: chứng từ không tồn tại (ví dụ phiếu nháp
            # đã bị `delivery_hook._huy_theo_delivery_note` xoá hẳn khi DN bị
            # huỷ — Notification Log trỏ tới một `document_name` không còn
            # nữa) VÀ chứng từ tồn tại nhưng không thuộc kho của khách này.
            kho_customer = frappe.db.get_value("Customer Warehouse", kho, "customer") if kho else None
            if not kho or kho_customer != customer:
                return None
            return f"/kho/nhap/{document_name}"
    except Exception:
        return None
    return None


def _customer_phien_hien_tai() -> str | None:
    """`get_portal_customer()` nhưng KHÔNG ném lỗi — trang Thông báo vẫn
    phải chạy được (chỉ mất khả năng suy link) cho một tài khoản lỗi cấu
    hình (chưa gắn Customer nào), thay vì 500 cả trang."""
    try:
        return get_portal_customer()
    except frappe.PermissionError:
        return None


def _pham_vi_phien_hien_tai() -> dict | None:
    """`pham_vi_don()` nhưng KHÔNG ném lỗi. Trả về MỘT TRONG BA, và người
    gọi PHẢI phân biệt cả ba (không được gộp bằng `if not pham_vi`):

    - `{}` — Quản lý, KHÔNG giới hạn theo khoa.
    - `{"custom_khoa_phong": ...}` — Nhân viên khoa, giới hạn đúng khoa đó.
    - `None` — KHÔNG xác định được phạm vi. Gồm cả tài khoản lỗi cấu hình
      (chưa gắn `Portal Member` nào) LẪN — quan trọng hơn — một Nhân viên
      khoa `active=1` CHƯA gán khoa, đúng ca `pham_vi_don()` cố ý fail-closed
      (`portal_context.py`, docstring "VÒNG SỬA 3").

    VÒNG SỬA 1 (review độc lập, I2 — Important): bản trước bắt
    `PermissionError` rồi trả `{}` — LẬT NGƯỢC fail-closed thành fail-open
    ĐÚNG Ở CA `pham_vi_don()` tồn tại để chặn. `None` khác `{}`: `bool(None)`
    và `bool({})` đều `False` trong Python — `if not pham_vi:` gộp nhầm hai
    ca này làm một chính là lỗi cũ, `_thong_bao_trong_pham_vi` bên dưới PHẢI
    kiểm `is None` tường minh."""
    try:
        return pham_vi_don()
    except frappe.PermissionError:
        return None


# `_lien_ket_thong_bao`/`dam_bao_xem_duoc` biết quy đúng ba doctype này về
# đơn cha. `Customer Stock Receipt`/`Portal Delivery Inspection` KHÔNG có
# mặt ở đây — CỐ Ý: kho là tài sản của CẢ bệnh viện, không thuộc riêng khoa
# nào (`Customer Warehouse` không gắn khoa phòng, xem thiết kế "kho khách
# hàng"), nên một thông báo "đã nhập hàng" là thông tin cấp bệnh viện, cùng
# hạng với `portal_catalog` — lọc nó theo khoa sẽ là lỗi, không phải một chỗ
# quên áp phạm vi.
_THONG_BAO_DOCTYPE_LOC_KHOA = ("Sales Order", "Delivery Note", "Sales Invoice")


def _thong_bao_trong_pham_vi(document_type, document_name, pham_vi: dict | None) -> bool:
    """`False` = ẨN CẢ DÒNG thông báo, không chỉ null hoá `link`.

    `_lien_ket_thong_bao` chỉ null `link` khi không sở hữu chứng từ đích —
    đủ để chặn NAVIGATE nhưng `subject` (vd. "Portal - Đơn mới: SAL-ORD-...")
    vẫn mang thẳng tên chứng từ ra ngoài. Với cách ly THEO KHOA, riêng
    `subject` đã là rò rỉ (một nhân viên khoa B đọc được "khoa A vừa có đơn
    SAL-ORD-2026-00099" dù không bấm vào xem được) — nên hàm này ẩn hẳn dòng
    thay vì chỉ tắt nút đi tới.

    `pham_vi is None` — VÒNG SỬA 1 (I2) — PHẢI kiểm TRƯỚC `not pham_vi`:
    `None` (không xác định được phạm vi, xem `_pham_vi_phien_hien_tai`) và
    `{}` (Quản lý, không giới hạn) đều `falsy` như nhau trong Python nhưng
    mang Ý NGHĨA NGƯỢC NHAU — gộp chúng bằng `if not pham_vi: return True`
    (bản trước) chính là lỗi lật fail-closed thành fail-open.

    Biết fan-out lúc TẠO thông báo (`portal_thong_bao_khach._portal_users_
    cua_khach`) hiện gửi cho MỌI thành viên đang active của khách hàng, chưa
    lọc theo khoa (docstring hàm đó tự ghi nhận, để dành việc đó cho phần mở
    rộng khác).

    SỬA (fix-wave 2026-08-18, V1 — CRITICAL): bản trước khẳng định "lọc Ở
    ĐÂY (đường đọc) vẫn đạt đúng mục tiêu cách ly" — SAI, và sai đúng loại
    "docstring hứa một tính chất an toàn mà mã không có" mà chính đề án này
    đã xếp Critical (xem C4 — `_loc_qua_don_cha`). Hàm này chỉ chặn ĐÚNG
    MỘT đường đọc: `portal_thong_bao_list`/`portal_thong_bao_doc`. `Notification
    Log` có DocPerm `read/report/export` cho role `All` (core), không phải
    bảng con nên `rest_guard`/`search_guard` không chặn — `frappe.get_list`/
    `frappe.client.get_value` gọi thẳng vẫn đi qua, BỎ QUA hàm này hoàn
    toàn. Ranh giới an ninh THẬT cho `Notification Log`, kể cả với nhân
    viên khoa gọi ngoài hai endpoint này, là hook `permission_query_
    conditions` (`permissions.notification_khoa_query`, đăng ký trong
    `hooks.py`) — hàm NÀY chỉ là một lớp ẨN THÊM (ẩn cả dòng thay vì chỉ
    null `link`) cho riêng hai màn Thông báo, không phải nguồn sự thật duy
    nhất."""
    if document_type not in _THONG_BAO_DOCTYPE_LOC_KHOA or not document_name:
        return True
    if pham_vi is None:
        # Fail-closed — không xác định được phạm vi thì KHÔNG được coi là
        # "Quản lý, thấy hết".
        return False
    if not pham_vi:
        return True
    try:
        # `pham_vi=pham_vi` — dùng LẠI giá trị đã tính MỘT LẦN cho cả trang
        # (không hỏi `pham_vi_don()` lại mỗi dòng thông báo).
        dam_bao_xem_duoc(document_type, document_name, pham_vi=pham_vi)
        return True
    except frappe.PermissionError:
        return False


@frappe.whitelist()
def portal_thong_bao_list(start=0, limit=20) -> dict:
    """Danh sách thông báo của CHÍNH khách đang đăng nhập + số chưa đọc cho
    badge nav. Lọc `for_user = frappe.session.user` — KHÔNG nhận user/
    customer từ client."""
    user = frappe.session.user
    start = frappe.utils.cint(start)
    limit = min(frappe.utils.cint(limit) or 20, 100)

    rows = frappe.get_all(
        "Notification Log",
        filters={"for_user": user},
        fields=[
            "name", "subject", "email_content", "document_type",
            "document_name", "read", "creation",
        ],
        order_by="creation desc",
        limit_start=start,
        limit_page_length=limit,
    )
    chua_doc = frappe.db.count("Notification Log", {"for_user": user, "read": 0})

    customer = _customer_phien_hien_tai()
    pham_vi = _pham_vi_phien_hien_tai()
    items = [
        {
            "name": r.name,
            "subject": r.subject,
            "noi_dung": r.email_content,
            "doc_type": r.document_type,
            "doc_name": r.document_name,
            "da_doc": bool(r.read),
            "ngay": r.creation,
            "link": _lien_ket_thong_bao(r.document_type, r.document_name, customer),
        }
        for r in rows
        if _thong_bao_trong_pham_vi(r.document_type, r.document_name, pham_vi)
    ]
    # `chua_doc` (badge nav) CỐ Ý chưa lọc theo khoa — đây là một CON SỐ,
    # không phải nội dung chứng từ; thu hẹp nó đòi kiểm dam_bao_xem_duoc trên
    # MỌI thông báo chưa đọc của user (không chỉ trang đang xem), một chi phí
    # không tương xứng với rủi ro (một con số badge, không phải tên/mã chứng
    # từ). Ghi nhận là giới hạn đã biết, không phải bị bỏ sót.
    return {"items": items, "chua_doc": chua_doc}


@frappe.whitelist()
def portal_thong_bao_doc(name) -> dict:
    """Bấm MỘT thông báo: kiểm sở hữu (chỉ đọc được thông báo CỦA CHÍNH
    mình — lọc `for_user` NGAY TRONG truy vấn, không load rồi kiểm sau),
    suy link (tự kiểm sở hữu chứng từ đích — xem `_lien_ket_thong_bao`), rồi
    đánh dấu đã đọc. KHÔNG nhận user từ client."""
    user = frappe.session.user
    log = frappe.db.get_value(
        "Notification Log",
        {"name": name, "for_user": user},
        ["name", "subject", "email_content", "document_type", "document_name", "read"],
        as_dict=True,
    )
    if not log:
        # Không tồn tại HOẶC thuộc `for_user` khác — cùng một câu trả lời để
        # không lộ ra sự khác biệt giữa hai trường hợp đó.
        raise frappe.PermissionError("Không tìm thấy thông báo.")

    pham_vi = _pham_vi_phien_hien_tai()
    if not _thong_bao_trong_pham_vi(log.document_type, log.document_name, pham_vi):
        # CÙNG thông điệp với "không tồn tại"/"thuộc user khác" ở trên —
        # nguyên tắc constraint #1: không phân biệt lý do để khỏi lộ sự tồn
        # tại của chứng từ đích.
        raise frappe.PermissionError("Không tìm thấy thông báo.")

    customer = _customer_phien_hien_tai()
    link = _lien_ket_thong_bao(log.document_type, log.document_name, customer)

    if not log.read:
        frappe.db.set_value("Notification Log", name, "read", 1, update_modified=False)

    return {
        "name": log.name,
        "subject": log.subject,
        "noi_dung": log.email_content,
        "doc_type": log.document_type,
        "doc_name": log.document_name,
        "link": link,
    }


# ------------------------------------------------------------ kiểm hàng (E9)
# Thiết kế: docs/superpowers/specs/2026-08-16-kiem-hang-tra-hang-hong-design.md
#
# Ba endpoint dưới đây KHÔNG nhận `customer` từ client — suy từ phiên, rồi đối
# chiếu với `customer` của CHÍNH Delivery Note đang được kiểm. `Portal Delivery
# Inspection` không có DocPerm nào cho role `Customer` (Quyết định #7), nên mọi
# thao tác đi qua đây với `ignore_permissions` sau khi đã tự kiểm sở hữu.


def _dn_kiem_hang_cua_khach(delivery_note: str, customer: str) -> frappe._dict:
    """Nạp phiếu giao và chứng minh nó thuộc khách đang đăng nhập.

    Kiểm CẢ `docstatus == 1`: một phiếu giao còn nháp thì hàng chưa rời kho
    Miyano, không có gì để kiểm; một phiếu đã huỷ thì đợt giao đó không tồn
    tại nữa. Cho lập biên bản trên hai loại đó sẽ sinh ra chứng từ khiếu nại
    về một lần giao hàng chưa/không hề xảy ra.
    """
    dam_bao_xem_duoc("Delivery Note", delivery_note)
    dn = frappe.db.get_value(
        "Delivery Note", delivery_note,
        ["name", "customer", "docstatus", "posting_date"], as_dict=True,
    )
    if not dn or dn.customer != customer:
        # Gộp "không tồn tại" và "của khách khác" vào một câu trả lời — không
        # để người gọi dò được sự tồn tại của chứng từ khách khác.
        raise frappe.PermissionError("Phiếu giao này không thuộc đơn vị của bạn.")
    if dn.docstatus != 1:
        frappe.throw(
            "Phiếu giao này chưa được ghi sổ hoặc đã huỷ.", frappe.ValidationError
        )
    return dn


@frappe.whitelist()
def portal_kiem_hang_get(delivery_note) -> dict:
    """Mở màn kiểm hàng: trả biên bản đã có, hoặc một biên bản TRỐNG dựng sẵn
    từ dòng hàng của phiếu giao (chưa lưu gì)."""
    customer = get_portal_customer()
    dn = _dn_kiem_hang_cua_khach(delivery_note, customer)

    # `dong_goc` — dòng dựng lại từ CHÍNH phiếu giao, luôn đi kèm. Sau một
    # lần bị từ chối, client cần một bộ dòng trắng để khách gõ lại mà không
    # phải gọi thêm một vòng API nữa.
    dong_goc = [{**d, "sl_thieu": 0.0} for d in dong_tu_delivery_note(delivery_note)]

    bien_ban = bien_ban_cua_dn(delivery_note)
    if bien_ban:
        return {"delivery_note": delivery_note, "ngay_giao": dn.posting_date,
                "bien_ban": bien_ban, "dong_goc": dong_goc, "moi": False}
    return {
        "delivery_note": delivery_note,
        "ngay_giao": dn.posting_date,
        "moi": True,
        "dong_goc": dong_goc,
        "bien_ban": {
            "name": None,
            "delivery_note": delivery_note,
            "trang_thai": "Nháp",
            "da_gui": False,
            "co_the_gui_lai": False,
            "co_hang_hong": False,
            "ly_do_tu_choi": None,
            "phieu_tra_hang": None,
            "ghi_chu": "",
            "items": list(dong_goc),
        },
    }


def _ap_dong_tu_client(doc, dong, delivery_note: str) -> None:
    """Ghi số liệu khách gửi lên vào `doc.items`.

    Dòng và mốc `sl_giao` LUÔN dựng lại từ chính Delivery Note, KHÔNG lấy từ
    payload: `sl_giao` là mốc đối chiếu: nhận nó từ client tức là để khách tự
    khai mình được giao bao nhiêu, và mọi ràng buộc "không nhận thừa" trong
    controller sẽ so với một con số do chính bên bị ràng buộc cung cấp. Client
    chỉ được đóng góp ba giá trị: `sl_nhan`, `sl_tra`, `ly_do`.
    """
    gui = {}
    for d in (dong or []):
        ma = (d.get("item_code") or "").strip()
        if ma:
            gui[ma] = d

    doc.items = []
    for goc in dong_tu_delivery_note(delivery_note):
        d = gui.get(goc["item_code"], {})
        doc.append("items", {
            "item_code": goc["item_code"],
            "item_name": goc["item_name"],
            "uom": goc["uom"],
            "sl_giao": goc["sl_giao"],
            "sl_nhan": frappe.utils.flt(d.get("sl_nhan", goc["sl_giao"])),
            "sl_tra": frappe.utils.flt(d.get("sl_tra", 0)),
            "ly_do": (d.get("ly_do") or "").strip()[:140],
        })


def _bien_ban_sua_duoc(delivery_note: str):
    """Bản nháp còn sửa được của phiếu giao này, hoặc None."""
    ten = frappe.db.get_value(
        "Portal Delivery Inspection",
        {"delivery_note": delivery_note, "docstatus": 0}, "name",
    )
    return frappe.get_doc("Portal Delivery Inspection", ten) if ten else None


def _chan_da_gui(delivery_note: str) -> None:
    """Đã gửi thì không sửa nữa — TRỪ bản bị Miyano từ chối.

    Bản từ chối vẫn là `docstatus=1`; không loại nó ra ở đây thì khách bị từ
    chối xong hết đường đi (spec §4.3 hứa ngược lại) — họ đọc "Liên hệ Miyano
    nếu cần chỉnh sửa" trên một màn khoá cứng.
    """
    da_gui = frappe.db.get_value(
        "Portal Delivery Inspection",
        # Hằng số, KHÔNG chuỗi viết tay: controller lọc cùng trạng thái này
        # bằng `TT_TU_CHOI`, hai bản chuỗi rời nhau là một chỗ trôi âm thầm
        # ngay lần đầu ai đó đổi tên trạng thái.
        {"delivery_note": delivery_note, "docstatus": 1,
         "trang_thai": ["!=", TT_TU_CHOI]},
        "name",
    )
    if da_gui:
        frappe.throw(
            f"Phiếu giao này đã có biên bản {da_gui} đã gửi. Liên hệ Miyano "
            "nếu cần chỉnh sửa.",
            frappe.ValidationError,
        )


@frappe.whitelist()
def portal_kiem_hang_luu(delivery_note, dong, ghi_chu=None) -> dict:
    """Lưu nháp — khách kiểm dở, đóng máy, mở lại vẫn còn."""
    customer = get_portal_customer()
    _dn_kiem_hang_cua_khach(delivery_note, customer)
    _chan_da_gui(delivery_note)
    if isinstance(dong, str):
        dong = frappe.parse_json(dong)

    doc = _bien_ban_sua_duoc(delivery_note)
    if not doc:
        doc = frappe.new_doc("Portal Delivery Inspection")
        doc.customer = customer
        doc.delivery_note = delivery_note
        doc.sales_order = frappe.db.get_value(
            "Delivery Note Item",
            {"parent": delivery_note, "against_sales_order": ["is", "set"]},
            "against_sales_order",
        )
    doc.ngay_kiem = frappe.utils.nowdate()
    doc.nguoi_kiem = frappe.session.user
    doc.trang_thai = "Nháp"
    doc.ghi_chu = (ghi_chu or "").strip()[:500]
    _ap_dong_tu_client(doc, dong, delivery_note)
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "trang_thai": doc.trang_thai}


@frappe.whitelist()
def portal_kiem_hang_gui(delivery_note, dong, ghi_chu=None) -> dict:
    """Gửi biên bản cho Miyano (submit).

    Lưu rồi submit trong CÙNG một lời gọi — không tin vào một bản nháp đã lưu
    từ trước: khách có thể mở hai tab, và bản nháp trên server có thể cũ hơn
    những gì họ đang nhìn thấy lúc bấm Gửi.
    """
    ket_qua = portal_kiem_hang_luu(delivery_note, dong, ghi_chu)
    doc = frappe.get_doc("Portal Delivery Inspection", ket_qua["name"])
    # Role `Customer` KHÔNG có DocPerm nào trên doctype này (Quyết định #7) —
    # cổng là chính endpoint này, đã tự kiểm sở hữu phiếu giao ở
    # `_dn_kiem_hang_cua_khach`. Không có cờ này thì `submit()` ném PermissionError cho
    # đúng người được phép gửi.
    doc.flags.ignore_permissions = True
    doc.submit()
    return {
        "name": doc.name,
        "trang_thai": doc.trang_thai,
        "co_hang_hong": bool(doc.co_hang_hong),
    }
