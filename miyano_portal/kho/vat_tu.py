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


# --------------------------------------------------------------------------
# File danh mục: export → sửa → nạp lại. MỘT bộ cột duy nhất cho cả ba việc
# (xuất, mẫu, đọc), đúng nguyên tắc round-tripping-spreadsheets.
# --------------------------------------------------------------------------

DANH_MUC_COLUMNS = [
	("Mã vật tư", "ma_vat_tu"),
	("Tên vật tư", "ten_vat_tu"),
	("ĐVT", "dvt"),
	("Mã hàng Miyano", "item_code"),
	("Quy cách", "quy_cach"),
	("Nhóm", "nhom"),
	("Đang dùng", "active"),
]

# Cột phải CÓ MẶT trong header. `item_code` không nằm đây vì nó chỉ đọc:
# xuất ra cho khách đối chiếu, nạp vào thì bỏ qua (server tự suy từ mã).
DANH_MUC_REQUIRED = {"ma_vat_tu", "ten_vat_tu", "dvt"}

_TRUE_VALUES = {"1", "x", "co", "có", "true", "yes", "y", "dang dung", "đang dùng"}
_FALSE_VALUES = {"", "0", "khong", "không", "false", "no", "n", "tat", "tắt"}


def _coerce_bool(value) -> tuple[int | None, str | None]:
	"""Cột 'Đang dùng': nhận 1/0, x, có/không, true/false. Trống = đang dùng."""
	if value in (None, ""):
		return 1, None
	if isinstance(value, bool):
		return int(value), None
	if isinstance(value, (int, float)):
		return int(bool(value)), None
	s = _norm(value).lower()
	if s in _TRUE_VALUES:
		return 1, None
	if s in _FALSE_VALUES:
		return 0, None
	return None, f"Cột 'Đang dùng' không hợp lệ: '{value}' (dùng 1/0 hoặc x/trống)"


def export_rows(kho: str) -> list[dict]:
	# `ghi_chu` không nằm trong DANH_MUC_COLUMNS (cột file không có nó), nhưng
	# _chuan_hoa_row() cần trường này có mặt — lấy kèm cho rẻ, build_xlsx() chỉ
	# đọc đúng các field khai trong DANH_MUC_COLUMNS nên phần dư không lộ ra file.
	rows = frappe.get_all(
		"Customer Warehouse Item",
		filters={"kho": kho},
		fields=["ma_vat_tu", "ten_vat_tu", "dvt", "item_code", "quy_cach", "nhom", "ghi_chu", "active"],
		order_by="ma_vat_tu asc",
	)
	return [_chuan_hoa_row(r) for r in rows]


def build_danh_muc_xlsx(kho: str) -> bytes:
	from miyano_portal.kho import reports

	return reports.build_xlsx(DANH_MUC_COLUMNS, export_rows(kho), "Danh muc vat tu")


def _ton_cua(kho: str, vat_tu: str) -> float:
	return sum(float(r["so_luong"]) for r in ledger.get_lot_balances(kho, vat_tu))


