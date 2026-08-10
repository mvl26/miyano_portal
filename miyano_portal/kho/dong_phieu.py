"""Bảng dòng của phiếu nhập/phiếu xuất: đọc từ .xlsx, xuất ra .xlsx.

Module này KHÔNG GHI GÌ vào database. Nó chỉ dịch giữa một tệp Excel và danh
sách dòng mà màn hình phiếu đang soạn — việc ghi vẫn đi qua đúng
kho_phieu_nhap_save / kho_phieu_xuat_save như mọi dòng gõ tay.

Vì sao phiếu xuất không có cột Đơn giá và Hạn sử dụng: controller của
Customer Stock Issue luôn ghi đè hai giá trị đó bằng giá/hạn hiện hành của lô
(_lay_gia_va_han_tu_lo). Nhận chúng từ tệp chỉ tạo ảo giác là người dùng đặt
được giá vốn.
"""

import frappe

from miyano_portal.kho import ledger
from miyano_portal.kho.import_ton_dau import (
	_cell_value,
	_coerce_date,
	_coerce_num,
	_norm,
	_match_vat_tu,
	mo_workbook,
	read_header,
)

COLUMNS = {
	"nhap": [
		("Mã vật tư", "ma_vat_tu"),
		("Tên vật tư", "ten_vat_tu"),
		("ĐVT", "dvt"),
		("Số lô", "so_lo"),
		("Hạn sử dụng", "han_su_dung"),
		("Số lượng", "so_luong"),
		("Đơn giá", "don_gia"),
		("Quy cách", "quy_cach"),
		("Nhóm", "nhom"),
		("Ghi chú", "ghi_chu"),
	],
	"xuat": [
		("Mã vật tư", "ma_vat_tu"),
		("Tên vật tư", "ten_vat_tu"),
		("ĐVT", "dvt"),
		("Số lô", "so_lo"),
		("Số lượng", "so_luong"),
		("Quy cách", "quy_cach"),
		("Nhóm", "nhom"),
		("Ghi chú", "ghi_chu"),
	],
}

# Cột phải CÓ MẶT trong header. `Tên vật tư`/`ĐVT` KHÔNG bắt buộc ở đây: chúng
# chỉ cần thiết cho dòng mang mã chưa có (để tạo nhanh), và điều đó được kiểm
# theo TỪNG DÒNG bên dưới.
REQUIRED = {
	"nhap": {"ma_vat_tu", "so_luong", "don_gia"},
	"xuat": {"ma_vat_tu", "so_luong"},
}

DOCTYPE_THEO_LOAI = {
	"nhap": "Customer Stock Receipt",
	"xuat": "Customer Stock Issue",
}
LOAI_THEO_DOCTYPE = {v: k for k, v in DOCTYPE_THEO_LOAI.items()}


def _kiem_loai(loai: str) -> str:
	if loai not in COLUMNS:
		frappe.throw(
			'Loại phiếu không hợp lệ. Chỉ chấp nhận "nhap" hoặc "xuat".',
			frappe.ValidationError,
		)
	return loai


def build_mau_xlsx(loai: str) -> bytes:
	"""Tệp mẫu rỗng, đúng bộ cột — không kèm dòng ví dụ, vì người dùng dán dữ
	liệu thật vào ngay dưới header và một dòng ví dụ bị bỏ quên sẽ thành một
	dòng phiếu thật."""
	from miyano_portal.kho import reports

	_kiem_loai(loai)
	return reports.build_xlsx(COLUMNS[loai], [], "Dong phieu")


