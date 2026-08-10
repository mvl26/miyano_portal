"""Danh mục vật tư của kho khách hàng — tạo, sửa có rào, đọc/ghi file.

Tầng này KHÔNG biết gì về phiên đăng nhập: `kho` luôn do nơi gọi (api/kho.py)
truyền vào sau khi đã resolve từ phiên, đúng khuôn ledger.py / reports.py /
import_ton_dau.py.

Hai rào của module này tồn tại vì sổ kho không quy đổi đơn vị và không sửa
được quá khứ:
  * `dvt` và `ma_vat_tu` khoá lại khi vật tư đã có dòng sổ — đổi ĐVT làm tồn
    133 Hộp đọc thành 133 Cái mà không có gì tự lộ ra.
  * không tắt được vật tư còn tồn — nó sẽ biến mất khỏi ô chọn (danh sách lọc
    active=1) trong khi báo cáo tồn vẫn hiện số của nó.
"""

import frappe

from miyano_portal.kho import ledger
from miyano_portal.kho.import_ton_dau import _match_vat_tu, _norm

# Trường DUY NHẤT được nhận từ client. Không bao giờ doc.update(payload):
# `kho` phải đến từ phiên, và `item_code` phải do server suy ra (xem _item_miyano).
TRUONG_NHAN_TU_CLIENT = ("ma_vat_tu", "ten_vat_tu", "dvt", "quy_cach", "nhom", "ghi_chu")

# Sửa được kể cả khi đã có phát sinh — chúng chỉ là mô tả, không tham gia phép cộng nào.
TRUONG_MO_TA = ("ten_vat_tu", "quy_cach", "nhom", "ghi_chu")

# Khoá lại khi đã có phát sinh.
TRUONG_KHOA = ("ma_vat_tu", "dvt")

_NHAN = {"ma_vat_tu": "Mã vật tư", "dvt": "ĐVT"}


def co_phat_sinh(vat_tu: str) -> bool:
	return bool(frappe.db.exists("Customer Stock Ledger Entry", {"vat_tu": vat_tu}))


def cac_vat_tu_co_phat_sinh(kho: str) -> set[str]:
	"""Bản gộp của co_phat_sinh() cho cả một kho — MỘT truy vấn cho toàn danh
	mục, không phải mỗi vật tư một truy vấn (kho_vat_tu_list gọi nó trên mọi
	lần mở màn phiếu)."""
	rows = frappe.db.sql(
		"select distinct vat_tu from `tabCustomer Stock Ledger Entry` where kho=%s", (kho,)
	)
	return {r[0] for r in rows}


def _item_miyano(ma_vat_tu: str) -> str | None:
	"""item_code thật của Miyano nếu mã trùng, theo đúng chính tả trong DB."""
	row = frappe.db.sql(
		"select item_code from `tabItem` where lower(item_code)=%s limit 1",
		(ma_vat_tu.strip().lower(),),
	)
	return row[0][0] if row else None


def _chuan_hoa_row(row: dict) -> dict:
	"""Chuẩn hoá TẠI CHỖ một dòng vật tư đọc thẳng từ DB: cột trống trong
	MariaDB là NULL (Python `None`), nhưng client (cả modal tạo nhanh lẫn màn
	danh mục) luôn cần chuỗi rỗng để bind vào input mà không hiện "null", và
	`active` cần về int thường (không phải Decimal/None) để so sánh được ở
	frontend.

	Đây là nguồn DUY NHẤT của phép chuẩn hoá này — `ra_dict()` (một bản ghi,
	dùng bởi kho_vat_tu_tao/sua) và `kho_vat_tu_list()` bên api/kho.py (cả
	danh sách) đều gọi lại đúng hàm này thay vì tự lặp khối gán, để thêm một
	trường vào danh mục vật tư chỉ phải sửa một chỗ — trước khi tách, hai nơi
	chép tay từng dòng y hệt nhau và rất dễ lệch khi ai đó sửa một bên mà quên
	bên kia.
	"""
	row["item_code"] = row["item_code"] or ""
	row["quy_cach"] = row["quy_cach"] or ""
	row["nhom"] = row["nhom"] or ""
	row["ghi_chu"] = row["ghi_chu"] or ""
	row["active"] = int(row["active"] or 0)
	return row


