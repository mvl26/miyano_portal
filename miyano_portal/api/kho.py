"""Endpoint kho cho cổng khách hàng — CỔNG DUY NHẤT.

Nguyên tắc bất di bất dịch: KHÔNG endpoint nào nhận tên kho hay tên khách hàng
từ client. Kho luôn được suy ra từ phiên đăng nhập qua get_portal_kho(), và mọi
tham số do client gửi (ví dụ `vat_tu`) đều phải kiểm tra là thuộc kho đó.

Kể từ vòng 4, đây không còn là "cách khuyến nghị" mà là ĐƯỜNG DUY NHẤT còn lại:
role `Customer` đã bị gỡ hết DocPerm trên tám doctype kho, nên tài khoản portal
không thể đọc chúng qua get_list / REST / printview / frappe.client.* nữa (xem
khối comment trong hooks.py). Hệ quả trực tiếp cho file này:

  * Mọi truy vấn ở đây PHẢI an toàn nhờ CẤU TRÚC (lọc tường minh theo kho lấy
    từ phiên), không được trông cậy vào tầng phân quyền của framework — tầng đó
    giờ chỉ biết nói "không" cho user portal.
  * Vì thế `frappe.get_all` và `frappe.db.get_value` (cả hai đều BỎ QUA phân
    quyền) là lựa chọn đúng ở đây, không phải lỗ hổng: mỗi lời gọi đều bị ràng
    vào `kho` do get_portal_kho() trả về. Ngược lại, `frappe.get_list` sẽ chỉ
    ném PermissionError cho user portal — nếu ai đó dùng nó ở đây, endpoint sẽ
    vỡ, chứ không phải rò rỉ.
  * TUYỆT ĐỐI không "sửa" bằng ignore_permissions=True trên một truy vấn nhận
    định danh từ client mà chưa kiểm sở hữu. Định danh do client gửi phải đi
    qua một guard kiểu _vat_tu_cua_kho() trước.
"""

import functools

import frappe

from miyano_portal.kho import dong_phieu
from miyano_portal.kho import ledger
from miyano_portal.kho import import_ton_dau
from miyano_portal.kho import reports
from miyano_portal.kho import voucher
from miyano_portal.kho import vat_tu as vat_tu_mod
from miyano_portal.portal_context import get_portal_kho
from miyano_portal.setup.install_kho_print_formats import DEFAULT_NHAP, DEFAULT_XUAT

# Ba loại báo cáo hợp lệ cho kho_bao_cao_excel — danh sách trắng, giống hệt
# khuôn _LOAI_TO_DOCTYPE ở trên: tham số `loai` do client gửi không bao giờ
# được nội suy thẳng vào tên sheet/hàm mà không qua kiểm tra thành viên trước.
_BAO_CAO_LOAI = {"nxt", "the_kho", "canh_bao"}

# Ánh xạ tham số `loai` do client gửi ("nhap"/"xuat") sang doctype thật. Không
# bao giờ nhận thẳng tên doctype từ client cho các endpoint liệt kê — chỉ hai
# giá trị này được chấp nhận.
_LOAI_TO_DOCTYPE = {"nhap": "Customer Stock Receipt", "xuat": "Customer Stock Issue"}

# docstatus -> nhãn tiếng Việt hiển thị trên portal.
_TRANG_THAI = {0: "Nháp", 1: "Đã ghi sổ", 2: "Đã huỷ"}

_LOAI_FIELD = {
    "Customer Stock Receipt": "loai_nhap",
    "Customer Stock Issue": "loai_xuat",
}


def _so_nguyen(gia_tri, nhan: str, mac_dinh: int | None = None) -> int:
    """Ép một tham số whitelisted về số nguyên.

    Một client HTTP thật gửi tham số qua query string/form-data dưới dạng
    CHUỖI. `int("20")` chạy được nên phần lớn test hiện có vẫn xanh dù gọi
    thẳng bằng số nguyên Python, nhưng một client gửi `limit=abc` sẽ làm
    `int()` trần ném `ValueError`.

    QUAN TRỌNG — lý do các tham số dùng hàm này (`limit`, `start` của
    kho_phieu_list) KHÔNG được gắn type hint `int` trên chữ ký hàm: build này
    (Frappe v15.113) tự validate kiểu tham số của MỌI hàm whitelist có type
    hint, qua `frappe.utils.typing_validations.validate_argument_types`, và
    điều kiện kích hoạt là `in_request_or_test` — tức là chạy CẢ trong test,
    không chỉ khi có HTTP request thật (đã đo thực nghiệm: gọi thẳng
    `kho_phieu_list(loai, limit="abc")` trong test vẫn kích hoạt lớp này).
    Một giá trị không parse được thành `int` sẽ bị lớp đó chặn TRƯỚC KHI hàm
    này kịp chạy, và lỗi ném ra là `FrappeTypeError` với thông điệp TIẾNG ANH
    ("Argument 'limit' should be of type 'int'...") — vi phạm quy tắc "mọi
    lỗi ra tiếng Việt", và `_phieu_action` không cứu được vì lớp typing nằm
    NGOÀI nó. Bỏ type hint để tham số luôn tới tay hàm này ở dạng thô (chuỗi),
    rồi tự ép ở đây với thông điệp tiếng Việt — đúng khuôn mà `kho_lo_goi_y`/
    `kho_canh_bao_han` vốn đã dùng cho `so_luong`/`so_ngay` (cả hai tham số đó
    cũng cố ý không có type hint số, cùng một lý do).

    Rỗng/`None`: dùng `mac_dinh` nếu có, không thì báo thiếu tham số. Có giá
    trị nhưng không parse được thành số nguyên: báo lỗi tiếng Việt nêu đúng
    tên tham số, không bao giờ để `ValueError` lọt ra ngoài.
    """
    if gia_tri in (None, ""):
        if mac_dinh is not None:
            return mac_dinh
        frappe.throw(f"Thiếu {nhan}.", frappe.ValidationError)
    try:
        return int(gia_tri)
    except (TypeError, ValueError):
        frappe.throw(f"{nhan} không hợp lệ.", frappe.ValidationError)