def doc_file(content: bytes, kho: str, loai: str) -> dict:
	"""Đọc tệp thành các dòng phiếu. KHÔNG GHI GÌ.

	Mỗi dòng nhận đúng một trạng thái:
	  * "khop"   — mã đã có trong kho; `vat_tu` gán sẵn, tên/ĐVT lấy THEO DANH
	               MỤC (bỏ qua cột mô tả trong tệp, để một tệp cũ nạp lại không
	               âm thầm đổi ĐVT của vật tư đã có phát sinh).
	  * "ma_moi" — mã chưa có; giữ nguyên mô tả đọc từ tệp để modal tạo nhanh
	               điền sẵn. Bắt buộc phải có Tên và ĐVT, không thì thành "loi".
	  * "loi"    — thiếu trường bắt buộc hoặc sai định dạng; `loi` liệt kê MỌI
	               lý do của dòng đó, kèm số dòng thật trong tệp.

	BẤT BIẾN cho consumer: `vat_tu` CHỈ khác rỗng khi `trang_thai == "khop"`.
	Một dòng "loi" không bao giờ mang định danh `vat_tu` thật, kể cả khi mã
	trên dòng đó trùng một Customer Warehouse Item đang tồn tại — rẽ nhánh
	PHẢI dựa vào `trang_thai`, không được suy luận từ `vat_tu` có giá trị
	hay không.
	"""
	_kiem_loai(loai)
	ws = mo_workbook(content)
	header_row, col_index = read_header(ws, COLUMNS[loai], REQUIRED[loai])
	co_don_gia = loai == "nhap"

	rows: list[dict] = []
	for line, row_cells in enumerate(
		ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row), start=header_row + 1
	):
		raw = {field: _cell_value(row_cells, col) for field, col in col_index.items()}
		if all(v is None or (isinstance(v, str) and not v.strip()) for v in raw.values()):
			continue

		loi: list[str] = []
		ma = _norm(raw.get("ma_vat_tu"))
		ten = _norm(raw.get("ten_vat_tu"))
		dvt = _norm(raw.get("dvt"))
		so_lo = _norm(raw.get("so_lo")) or ledger.LOT_KHONG_CO
		ghi_chu = _norm(raw.get("ghi_chu"))

		if not ma:
			loi.append("Thiếu Mã vật tư")

		so_luong = None
		if raw.get("so_luong") in (None, ""):
			loi.append("Thiếu Số lượng")
		else:
			so_luong, err = _coerce_num(raw.get("so_luong"))
			if err:
				loi.append(f"Số lượng không hợp lệ: {err}")
			elif so_luong <= 0:
				loi.append("Số lượng phải lớn hơn 0")

		don_gia = None
		han_su_dung = None
		if co_don_gia:
			if raw.get("don_gia") in (None, ""):
				loi.append("Thiếu Đơn giá")
			else:
				don_gia, err = _coerce_num(raw.get("don_gia"))
				if err:
					loi.append(f"Đơn giá không hợp lệ: {err}")
				elif don_gia < 0:
					loi.append("Đơn giá không được âm")
			han_su_dung, han_err = _coerce_date(raw.get("han_su_dung"))
			if han_err:
				loi.append(han_err)

		vat_tu_name = ""
		trang_thai = "ma_moi"
		if ma:
			# Chạy VÔ ĐIỀU KIỆN khi có mã — không gate theo `not loi`: nếu không,
			# một dòng vừa sai định dạng (Số lượng/Đơn giá/Hạn) VỪA mang mã mới
			# thiếu Tên/ĐVT sẽ chỉ báo lỗi định dạng, nuốt mất lý do "cần Tên/ĐVT
			# để tạo mới" — vi phạm thẳng yêu cầu "loi liệt kê MỌI lý do".
			match_type, _item_code, found = _match_vat_tu(kho, ma)
			if match_type == "existing":
				trang_thai = "khop"
				vat_tu_name = found
				hien = frappe.db.get_value(
					"Customer Warehouse Item", found, ["ma_vat_tu", "ten_vat_tu", "dvt"], as_dict=True
				)
				ma, ten, dvt = hien.ma_vat_tu, hien.ten_vat_tu, hien.dvt
			else:
				if not ten:
					loi.append("Mã chưa có trong kho — cần Tên vật tư để tạo mới")
				if not dvt:
					loi.append("Mã chưa có trong kho — cần ĐVT để tạo mới")

		trang_thai_cuoi = "loi" if loi else trang_thai
		row = {
			"line": line,
			"trang_thai": trang_thai_cuoi,
			# Chỉ tin `vat_tu_name` khi dòng thật sự "khop": `_match_vat_tu` có
			# thể chạy và tìm thấy một bản ghi thật ngay cả trên một dòng đã có
			# lỗi định dạng khác (Số lượng/Đơn giá/Hạn) — bất biến bắt buộc là
			# dòng "loi" KHÔNG BAO GIỜ mang một định danh vat_tu thật, nếu không
			# một consumer sau này rẽ nhánh theo "có vat_tu hay không" thay vì
			# theo trang_thai sẽ âm thầm coi dòng lỗi là dòng đã khớp.
			"vat_tu": vat_tu_name if trang_thai_cuoi == "khop" else "",
			"ma_vat_tu": ma,
			"ten_vat_tu": ten,
			"dvt": dvt,
			"so_lo": so_lo,
			"so_luong": so_luong,
			"quy_cach": _norm(raw.get("quy_cach")),
			"nhom": _norm(raw.get("nhom")),
			"ghi_chu": ghi_chu,
			"loi": loi,
		}
		if co_don_gia:
			row["don_gia"] = don_gia
			row["han_su_dung"] = han_su_dung
		rows.append(row)

	return {"total": len(rows), "rows": rows}


def export_rows(doctype: str, name: str) -> list[dict]:
	"""Nơi gọi PHẢI kiểm phiếu thuộc kho của người gọi trước (_phieu_cua_kho)."""
	loai = LOAI_THEO_DOCTYPE.get(doctype)
	if not loai:
		frappe.throw("Loại chứng từ không hợp lệ.", frappe.ValidationError)

	doc = frappe.get_doc(doctype, name)
	out = []
	for r in doc.items:
		vt = frappe.db.get_value(
			"Customer Warehouse Item", r.vat_tu,
			["ma_vat_tu", "ten_vat_tu", "dvt", "quy_cach", "nhom"], as_dict=True,
		) or frappe._dict()
		row = {
			"ma_vat_tu": vt.get("ma_vat_tu") or "",
			"ten_vat_tu": r.ten_vat_tu or vt.get("ten_vat_tu") or "",
			"dvt": r.dvt or vt.get("dvt") or "",
			"so_lo": r.so_lo,
			"so_luong": float(r.so_luong or 0),
			"quy_cach": vt.get("quy_cach") or "",
			"nhom": vt.get("nhom") or "",
			"ghi_chu": r.ghi_chu or "",
		}
		if loai == "nhap":
			row["han_su_dung"] = r.han_su_dung
			row["don_gia"] = float(r.don_gia or 0)
		out.append(row)
	return out


def build_export_xlsx(doctype: str, name: str) -> bytes:
	from miyano_portal.kho import reports

	loai = LOAI_THEO_DOCTYPE.get(doctype)
	if not loai:
		frappe.throw("Loại chứng từ không hợp lệ.", frappe.ValidationError)
	return reports.build_xlsx(COLUMNS[loai], export_rows(doctype, name), "Dong phieu")
