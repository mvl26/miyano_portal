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

import frappe

from miyano_portal.kho import ledger
from miyano_portal.kho import import_ton_dau
from miyano_portal.portal_context import get_portal_kho


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
	"""Tồn hiện tại, gộp các lô về một dòng cho mỗi vật tư."""
	kho = get_portal_kho()
	lots = frappe.get_all(
		"Customer Stock Lot Balance",
		filters={"kho": kho, "so_luong": [">", ledger.EPS]},
		fields=["vat_tu", "so_lo", "han_su_dung", "so_luong", "gia_tri"],
	)

	gop = {}
	for lot in lots:
		g = gop.setdefault(lot["vat_tu"], {
			"vat_tu": lot["vat_tu"], "so_luong": 0.0, "gia_tri": 0.0,
			"so_lo_count": 0, "han_gan_nhat": None,
		})
		g["so_luong"] += float(lot["so_luong"])
		g["gia_tri"] += float(lot["gia_tri"] or 0)
		g["so_lo_count"] += 1
		han = lot["han_su_dung"]
		if han and (g["han_gan_nhat"] is None or han < g["han_gan_nhat"]):
			g["han_gan_nhat"] = han

	out = []
	for vat_tu, g in gop.items():
		vt = frappe.db.get_value(
			"Customer Warehouse Item", vat_tu,
			["ma_vat_tu", "ten_vat_tu", "dvt", "item_code"], as_dict=True,
		)
		if not vt:
			continue
		if tim:
			hay = f"{vt.ma_vat_tu} {vt.ten_vat_tu}".lower()
			if tim.lower() not in hay:
				continue
		out.append({**g, **{
			"ma_vat_tu": vt.ma_vat_tu, "ten_vat_tu": vt.ten_vat_tu,
			"dvt": vt.dvt, "item_code": vt.item_code or "",
		}})
	return sorted(out, key=lambda r: r["ten_vat_tu"])


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