def _so_thuc(gia_tri, nhan: str) -> float:
    """Bản số thực của _so_nguyen(), dùng cho tham số có thể có phần lẻ
    (số lượng). Không có `mac_dinh`: các tham số dùng hàm này trong module là
    tham số bắt buộc, thiếu thì cũng là một giá trị "không hợp lệ"."""
    try:
        return float(gia_tri)
    except (TypeError, ValueError):
        frappe.throw(f"{nhan} không hợp lệ.", frappe.ValidationError)


def _doctype_tu_loai(loai: str) -> str:
    dt = _LOAI_TO_DOCTYPE.get(loai)
    if not dt:
        frappe.throw(
            "Loại phiếu không hợp lệ. Chỉ chấp nhận \"nhap\" hoặc \"xuat\".",
            frappe.ValidationError,
        )
    return dt


def _phieu_cua_kho(doctype: str, name: str, kho: str) -> None:
    """Xác nhận một PHIẾU (nhập hoặc xuất) do client gửi tên đúng là của kho
    người gọi, TRƯỚC khi bất kỳ frappe.get_doc/db.get_value nào khác chạm vào
    nó. Cùng khuôn với _vat_tu_cua_kho(): frappe.get_doc không tự kiểm
    has_permission ở build này.

    `doctype` cũng do client gửi ở các endpoint kho_phieu_* (theo đúng chữ ký
    trong yêu cầu) — kiểm nó nằm trong danh sách trắng TRƯỚC, nếu không
    kho_phieu_submit(doctype, name) sẽ là một cách gọi submit() trên BẤT KỲ
    doctype submittable nào trên site.

    Tên không tồn tại thì frappe.db.get_value trả None, tự động khác `kho` và
    rơi vào đúng nhánh PermissionError tiếng Việt bên dưới — không bao giờ lộ
    ra DoesNotExistError bằng tiếng Anh nêu tên doctype.
    """
    if doctype not in voucher.VOUCHER_DOCTYPES:
        frappe.throw("Loại chứng từ không hợp lệ.", frappe.ValidationError)
    if not name or frappe.db.get_value(doctype, name, "kho") != kho:
        raise frappe.PermissionError("Phiếu không thuộc kho của đơn vị bạn.")


def _action(danh_tu: str):
    """Nhà máy sinh decorator bọc lỗi cho endpoint cổng, tham số hoá bằng DANH TỪ
    của thứ đang được xử lý ("phiếu", "vật tư").

    Mọi ngoại lệ KHÔNG PHẢI lỗi nghiệp vụ của chính chúng ta (ValidationError
    do voucher.py/controller ném ra với thông điệp tiếng Việt đã soạn sẵn, hoặc
    PermissionError của các guard cách ly) phải được dịch sang một thông điệp
    tiếng Việt chung chung trước khi tới người dùng — không bao giờ để lộ
    traceback hay tên lớp lỗi tiếng Anh của framework. Lỗi gốc vẫn được ghi
    vào Error Log để nhân viên kỹ thuật tra được.

    Danh từ là tham số chứ không phải chuỗi cứng "phiếu" vì các endpoint danh
    mục vật tư (kho_vat_tu_*) dùng CHUNG lớp bọc này: một câu "Có lỗi xảy ra khi
    xử lý phiếu" hiện ra lúc người dùng đang nhập DANH MỤC khiến họ đi tìm phiếu
    nào vừa hỏng, và tệ hơn là báo sai cho nhân viên hỗ trợ.

    Lưu ý cho endpoint trả tệp (kho_*_export, kho_dong_phieu_mau): wrapper chỉ
    chuyển tiếp giá trị trả về, KHÔNG đụng tới frappe.local.response — cơ chế
    tải tệp (response.type = "download") vẫn chạy nguyên vẹn qua lớp bọc.
    """

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (frappe.ValidationError, frappe.PermissionError):
                raise
            except Exception:
                frappe.log_error(title=f"kho: lỗi trong {fn.__name__}")
                frappe.throw(
                    f"Có lỗi xảy ra khi xử lý {danh_tu}. Vui lòng thử lại hoặc "
                    "liên hệ nhân viên kinh doanh Miyano.",
                    frappe.ValidationError,
                )

        return wrapper

    return deco


# Hai lớp bọc đang dùng. Tên `_phieu_action` giữ nguyên vì đã có mười endpoint
# và nhiều test tham chiếu tới nó.
_phieu_action = _action("phiếu")
_vat_tu_action = _action("vật tư")


def _vat_tu_cua_kho(vat_tu: str, kho: str) -> str:
	"""Xác nhận một vật tư do client gửi lên đúng là của kho người gọi.

	frappe.get_doc KHÔNG tự chạy hook has_permission ở build này (xem
	api/portal.py:351), nên không thể tin vào việc nạp doc là đủ an toàn.
	"""
	if frappe.db.get_value("Customer Warehouse Item", vat_tu, "kho") != kho:
		raise frappe.PermissionError("Vật tư không thuộc kho của đơn vị bạn.")
	return vat_tu


@frappe.whitelist()
def kho_me() -> dict:
	kho = get_portal_kho()
	row = frappe.db.get_value(
		"Customer Warehouse", kho,
		["name", "ten_kho", "ma_kho", "thu_kho", "customer", "ngay_bat_dau"],
		as_dict=True,
	)
	return {
		"kho": row.name,
		"ten_kho": row.ten_kho,
		"ma_kho": row.ma_kho,
		"thu_kho": row.thu_kho or "",
		"customer": row.customer,
		"customer_name": frappe.db.get_value(
			"Customer", row.customer, "customer_name"
		),
		"ngay_bat_dau": row.ngay_bat_dau,
	}


