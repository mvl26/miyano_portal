"""Logic dùng chung của phiếu nhập và phiếu xuất kho khách hàng."""

import frappe

from miyano_portal.kho.ledger import LOT_KHONG_CO

LOAI_DAO = "Phiếu đảo"

# Chỉ hai doctype này được phép truyền vào next_voucher_name. Danh sách trắng
# vì tên doctype bị nội suy thẳng vào SQL — không bao giờ nhận từ dữ liệu
# người dùng.
VOUCHER_DOCTYPES = ("Customer Stock Receipt", "Customer Stock Issue")


def next_voucher_name(prefix: str, doctype: str, kho: str, ngay: str) -> str:
	"""Sinh số phiếu dạng PN-BM-2026-00001, đếm riêng theo từng kho và từng năm.

	Không dùng naming_series của Frappe vì series ở đó là hằng số khai báo
	trong doctype, không chèn được mã kho lấy từ bản ghi.
	"""
	if doctype not in VOUCHER_DOCTYPES:
		frappe.throw(f"Loại chứng từ kho không hợp lệ: {doctype}")
	ma_kho = frappe.db.get_value("Customer Warehouse", kho, "ma_kho")
	nam = frappe.utils.getdate(ngay).year
	tien_to = f"{prefix}-{ma_kho}-{nam}-"
	cuoi = frappe.db.sql(
		f"""select name from `tab{doctype}` where name like %s
		    order by name desc limit 1""",
		tien_to + "%",
	)
	so = int(cuoi[0][0].rsplit("-", 1)[1]) + 1 if cuoi else 1
	return f"{tien_to}{so:05d}"


def validate_ngay(doc) -> None:
	bat_dau = frappe.db.get_value("Customer Warehouse", doc.kho, "ngay_bat_dau")
	if bat_dau and frappe.utils.getdate(doc.ngay) < frappe.utils.getdate(bat_dau):
		frappe.throw(
			f"Ngày phiếu ({frappe.utils.formatdate(doc.ngay)}) không được trước "
			f"Ngày bắt đầu quản lý của kho ({frappe.utils.formatdate(bat_dau)}).",
			frappe.ValidationError,
		)


def validate_vat_tu_thuoc_kho(doc) -> None:
	"""Chặn dòng phiếu trỏ tới vật tư của kho khác.

	Đây vừa là kiểm tra dữ liệu vừa là hàng rào cách ly: nếu không có nó, một
	người dùng có thể ghi vào sổ kho của mình bằng vật tư của khách khác.
	"""
	for row in doc.items:
		kho_cua_vt = frappe.db.get_value("Customer Warehouse Item", row.vat_tu, "kho")
		if kho_cua_vt != doc.kho:
			frappe.throw(
				f"Dòng {row.idx}: vật tư {row.vat_tu} không thuộc kho {doc.kho}.",
				frappe.ValidationError,
			)


def validate_so_luong_don_gia(doc) -> None:
	for row in doc.items:
		if float(row.so_luong or 0) <= 0:
			frappe.throw(
				f"Dòng {row.idx}: số lượng phải lớn hơn 0.", frappe.ValidationError
			)
		if float(row.don_gia or 0) < 0:
			frappe.throw(
				f"Dòng {row.idx}: đơn giá không được âm.", frappe.ValidationError
			)


def fill_item_details(doc) -> None:
	"""Điền tên/ĐVT và tính thành tiền, tổng tiền."""
	tong = 0.0
	for row in doc.items:
		vt = frappe.db.get_value(
			"Customer Warehouse Item", row.vat_tu, ["ten_vat_tu", "dvt"], as_dict=True
		)
		if vt:
			row.ten_vat_tu = vt.ten_vat_tu
			row.dvt = vt.dvt
		if not row.so_lo:
			row.so_lo = LOT_KHONG_CO
		row.thanh_tien = float(row.so_luong or 0) * float(row.don_gia or 0)
		tong += row.thanh_tien
	doc.tong_tien = tong


def block_cancel_of_reversal(doc, loai_field: str) -> None:
	if doc.get(loai_field) == LOAI_DAO:
		frappe.throw(
			"Không thể huỷ một phiếu đảo. Phiếu đảo được sinh tự động để bù trừ "
			"phiếu gốc.",
			frappe.ValidationError,
		)