def ra_dict(name: str, da_co: bool = False) -> dict:
	row = frappe.db.get_value(
		"Customer Warehouse Item", name,
		["name", "ma_vat_tu", "ten_vat_tu", "dvt", "item_code",
		 "quy_cach", "nhom", "ghi_chu", "active"],
		as_dict=True,
	)
	_chuan_hoa_row(row)
	row["co_phat_sinh"] = co_phat_sinh(name)
	# `da_co` cho giao diện biết đây là vật tư đã tồn tại chứ không phải vừa
	# tạo — nút "Tạo vật tư" ở dòng thứ hai cùng mã không được báo lỗi.
	row["da_co"] = da_co
	return row


def tao(kho: str, du_lieu: dict) -> dict:
	ma = _norm(du_lieu.get("ma_vat_tu"))
	ten = _norm(du_lieu.get("ten_vat_tu"))
	dvt = _norm(du_lieu.get("dvt"))
	if not ma:
		frappe.throw("Thiếu Mã vật tư.", frappe.ValidationError)
	if not ten:
		frappe.throw("Thiếu Tên vật tư.", frappe.ValidationError)
	if not dvt:
		frappe.throw("Thiếu ĐVT.", frappe.ValidationError)

	# Kiểm TRƯỚC, không bắt ValidationError của controller: bắt ngoại lệ giữa
	# một transaction đang mở là cách chắc chắn để lại trạng thái nửa vời.
	match_type, item_code, vat_tu_name = _match_vat_tu(kho, ma)
	if match_type == "existing":
		return ra_dict(vat_tu_name, da_co=True)

	doc = frappe.get_doc({
		"doctype": "Customer Warehouse Item",
		"kho": kho,
		# Mã khớp Item của Miyano thì lấy chính tả chuẩn trong hệ thống Miyano,
		# không lấy cách khách gõ.
		"ma_vat_tu": item_code or ma,
		"ten_vat_tu": ten,
		"dvt": dvt,
		"active": 1,
		"item_code": item_code or None,
		"quy_cach": _norm(du_lieu.get("quy_cach")) or None,
		"nhom": _norm(du_lieu.get("nhom")) or None,
		"ghi_chu": _norm(du_lieu.get("ghi_chu")) or None,
	})
	doc.insert(ignore_permissions=True)
	return ra_dict(doc.name)


def _chan_tat_khi_con_ton(doc) -> None:
	ton = sum(float(r["so_luong"]) for r in ledger.get_lot_balances(doc.kho, doc.name))
	if ton > ledger.EPS:
		frappe.throw(
			f"Vật tư {doc.ma_vat_tu} còn tồn {ton:g} {doc.dvt or ''}. "
			"Hãy xuất hết trước khi ngừng dùng.",
			frappe.ValidationError,
		)


def sua(kho: str, vat_tu: str, du_lieu: dict) -> dict:
	"""Nơi gọi PHẢI kiểm `vat_tu` thuộc `kho` trước (api/kho.py._vat_tu_cua_kho)."""
	doc = frappe.get_doc("Customer Warehouse Item", vat_tu)
	da_phat_sinh = co_phat_sinh(vat_tu)
	ma_cu = doc.ma_vat_tu

	for truong in TRUONG_MO_TA:
		if truong in du_lieu:
			setattr(doc, truong, _norm(du_lieu.get(truong)) or None)
	if not doc.ten_vat_tu:
		frappe.throw("Thiếu Tên vật tư.", frappe.ValidationError)

	for truong in TRUONG_KHOA:
		if truong not in du_lieu:
			continue
		gia_tri = _norm(du_lieu.get(truong))
		if gia_tri == _norm(getattr(doc, truong)):
			continue  # gửi lên giá trị y hệt thì không tính là sửa
		if da_phat_sinh:
			frappe.throw(
				f"{_NHAN[truong]} không sửa được vì vật tư {ma_cu} đã có phát sinh "
				"trong sổ kho. Số liệu cũ đã tính theo giá trị hiện tại và hệ thống "
				"không quy đổi.",
				frappe.ValidationError,
			)
		if not gia_tri:
			frappe.throw(f"Thiếu {_NHAN[truong]}.", frappe.ValidationError)
		setattr(doc, truong, gia_tri)

	if doc.ma_vat_tu != ma_cu:
		# Mã mới có thể trùng một Item của Miyano, hoặc thôi không trùng nữa.
		doc.item_code = _item_miyano(doc.ma_vat_tu)

	if "active" in du_lieu:
		active = 1 if frappe.utils.cint(du_lieu.get("active")) else 0
		if not active and doc.active:
			_chan_tat_khi_con_ton(doc)
		doc.active = active

	doc.save(ignore_permissions=True)
	return ra_dict(doc.name)