@frappe.whitelist()
def kho_ton(tim=None) -> list:
	"""Tồn hiện tại, gộp các lô về một dòng cho mỗi vật tư.

	Phép gộp thật sự sống ở `reports.ton_hien_tai_rows()` — dùng chung với báo
	cáo "Tồn kho khách hàng" phía desk (Phase 6), vốn gọi lại đúng hàm này cho
	từng kho rồi gắn thêm khách hàng, chứ không viết lại phép cộng lần hai."""
	return reports.ton_hien_tai_rows(get_portal_kho(), tim)


@frappe.whitelist()
def kho_lo(vat_tu) -> list:
	"""Các lô còn tồn của một vật tư, thứ tự FEFO."""
	kho = get_portal_kho()
	_vat_tu_cua_kho(vat_tu, kho)
	# ledger.get_lot_balances() cũng trả `name` (docname nội bộ của Customer
	# Stock Lot Balance) — bỏ trước khi trả ra ngoài. Đây chính là loại định
	# danh do client cầm trong tay mà nguyên tắc đầu file cảnh báo: một
	# endpoint sau này (ví dụ chi tiết một lô, in phiếu) rất dễ vô tình nhận
	# nó làm tham số rồi tin nó thuộc đúng kho mà không kiểm lại.
	return [{k: v for k, v in row.items() if k != "name"} for row in ledger.get_lot_balances(kho, vat_tu)]


@frappe.whitelist()
def kho_vat_tu_list(tim=None, ca_tat=0) -> list:
	"""Danh mục vật tư của kho — nguồn cho ô chọn vật tư ở hai màn phiếu VÀ
	cho màn danh mục.

	`ca_tat` CỐ Ý không có type hint (xem _so_nguyen): tham số số có type hint
	bị lớp typing của Frappe chặn bằng thông điệp tiếng Anh trước khi hàm chạy.
	Mặc định 0 nên hành vi cũ (chỉ trả vật tư đang dùng) giữ nguyên cho hai màn
	phiếu vốn gọi hàm này không tham số.
	"""
	kho = get_portal_kho()
	filters = {"kho": kho}
	if not _so_nguyen(ca_tat, "Tham số hiển thị vật tư đã tắt", 0):
		filters["active"] = 1
	rows = frappe.get_all(
		"Customer Warehouse Item",
		filters=filters,
		fields=["name", "ma_vat_tu", "ten_vat_tu", "dvt", "item_code",
		        "quy_cach", "nhom", "ghi_chu", "active"],
		order_by="ten_vat_tu asc",
	)
	if tim:
		hay = str(tim).strip().lower()
		rows = [r for r in rows if hay in f"{r['ma_vat_tu']} {r['ten_vat_tu']}".lower()]
	# MỘT truy vấn cho cả danh mục, không phải mỗi dòng một truy vấn.
	co_ps = vat_tu_mod.cac_vat_tu_co_phat_sinh(kho)
	for r in rows:
		vat_tu_mod._chuan_hoa_row(r)
		r["co_phat_sinh"] = r["name"] in co_ps
	return rows


@frappe.whitelist()
@_vat_tu_action
def kho_vat_tu_tao(payload) -> dict:
	"""Tạo một vật tư trong kho của người gọi.

	`kho` lấy từ phiên; `item_code` KHÔNG nhận từ client mà do vat_tu.tao() tự
	suy từ mã — nhận item_code từ client cho phép khách nối vật tư của mình vào
	một mặt hàng Miyano bất kỳ, và từ đó hook Delivery Note cộng hàng vào đúng
	dòng danh mục sai đó.
	"""
	kho = get_portal_kho()
	return vat_tu_mod.tao(kho, _parse_payload(payload))


@frappe.whitelist()
@_vat_tu_action
def kho_vat_tu_sua(name: str, payload) -> dict:
	kho = get_portal_kho()
	_vat_tu_cua_kho(name, kho)
	return vat_tu_mod.sua(kho, name, _parse_payload(payload))


@frappe.whitelist()
@_vat_tu_action
def kho_vat_tu_export() -> None:
	kho = get_portal_kho()
	frappe.local.response.filename = "danh_muc_vat_tu.xlsx"
	frappe.local.response.filecontent = vat_tu_mod.build_danh_muc_xlsx(kho)
	frappe.local.response.type = "download"
	frappe.local.response.content_type = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)


@frappe.whitelist()
@_vat_tu_action
def kho_vat_tu_import_preview(file_url) -> dict:
	"""Đọc và phân tích file danh mục, KHÔNG GHI GÌ."""
	kho = get_portal_kho()
	content = _resolve_owned_spreadsheet(file_url)
	return vat_tu_mod.parse_danh_muc(content, kho)


@frappe.whitelist()
@_vat_tu_action
def kho_vat_tu_import_commit(file_url) -> dict:
	"""Đọc lại VÀ kiểm tra lại từ đầu ở server rồi mới ghi."""
	kho = get_portal_kho()
	content = _resolve_owned_spreadsheet(file_url)
	return vat_tu_mod.commit_danh_muc(content, kho)


