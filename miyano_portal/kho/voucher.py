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


def _check_so_luong(row) -> None:
	"""C1 (BR-K17 vô hiệu qua nút xoá dòng, E3 phần B review): trước bản này,
	`so_luong` phải > 0 TUYỆT ĐỐI — không có cách nào ghi "nhận 0" trên một
	dòng nguồn Miyano (`sl_giao > 0`), nên hàng bị mất/thiếu HOÀN TOÀN buộc
	thủ kho phải xoá cả dòng để lưu được. Xoá dòng làm `sl_giao` biến mất
	theo, tắt luôn BR-K17 và khiến report "Đối soát giao nhận" không bao giờ
	thấy được số hàng đã mất — không một tín hiệu, không notification.

	Giờ cho phép `so_luong = 0` NHƯNG CHỈ trên dòng có `sl_giao > 0` — dòng
	khách tự lập (Tồn đầu kỳ, Nhập khác, và mọi dòng phiếu xuất — không
	doctype nào trong số đó có field `sl_giao`, `row.get("sl_giao")` trả
	`None`/0 an toàn) vẫn bị chặn `so_luong <= 0` y hệt trước đây. `so_luong
	== 0` trên dòng nguồn Miyano vẫn phải qua `_validate_doi_soat_giao_nhan`
	(BR-K17) như mọi mức lệch khác — bắt lý do, gắn `co_chenh_lech`, bắn
	notification; không phải một lối tắt né chốt chặn đó."""
	so_luong = float(row.so_luong or 0)
	if so_luong < 0:
		frappe.throw(
			f"Dòng {row.idx}: số lượng không được âm.", frappe.ValidationError
		)
	if so_luong == 0 and not float(row.get("sl_giao") or 0):
		frappe.throw(
			f"Dòng {row.idx}: số lượng phải lớn hơn 0.", frappe.ValidationError
		)


def validate_so_luong(doc) -> None:
	"""Chỉ kiểm số lượng. Dùng cho phiếu XUẤT, nơi `don_gia` không do người
	dùng nhập mà lấy từ lô SAU bước validate này — kiểm đơn giá ở đây sẽ bắt
	nhầm giá trị tạm trên bản nháp trước khi nó bị ghi đè."""
	for row in doc.items:
		_check_so_luong(row)


def validate_so_luong_don_gia(doc) -> None:
	"""Phiếu NHẬP: người dùng nhập cả hai, nên kiểm cả hai.

	Kiểm theo TỪNG DÒNG (số lượng rồi đơn giá) chứ không phải hai vòng lặp
	tách rời, để thông báo lỗi vẫn là lỗi đầu tiên theo thứ tự dòng — gộp
	chung với validate_so_luong() bằng hai vòng lặp sẽ đổi lỗi báo ra trong
	trường hợp dòng 1 sai đơn giá và dòng 2 sai số lượng.
	"""
	for row in doc.items:
		_check_so_luong(row)
		if float(row.don_gia or 0) < 0:
			frappe.throw(
				f"Dòng {row.idx}: đơn giá không được âm.", frappe.ValidationError
			)


def fill_ten_dvt(doc) -> None:
	"""Điền tên vật tư và ĐVT từ danh mục vật tư của kho.

	Tách riêng khỏi fill_item_details() để phiếu xuất dùng lại được: phiếu
	xuất phải chen bước lấy đơn giá/hạn dùng từ lô vào GIỮA bước điền tên và
	bước tính tiền, nên không gọi trọn gói được.
	"""
	for row in doc.items:
		vt = frappe.db.get_value(
			"Customer Warehouse Item", row.vat_tu, ["ten_vat_tu", "dvt"], as_dict=True
		)
		if vt:
			row.ten_vat_tu = vt.ten_vat_tu
			row.dvt = vt.dvt


def tinh_tien(doc) -> None:
	"""Thành tiền từng dòng và tổng tiền của phiếu."""
	tong = 0.0
	for row in doc.items:
		row.thanh_tien = float(row.so_luong or 0) * float(row.don_gia or 0)
		tong += row.thanh_tien
	doc.tong_tien = tong


def fill_item_details(doc) -> None:
	"""Điền tên/ĐVT, mặc định số lô, và tính thành tiền, tổng tiền.

	Bước mặc định `so_lo` CỐ Ý chỉ có ở đây (phiếu nhập) chứ không nằm trong
	fill_ten_dvt(): phiếu xuất không mặc định số lô, và thêm vào sẽ là đổi
	hành vi chứ không phải gộp trùng lặp.
	"""
	fill_ten_dvt(doc)
	for row in doc.items:
		if not row.so_lo:
			row.so_lo = LOT_KHONG_CO
	tinh_tien(doc)


def block_cancel_of_reversal(doc, loai_field: str) -> None:
	if doc.get(loai_field) == LOAI_DAO:
		frappe.throw(
			"Không thể huỷ một phiếu đảo. Phiếu đảo được sinh tự động để bù trừ "
			"phiếu gốc.",
			frappe.ValidationError,
		)