def parse_danh_muc(content: bytes, kho: str) -> dict:
	"""Đọc và validate toàn bộ file danh mục, KHÔNG GHI GÌ.

	Mỗi dòng ra một trong hai hành động: `tao_moi` (mã chưa có) hoặc `cap_nhat`
	(mã đã có). Rào §4.2/§4.3 của thiết kế được kiểm NGAY Ở ĐÂY chứ không để
	đến lúc ghi, để dòng vi phạm hiện thành dòng lỗi trong bản xem trước thay
	vì một thay đổi bị bỏ qua im lặng.
	"""
	from miyano_portal.kho.import_ton_dau import _cell_value, mo_workbook, read_header

	ws = mo_workbook(content)
	header_row, col_index = read_header(ws, DANH_MUC_COLUMNS, DANH_MUC_REQUIRED)

	rows_ok: list[dict] = []
	rows_error: list[dict] = []

	for line, row_cells in enumerate(
		ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row), start=header_row + 1
	):
		raw = {field: _cell_value(row_cells, col) for field, col in col_index.items()}
		if all(v is None or (isinstance(v, str) and not v.strip()) for v in raw.values()):
			continue

		errors: list[str] = []
		ma = _norm(raw.get("ma_vat_tu"))
		ten = _norm(raw.get("ten_vat_tu"))
		dvt = _norm(raw.get("dvt"))
		if not ma:
			errors.append("Thiếu Mã vật tư")
		if not ten:
			errors.append("Thiếu Tên vật tư")
		if not dvt:
			errors.append("Thiếu ĐVT")

		active, bool_err = _coerce_bool(raw.get("active"))
		if bool_err:
			errors.append(bool_err)

		vat_tu_name = None
		hanh_dong = "tao_moi"
		# Chỉ gửi 'dvt' xuống sua() khi nó THỰC SỰ đổi (so sánh không phân biệt
		# hoa/thường, giống rào bên dưới) — nếu không, một dòng chỉ lệch hoa/
		# thường ('Hộp' xuất ra, khách gõ lại 'hộp') sẽ đi lọt qua rào ở đây rồi
		# rơi vào đúng rào case-sensitive của sua() ở bước ghi, ném lỗi giữa
		# vòng lặp thay vì hiện ngay trong bản xem trước.
		dvt_thay_doi = False
		if ma and not errors:
			match_type, item_code, vat_tu_name = _match_vat_tu(kho, ma)
			if match_type == "existing":
				hanh_dong = "cap_nhat"
				hien = frappe.db.get_value(
					"Customer Warehouse Item", vat_tu_name, ["dvt", "active"], as_dict=True
				)
				dvt_thay_doi = _fold_khac(hien.dvt, dvt)
				if dvt_thay_doi and co_phat_sinh(vat_tu_name):
					errors.append(
						f"ĐVT không sửa được: {ma} đã có phát sinh trong sổ "
						f"(ĐVT hiện tại: {hien.dvt})"
					)
				if active == 0 and int(hien.active or 0) == 1:
					ton = _ton_cua(kho, vat_tu_name)
					if ton > ledger.EPS:
						errors.append(f"Không tắt được: {ma} còn tồn {ton:g} {hien.dvt or ''}")

		if errors:
			rows_error.append({"line": line, "ma_vat_tu": ma or f"(dòng {line})", "errors": errors})
			continue

		rows_ok.append({
			"line": line, "ma_vat_tu": ma, "ten_vat_tu": ten, "dvt": dvt,
			"quy_cach": _norm(raw.get("quy_cach")), "nhom": _norm(raw.get("nhom")),
			"active": active, "hanh_dong": hanh_dong, "vat_tu": vat_tu_name,
			"dvt_thay_doi": dvt_thay_doi,
		})

	summary = {"tao_moi": 0, "cap_nhat": 0}
	for r in rows_ok:
		summary[r["hanh_dong"]] += 1

	return {
		"total": len(rows_ok) + len(rows_error),
		"ok_count": len(rows_ok),
		"error_count": len(rows_error),
		"summary": summary,
		"rows_ok": rows_ok,
		"rows_error": rows_error,
	}


def _fold_khac(a, b) -> bool:
	return _norm(a).lower() != _norm(b).lower()


def commit_danh_muc(content: bytes, kho: str) -> dict:
	"""Đọc lại TỪ ĐẦU trên server rồi ghi. Tất-cả-hoặc-không."""
	parsed = parse_danh_muc(content, kho)
	if parsed["error_count"]:
		first = parsed["rows_error"][0]
		frappe.throw(
			f"Tệp có {parsed['error_count']} dòng lỗi trong tổng số {parsed['total']} dòng "
			f"(ví dụ dòng {first['line']}: {'; '.join(first['errors'])}). "
			"Vui lòng sửa và tải lại — chưa có dữ liệu nào được ghi.",
			frappe.ValidationError,
		)
	if not parsed["rows_ok"]:
		frappe.throw("Tệp không có dòng dữ liệu hợp lệ nào.", frappe.ValidationError)

	sp = "kho_danh_muc_commit_sp"
	frappe.db.savepoint(sp)
	try:
		for row in parsed["rows_ok"]:
			if row["hanh_dong"] == "tao_moi":
				# tao() luôn tạo active=1 (xem TRUONG_NHAN_TU_CLIENT) — dòng file
				# xin 'Đang dùng=0' cho một mã hoàn toàn mới thì tắt lại ngay sau,
				# chứ không được lặng lẽ bỏ qua giá trị khách đã ghi trong file.
				moi = tao(kho, {
					"ma_vat_tu": row["ma_vat_tu"], "ten_vat_tu": row["ten_vat_tu"],
					"dvt": row["dvt"], "quy_cach": row["quy_cach"], "nhom": row["nhom"],
				})
				if row["active"] == 0:
					sua(kho, moi["name"], {"active": 0})
			else:
				# KHÔNG gửi 'ma_vat_tu': nó chỉ dùng để TRA CỨU bản ghi ở
				# _match_vat_tu, không bao giờ diễn tả một phép đổi mã ở đường
				# này. Gửi nó xuống sua() chỉ có hại: so khớp mã ở trên không
				# phân biệt hoa/thường nhưng rào TRUONG_KHOA của sua() thì có,
				# nên một dòng chỉ lệch hoa/thường sẽ ăn nhầm rào "đã có phát
				# sinh" giữa lúc ghi, hoặc lặng lẽ đổi lại chính tả mã.
				du_lieu = {
					"ten_vat_tu": row["ten_vat_tu"], "quy_cach": row["quy_cach"],
					"nhom": row["nhom"], "active": row["active"],
				}
				if row["dvt_thay_doi"]:
					du_lieu["dvt"] = row["dvt"]
				sua(kho, row["vat_tu"], du_lieu)
	except Exception:
		frappe.db.rollback(save_point=sp)
		raise

	return parsed["summary"]