def _resolve_owned_spreadsheet(file_url: str) -> bytes:
	"""Nạp nội dung một file .xlsx do CHÍNH người gọi vừa upload.

	`frappe.get_doc` không tự kiểm has_permission (xem khối comment đầu file),
	nên không thể tin việc nạp doc là đủ an toàn — đặc biệt ở đây, nơi
	`file_url` đến thẳng từ tham số client gửi. Sở hữu được xác nhận bằng so
	sánh `owner` tường minh, không phải bằng check_permission() (File dùng
	tầng quyền chung của Frappe, không thuộc nhóm doctype kho bị gỡ quyền).

	Tra `name` bằng `frappe.db.get_value` TRƯỚC khi gọi `frappe.get_doc`: một
	`file_url` không tồn tại (tệp đã bị xoá, tab cũ gửi lại, hoặc client tự bịa)
	khiến `frappe.get_doc("File", {...})` ném `DoesNotExistError` với thông điệp
	tiếng Anh nêu thẳng tên doctype — vi phạm quy tắc "mọi lỗi ra tiếng Việt,
	không lộ tên doctype". Bắt sớm để luôn trả thông điệp tiếng Việt của riêng
	hàm này.
	"""
	if not file_url:
		frappe.throw("Thiếu tệp để nhập.", frappe.ValidationError)
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(
			"Không tìm thấy tệp đã tải lên. Vui lòng chọn lại tệp và thử lại.",
			frappe.ValidationError,
		)
	file_doc = frappe.get_doc("File", file_name)
	if file_doc.owner != frappe.session.user:
		raise frappe.PermissionError("Bạn không có quyền đọc tệp này.")
	if not (file_doc.file_name or "").lower().endswith(".xlsx"):
		frappe.throw("Vui lòng chọn tệp .xlsx đúng định dạng.", frappe.ValidationError)
	try:
		content = file_doc.get_content()
	except Exception:
		frappe.throw("Không đọc được tệp đã tải lên.", frappe.ValidationError)
	if isinstance(content, str):
		content = content.encode("utf-8")
	return content


@frappe.whitelist()
def kho_import_template() -> None:
	"""Tải file mẫu import danh mục + tồn đầu kỳ. get_portal_kho() vẫn được
	gọi dù không dùng kết quả, để nhất quán "mọi endpoint đều tự suy kho từ
	phiên" với hai endpoint preview/commit — khách chưa mở kho nhận cùng một
	thông báo tiếng Việt ở cả ba endpoint thay vì tải mẫu được nhưng preview
	thì bị chặn.
	"""
	get_portal_kho()
	frappe.local.response.filename = "mau_nhap_ton_dau_kho.xlsx"
	frappe.local.response.filecontent = import_ton_dau.build_template_bytes()
	frappe.local.response.type = "download"
	frappe.local.response.content_type = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)


@frappe.whitelist()
def kho_import_preview(file_url) -> dict:
	"""Đọc và phân tích file, KHÔNG GHI GÌ. Xem import_ton_dau.parse_workbook."""
	kho = get_portal_kho()
	content = _resolve_owned_spreadsheet(file_url)
	return import_ton_dau.parse_workbook(content, kho)


@frappe.whitelist()
def kho_import_commit(file_url) -> dict:
	"""Đọc lại VÀ kiểm tra lại từ đầu ở server rồi mới ghi — không tin bất kỳ
	dòng dữ liệu nào mà client (đã gọi preview trước đó) có thể gửi kèm."""
	kho = get_portal_kho()
	content = _resolve_owned_spreadsheet(file_url)
	return import_ton_dau.commit_workbook(content, kho)


# ---------------------------------------------------------------------------
# Phiếu nhập / xuất kho (Phase 3): danh sách, chi tiết, tạo/sửa nháp, ghi sổ,
# huỷ, gợi ý lô FEFO, in PDF.
# ---------------------------------------------------------------------------


def _phieu_to_dict(doc) -> dict:
	out = doc.as_dict()
	# as_dict() giữ nguyên mọi field nội bộ (owner, creation, docstatus dạng
	# DocStatus...). Portal chỉ cần các field hiển thị — không có gì nhạy cảm
	# ở đây (đây là DỮ LIỆU CỦA CHÍNH NGƯỜI GỌI, đã qua _phieu_cua_kho), nhưng
	# vẫn ép docstatus về int thường để JSON hoá gọn và thêm nhãn trạng thái.
	out["docstatus"] = int(doc.docstatus)
	out["trang_thai"] = _TRANG_THAI.get(int(doc.docstatus), "")
	out["items"] = [row.as_dict() for row in doc.items]
	return out


@frappe.whitelist()
@_phieu_action
def kho_phieu_list(loai: str, limit=20, start=0) -> list:
	# `limit`/`start` CỐ Ý không gắn type hint `int`: build này (Frappe
	# v15.113) tự validate kiểu tham số của hàm whitelist theo type hint qua
	# `frappe.utils.typing_validations` — kể cả khi gọi trực tiếp trong test
	# (điều kiện kích hoạt là `in_request_or_test`, không phải chỉ HTTP thật).
	# Nếu khai `limit: int`, một giá trị không parse được sẽ bị chặn ở lớp đó
	# TRƯỚC KHI hàm này chạy, và lỗi ném ra là `FrappeTypeError` với thông điệp
	# TIẾNG ANH ("Argument 'limit' should be of type...") — vi phạm quy tắc
	# "mọi lỗi ra tiếng Việt" của cả dự án, và `_phieu_action` không cứu được
	# vì lớp đó nằm NGOÀI nó. Bỏ type hint để tham số tới tay hàm ở dạng thô,
	# rồi tự ép bằng `_so_nguyen()` bên dưới với thông điệp tiếng Việt — đúng
	# khuôn mà `kho_lo_goi_y`/`kho_canh_bao_han` đã dùng cho `so_luong`/`so_ngay`.
	kho = get_portal_kho()
	doctype = _doctype_tu_loai(loai)
	loai_field = _LOAI_FIELD[doctype]
	fields = ["name", "ngay", loai_field, "tong_tien", "docstatus", "modified"]
	if doctype == "Customer Stock Receipt":
		fields.append("nguoi_giao")
	else:
		fields += ["noi_nhan", "nguoi_nhan"]
	rows = frappe.get_all(
		doctype,
		filters={"kho": kho},
		fields=fields,
		order_by="creation desc",
		limit_page_length=_so_nguyen(limit, "Số dòng mỗi trang", 20),
		limit_start=_so_nguyen(start, "Vị trí bắt đầu", 0),
	)
	for row in rows:
		row["trang_thai"] = _TRANG_THAI.get(int(row["docstatus"]), "")
	return rows


@frappe.whitelist()
@_phieu_action
def kho_phieu_get(doctype: str, name: str) -> dict:
	kho = get_portal_kho()
	_phieu_cua_kho(doctype, name, kho)
	doc = frappe.get_doc(doctype, name)
	return _phieu_to_dict(doc)


def _parse_payload(payload) -> dict:
	if isinstance(payload, str):
		payload = frappe.parse_json(payload)
	if not isinstance(payload, dict):
		frappe.throw("Dữ liệu phiếu không hợp lệ.", frappe.ValidationError)
	return payload


def _validate_items_present(items) -> list:
	if not items:
		frappe.throw("Phiếu phải có ít nhất một dòng vật tư.", frappe.ValidationError)
	for idx, row in enumerate(items, start=1):
		if not (row.get("vat_tu") if isinstance(row, dict) else row.vat_tu):
			frappe.throw(f"Dòng {idx}: chưa chọn vật tư.", frappe.ValidationError)
		if not (row.get("so_lo") if isinstance(row, dict) else row.so_lo):
			frappe.throw(f"Dòng {idx}: chưa nhập số lô.", frappe.ValidationError)
	return items


@frappe.whitelist()
@_phieu_action
def kho_phieu_nhap_save(payload) -> dict:
	kho = get_portal_kho()
	payload = _parse_payload(payload)
	name = payload.get("name")

	if name:
		_phieu_cua_kho("Customer Stock Receipt", name, kho)
		doc = frappe.get_doc("Customer Stock Receipt", name)
		if doc.docstatus != 0:
			frappe.throw(
				"Phiếu đã được ghi sổ hoặc đã huỷ, không thể sửa. Chỉ có thể "
				"sửa khi phiếu còn ở trạng thái nháp.",
				frappe.ValidationError,
			)
	else:
		doc = frappe.new_doc("Customer Stock Receipt")

	items = _validate_items_present(payload.get("items"))

	# `kho` LUÔN lấy từ phiên đăng nhập, không bao giờ từ payload — kể cả khi
	# client cố tình gửi kèm kho của khách khác.
	doc.kho = kho
	doc.ngay = payload.get("ngay") or doc.ngay or frappe.utils.today()
	doc.loai_nhap = payload.get("loai_nhap") or doc.loai_nhap or "Nhập khác"
	doc.nguoi_giao = payload.get("nguoi_giao")
	doc.chung_tu_kem = payload.get("chung_tu_kem")
	doc.dien_giai = payload.get("dien_giai")

	# `sl_giao`/`thieu_lo_han` (US-E3.2, BR-K16) là mốc đối soát do
	# delivery_hook điền, KHÔNG BAO GIỜ nhận từ client — cùng nguyên tắc với
	# don_gia/han_su_dung của phiếu xuất bên dưới (kho_phieu_xuat_save). Nhưng
	# vòng lặp này XOÁ SẠCH bảng dòng cũ rồi dựng lại hoàn toàn từ payload, nên
	# nếu không tự khôi phục thì mốc đó BIẾN MẤT ngay lần đầu thủ kho sửa
	# so_luong rồi lưu nháp — vỡ chốt chặn BR-K17 (sl_giao về 0 khiến dòng bị
	# coi là "không thuộc nguồn Miyano", bỏ qua kiểm tra thay vì chặn đúng lúc
	# cần).
	#
	# Khớp theo `name` của DÒNG CON (danh tính thật, không giả được — client
	# nhận nó từ chính lần load trước qua _phieu_to_dict()), KHÔNG PHẢI theo
	# giá trị (vat_tu, so_lo) như bản trước. Bản trước có hai lỗ:
	#   1. Thủ kho sửa Số lô (ví dụ gõ số lô in trên thùng thay cho KHONG-LO)
	#      → khoá không còn khớp → sl_giao rơi về 0 ÂM THẦM, tắt vĩnh viễn
	#      BR-K17 cho dòng đó (không cảnh báo gì — sổ append-only, không sửa
	#      lại được sau khi ghi sổ).
	#   2. Hook có thể sinh HAI dòng cùng (vat_tu, so_lo) thật (hai dòng DN
	#      khác giá/khác SO gộp lô) — `cu.pop(0)` gán mốc của dòng ĐẦU cho bất
	#      kỳ dòng nào khớp giá trị, kể cả khi thủ kho xoá dòng đầu và dòng
	#      còn lại đáng lẽ mang mốc khác.
	# `name` không đổi dù thủ kho sửa vat_tu/so_lo/so_luong — chỉ đổi khi dòng
	# đó thật sự bị xoá. Dòng KHÔNG có `name` trong payload (mới thêm tay/nhập
	# Excel) không khớp gì cả → sl_giao=0 đúng nghĩa "không có mốc", nhất quán
	# cho cả trường hợp thêm dòng mới thật lẫn trường hợp thủ kho xoá dòng
	# hook sinh rồi gõ tay lại "y hệt" — đó KHÔNG PHẢI cùng một dòng nữa.
	moc_doi_soat_cu: dict[str, dict] = {
		r.name: {"sl_giao": r.sl_giao, "thieu_lo_han": r.thieu_lo_han}
		for r in doc.items
	}

	# C1 (BR-K17 bị vô hiệu qua nút xoá dòng): payload đánh rơi một dòng đã có
	# sl_giao > 0 (tức nguồn Miyano — hook điền) là thủ kho vừa bấm ✕ xoá nó.
	# Hàng biến mất khỏi chứng từ NGAY CẢ KHI thủ kho không cố ý lách luật —
	# đây là lối tắt DUY NHẤT còn lại để tránh chốt chặn BR-K17 khi hàng thật
	# sự bị thiếu/mất hoàn toàn (0 đơn vị), vì trước đây _check_so_luong không
	# cho ghi so_luong=0. Kể từ bản này so_luong=0 được PHÉP cho dòng có
	# sl_giao > 0 (xem voucher._check_so_luong) — "nhận 0" giờ đi qua đúng
	# đường BR-K17 (bắt lý do, hiện trên report), không phải qua đường xoá
	# dòng làm biến mất mọi dấu vết. Kiểm TRƯỚC khi wipe doc.items.
	ten_con_trong_payload = {row.get("name") for row in items if row.get("name")}
	for r in doc.items:
		if float(r.sl_giao or 0) > 0 and r.name not in ten_con_trong_payload:
			frappe.throw(
				f"Dòng {r.idx} ({r.ten_vat_tu or r.vat_tu}): không được xoá dòng "
				"do phiếu giao hàng sinh ra. Nhận thiếu/mất hoàn toàn thì ghi "
				"số lượng 0 và nêu lý do chênh lệch, đừng xoá dòng — xoá sẽ làm "
				"mất dấu vết, hàng coi như chưa từng được giao.",
				frappe.ValidationError,
			)

	doc.set("items", [])
	for row in items:
		ten = row.get("name")
		# Chỉ tin `ten` khi nó khớp một dòng ĐANG THẬT SỰ có trong doc.items
		# vừa load (moc_doi_soat_cu dựng từ đó) — một `name` lạ/cũ (đã đổi từ
		# vòng lưu trước, xem lý do trong dòng_moi bên dưới) không được coi
		# là hợp lệ, rơi về nhánh "dòng mới" cho an toàn.
		giu_lai = moc_doi_soat_cu.get(ten)
		dong_moi = {
			"vat_tu": row.get("vat_tu"),
			"so_lo": row.get("so_lo"),
			"han_su_dung": row.get("han_su_dung"),
			"so_luong": row.get("so_luong"),
			"don_gia": row.get("don_gia"),
			"ghi_chu": row.get("ghi_chu"),
			"ly_do_chenh_lech": row.get("ly_do_chenh_lech"),
			"sl_giao": (giu_lai or {}).get("sl_giao"),
			"thieu_lo_han": (giu_lai or {}).get("thieu_lo_han"),
		}
		if giu_lai is not None:
			# QUAN TRỌNG: giữ lại `name` gốc khi append lại — không giữ thì
			# Frappe sinh `name` MỚI cho MỌI dòng ở MỖI lần lưu (vòng lặp này
			# luôn wipe rồi dựng lại toàn bộ bảng dòng), khiến định danh dòng
			# không ổn định qua hai lần gọi liên tiếp. Client vẫn hoạt động
			# đúng (Vue luôn ghi đè doc.items bằng đúng response mới nhất sau
			# mỗi lần lưu — xem save() trong PhieuNhapDetail.vue), nhưng nếu
			# name đổi mà không được lưu ổn định, chốt chặn "xoá dòng" phía
			# trên (C1) sẽ nhận NHẦM một dòng CÒN NGUYÊN là "vừa bị xoá" ngay
			# ở lần lưu tiếp theo — tự mình gây ra chính lỗ hổng C1 định vá.
			dong_moi["name"] = ten
		doc.append("items", dong_moi)

	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return _phieu_to_dict(doc)


@frappe.whitelist()
@_phieu_action
def kho_phieu_xuat_save(payload) -> dict:
	kho = get_portal_kho()
	payload = _parse_payload(payload)
	name = payload.get("name")

	if name:
		_phieu_cua_kho("Customer Stock Issue", name, kho)
		doc = frappe.get_doc("Customer Stock Issue", name)
		if doc.docstatus != 0:
			frappe.throw(
				"Phiếu đã được ghi sổ hoặc đã huỷ, không thể sửa. Chỉ có thể "
				"sửa khi phiếu còn ở trạng thái nháp.",
				frappe.ValidationError,
			)
	else:
		doc = frappe.new_doc("Customer Stock Issue")

	items = _validate_items_present(payload.get("items"))

	doc.kho = kho
	doc.ngay = payload.get("ngay") or doc.ngay or frappe.utils.today()
	doc.loai_xuat = payload.get("loai_xuat") or doc.loai_xuat or "Xuất sử dụng"
	doc.noi_nhan = payload.get("noi_nhan")
	doc.nguoi_nhan = payload.get("nguoi_nhan")
	doc.dien_giai = payload.get("dien_giai")

	doc.set("items", [])
	for row in items:
		# don_gia và han_su_dung KHÔNG nhận từ client dù có gửi kèm: controller
		# (_lay_gia_va_han_tu_lo) luôn ghi đè bằng giá/hạn hiện hành của lô ở
		# validate(), đúng như test_price_taken_from_lot_not_user đã khẳng định.
		doc.append("items", {
			"vat_tu": row.get("vat_tu"),
			"so_lo": row.get("so_lo"),
			"so_luong": row.get("so_luong"),
			"xac_nhan_het_han": 1 if row.get("xac_nhan_het_han") else 0,
			"ghi_chu": row.get("ghi_chu"),
		})

	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return _phieu_to_dict(doc)


@frappe.whitelist()
@_phieu_action
def kho_phieu_submit(doctype: str, name: str) -> dict:
	kho = get_portal_kho()
	_phieu_cua_kho(doctype, name, kho)
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus != 0:
		frappe.throw(
			"Chỉ có thể ghi sổ phiếu đang ở trạng thái nháp.",
			frappe.ValidationError,
		)
	doc.flags.ignore_permissions = True
	doc.submit()
	return _phieu_to_dict(doc)


@frappe.whitelist()
@_phieu_action
def kho_phieu_cancel(doctype: str, name: str) -> dict:
	kho = get_portal_kho()
	_phieu_cua_kho(doctype, name, kho)
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus != 1:
		frappe.throw(
			"Chỉ có thể huỷ phiếu đã được ghi sổ.", frappe.ValidationError
		)
	doc.flags.ignore_permissions = True
	doc.cancel()
	return _phieu_to_dict(doc)


@frappe.whitelist()
@_phieu_action
def kho_dong_phieu_mau(loai: str) -> None:
	"""Tệp .xlsx rỗng đúng bộ cột của loại phiếu, để khách điền rồi nạp vào."""
	get_portal_kho()  # khách chưa mở kho nhận cùng thông báo như mọi endpoint kho
	frappe.local.response.filename = f"mau_dong_phieu_{loai}.xlsx"
	frappe.local.response.filecontent = dong_phieu.build_mau_xlsx(loai)
	frappe.local.response.type = "download"
	frappe.local.response.content_type = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)


@frappe.whitelist()
@_phieu_action
def kho_dong_phieu_doc_file(loai: str, file_url) -> dict:
	"""Đọc tệp thành các dòng phiếu. KHÔNG GHI GÌ — việc ghi vẫn đi qua
	kho_phieu_nhap_save / kho_phieu_xuat_save như dòng gõ tay."""
	kho = get_portal_kho()
	content = _resolve_owned_spreadsheet(file_url)
	return dong_phieu.doc_file(content, kho, loai)


@frappe.whitelist()
@_phieu_action
def kho_dong_phieu_export(doctype: str, name: str) -> None:
	kho = get_portal_kho()
	_phieu_cua_kho(doctype, name, kho)
	frappe.local.response.filename = f"{name}-dong.xlsx"
	frappe.local.response.filecontent = dong_phieu.build_export_xlsx(doctype, name)
	frappe.local.response.type = "download"
	frappe.local.response.content_type = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)


@frappe.whitelist()
@_phieu_action
def kho_lo_goi_y(vat_tu: str, so_luong) -> dict:
	"""Gợi ý lô theo FEFO cho một dòng xuất: đi từ lô hết hạn gần nhất, lô
	không có hạn xếp cuối (ledger.get_lot_balances đã sắp đúng thứ tự này),
	và phân bổ tham lam (greedy) số lượng cần xuất qua từng lô cho tới khi đủ.

	Đây CHỈ là gợi ý hiển thị trên form — không ném lỗi khi không đủ tồn, vì
	người dùng có thể đang xem trước hoặc sẽ đổi số lượng; chốt chặn thật nằm
	ở before_submit của Customer Stock Issue (_chan_xuat_qua_ton).
	"""
	kho = get_portal_kho()
	_vat_tu_cua_kho(vat_tu, kho)
	can = _so_thuc(so_luong, "Số lượng")
	if can < 0:
		frappe.throw("Số lượng không hợp lệ.", frappe.ValidationError)

	hom_nay = frappe.utils.getdate(frappe.utils.today())
	con_lai = can
	lots = []
	for lot in ledger.get_lot_balances(kho, vat_tu):
		ton = float(lot["so_luong"])
		de_xuat = min(con_lai, ton) if con_lai > 0 else 0.0
		con_lai = max(0.0, con_lai - de_xuat)
		han = lot["han_su_dung"]
		lots.append({
			"so_lo": lot["so_lo"],
			"han_su_dung": han,
			"so_luong_ton": ton,
			"don_gia": float(lot["don_gia"] or 0),
			"het_han": bool(han and frappe.utils.getdate(han) < hom_nay),
			"de_xuat": de_xuat,
		})
	return {"lots": lots, "thieu": con_lai}


def _print_format_cho_kho(doctype: str, kho: str) -> str:
	"""Chọn mẫu in: mẫu riêng của kho nếu có VÀ đúng loại chứng từ, ngược lại
	dùng mẫu TT107 mặc định. Một Print Format cấu hình sai loại doc_type (ví
	dụ trỏ nhầm sang "Miyano - Hoá đơn") sẽ bị bỏ qua thay vì render rác hoặc
	ném lỗi tiếng Anh của framework.
	"""
	field = "mau_phieu_nhap" if doctype == "Customer Stock Receipt" else "mau_phieu_xuat"
	default = DEFAULT_NHAP if doctype == "Customer Stock Receipt" else DEFAULT_XUAT
	chosen = frappe.db.get_value("Customer Warehouse", kho, field)
	if chosen:
		doc_type_cua_mau = frappe.db.get_value("Print Format", chosen, "doc_type")
		if doc_type_cua_mau == doctype:
			return chosen
	return default


def _render_phieu_html(doctype: str, name: str, kho: str) -> str:
	"""Dựng HTML của phiếu bằng CHÍNH mẫu Print Format đã cài, nhưng KHÔNG đi
	qua frappe.www.printview.get_html_and_style(): hàm đó tự kiểm quyền bên
	trong (đã đo thực nghiệm — ném PermissionError cho user portal dù đã gọi
	doc.check_permission("read") thành công trước đó không giúp gì, vì
	get_html_and_style tự làm lại việc kiểm tra bằng cơ chế module-level mà
	role Customer luôn trượt, đúng như spec mục 6 mô tả).

	Thay vào đó: sau khi TỰ kiểm sở hữu bằng _phieu_cua_kho() (đã làm ở nơi
	gọi), nạp doc bằng frappe.get_doc (an toàn ở đây vì sở hữu đã được xác
	nhận tường minh) rồi tự render template của Print Format bằng
	frappe.render_template — hàm thuần render, không có tầng kiểm quyền nào
	chen vào giữa.

	Context truyền vào CHỈ gồm {"doc", "frappe"} — cố ý giống hệt context mà
	frappe.www.printview.get_html_and_style() (đường render CHUẨN mà nhân
	viên Miyano vẫn dùng từ desk, có print=1 trên hai doctype này) tự truyền.
	Bản trước còn bơm thêm "kho"/"rows_html" riêng cho đường portal — khiến
	mẫu RENDER LỖI ("'kho' is undefined") khi ai đó in từ desk, vì đường đó
	không biết hai biến này. Đã đo bằng get_html_and_style() thật và sửa:
	bốn template giờ tự tra thông tin kho qua frappe.db.get_value(doc.kho)
	và tự lặp doc.items, không cần biến ngoài nào khác — cả hai đường render
	dùng chung một cách phá vỡ, và một cái là đủ.
	"""
	doc = frappe.get_doc(doctype, name)
	print_format = _print_format_cho_kho(doctype, kho)
	html_template = frappe.db.get_value("Print Format", print_format, "html")
	return frappe.render_template(html_template, {"doc": doc, "frappe": frappe})


@frappe.whitelist()
@_phieu_action
def kho_phieu_pdf(doctype: str, name: str) -> None:
	kho = get_portal_kho()
	_phieu_cua_kho(doctype, name, kho)
	html = _render_phieu_html(doctype, name, kho)
	from frappe.utils.pdf import get_pdf
	frappe.local.response.filename = f"{name}.pdf"
	frappe.local.response.filecontent = get_pdf(html)
	frappe.local.response.type = "pdf"


# ---------------------------------------------------------------------------
# Phase 5: báo cáo Nhập-Xuất-Tồn, thẻ kho, cảnh báo hạn dùng, xuất Excel.
# Toàn bộ phép tính nằm ở miyano_portal/kho/reports.py — các hàm dưới đây chỉ
# suy kho từ phiên, kiểm sở hữu tham số do client gửi (`vat_tu`), rồi giao lại
# cho reports.py, đúng khuôn phân lớp của ledger.py/import_ton_dau.py.
# ---------------------------------------------------------------------------


@frappe.whitelist()
def kho_bao_cao_nxt(tu_ngay, den_ngay, tim=None, vat_tu=None) -> dict:
	"""Báo cáo Nhập-Xuất-Tồn. Không truyền `vat_tu`: một dòng cho mỗi vật tư.
	Có truyền `vat_tu`: bung xuống mức lô CỦA CHÍNH vật tư đó — `vat_tu` do
	client gửi nên phải qua _vat_tu_cua_kho() trước khi chạm ledger, đúng
	nguyên tắc đầu file (đây là tham số duy nhất của cả ba báo cáo Phase 5 mà
	client tự chọn giá trị).
	"""
	kho = get_portal_kho()
	if vat_tu:
		_vat_tu_cua_kho(vat_tu, kho)
		return {"muc": "lo", "vat_tu": vat_tu, "rows": reports.nxt_lot_rows(kho, vat_tu, tu_ngay, den_ngay)}
	return {"muc": "vat_tu", "rows": reports.nxt_item_rows(kho, tu_ngay, den_ngay, tim)}


@frappe.whitelist()
def kho_the_kho(vat_tu: str, tu_ngay, den_ngay) -> list:
	"""Thẻ kho của một vật tư trong khoảng ngày."""
	kho = get_portal_kho()
	_vat_tu_cua_kho(vat_tu, kho)
	return reports.the_kho_rows(kho, vat_tu, tu_ngay, den_ngay)


@frappe.whitelist()
def kho_canh_bao_han(so_ngay=90) -> list:
	"""Lô đã hết hạn còn tồn và lô sắp hết hạn trong `so_ngay` ngày tới."""
	kho = get_portal_kho()
	so_ngay = _so_nguyen(so_ngay, "Số ngày", 90)
	if so_ngay < 0:
		frappe.throw("Số ngày không hợp lệ.", frappe.ValidationError)
	return reports.canh_bao_han_rows(kho, so_ngay)


@frappe.whitelist()
def kho_bao_cao_excel(loai: str, tu_ngay=None, den_ngay=None, tim=None, vat_tu=None, so_ngay=90) -> None:
	"""Xuất báo cáo ĐANG XEM ra .xlsx — CÙNG bộ cột, CÙNG dữ liệu mà endpoint
	JSON tương ứng vừa trả cho màn hình, không có đường dữ liệu riêng nào
	khác: `loai` chọn ĐÚNG MỘT trong ba hàm reports.*_rows() mà các endpoint
	JSON ở trên cũng gọi, nên "cột khớp màn hình" là một tính chất CẤU TRÚC,
	không phải một lời hứa phải tự kiểm tra tay mỗi khi sửa cột.
	"""
	kho = get_portal_kho()
	if loai not in _BAO_CAO_LOAI:
		frappe.throw("Loại báo cáo không hợp lệ.", frappe.ValidationError)

	if loai == "nxt":
		if not (tu_ngay and den_ngay):
			frappe.throw("Thiếu khoảng ngày để xuất báo cáo.", frappe.ValidationError)
		if vat_tu:
			_vat_tu_cua_kho(vat_tu, kho)
			rows = reports.nxt_lot_rows(kho, vat_tu, tu_ngay, den_ngay)
			columns = reports.NXT_LOT_COLUMNS
		else:
			rows = reports.nxt_item_rows(kho, tu_ngay, den_ngay, tim)
			columns = reports.NXT_COLUMNS
		filename, sheet = "bao_cao_nhap_xuat_ton.xlsx", "N-X-T"
	elif loai == "the_kho":
		if not (vat_tu and tu_ngay and den_ngay):
			frappe.throw("Thiếu vật tư hoặc khoảng ngày để xuất thẻ kho.", frappe.ValidationError)
		_vat_tu_cua_kho(vat_tu, kho)
		rows = reports.the_kho_rows(kho, vat_tu, tu_ngay, den_ngay)
		columns = reports.THE_KHO_COLUMNS
		filename, sheet = "the_kho.xlsx", "The kho"
	else:
		so_ngay = _so_nguyen(so_ngay, "Số ngày", 90)
		if so_ngay < 0:
			frappe.throw("Số ngày không hợp lệ.", frappe.ValidationError)
		rows = reports.canh_bao_han_rows(kho, so_ngay)
		columns = reports.CANH_BAO_COLUMNS
		filename, sheet = "canh_bao_han_dung.xlsx", "Canh bao han dung"

	frappe.local.response.filename = filename
	frappe.local.response.filecontent = reports.build_xlsx(columns, rows, sheet)
	frappe.local.response.type = "download"
	frappe.local.response.content_type = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)
