import frappe
from frappe.model.document import Document

from miyano_portal.kho import ledger, voucher


class CustomerStockReceipt(Document):
	def autoname(self):
		self.name = voucher.next_voucher_name(
			"PN", "Customer Stock Receipt", self.kho, self.ngay
		)

	def validate(self):
		self._chan_tu_tao_phieu_dao()
		voucher.validate_ngay(self)
		voucher.validate_vat_tu_thuoc_kho(self)
		voucher.validate_so_luong_don_gia(self)
		voucher.fill_item_details(self)

	def _chan_tu_tao_phieu_dao(self):
		"""Chỉ `_tao_phieu_dao()` được phép tạo phiếu loại "Phiếu đảo".

		"Phiếu đảo" là một lựa chọn trong dropdown `loai_nhap`, không có gì
		ngăn người dùng tự chọn nó. Nếu để lọt: `_he_so_dau()` sẽ ghi số lượng
		ÂM vào sổ như thể đang bù trừ một phiếu gốc không hề tồn tại — tức là
		một cách rút kho — và `block_cancel_of_reversal` khiến phiếu đó vĩnh
		viễn không huỷ được. Không có đường lùi.

		Điều kiện duy nhất được chấp nhận là `self.flags.dang_tao_dao`.
		`self.flags` là thuộc tính trong bộ nhớ của riêng đối tượng Python này,
		KHÔNG BAO GIỜ được lưu xuống DB và không nằm trong danh sách field của
		doctype — không cách nào giả được nó qua form, qua payload API, hay
		qua `frappe.get_doc({...})`. `_tao_phieu_dao()` đặt cờ này trước khi
		gọi `insert()`.

		Bản trước của guard này còn chấp nhận `or self.phieu_goc` — SAI: sau
		khi finding 2 đổi `phieu_goc` từ Link sang Data, đó chỉ còn là một
		field Data thường, ai cũng ghi được chuỗi bất kỳ vào đó (kể cả một
		mã không tồn tại), nên vế `or` biến chốt chặn thành vô tác dụng. ĐỪNG
		thêm lại bất kỳ điều kiện `or` nào dựa trên giá trị field vào đây —
		field luôn ghi được từ bên ngoài, cờ `flags` thì không.
		"""
		if self.loai_nhap != voucher.LOAI_DAO:
			return
		if not self.flags.dang_tao_dao:
			frappe.throw(
				"Không thể tạo phiếu đảo bằng tay. Phiếu đảo chỉ được hệ thống "
				"sinh tự động khi huỷ một phiếu nhập đã ghi sổ.",
				frappe.ValidationError,
			)

	def _he_so_dau(self) -> float:
		"""Phiếu đảo mang số lượng DƯƠNG trên chứng từ cho người đọc dễ hiểu,
		nhưng ghi vào sổ với dấu ÂM để bù trừ phiếu gốc."""
		return -1.0 if self.loai_nhap == voucher.LOAI_DAO else 1.0

	def on_submit(self):
		he_so = self._he_so_dau()
		ledger.post_lines(self, [{
			"vat_tu": r.vat_tu,
			"so_lo": r.so_lo,
			"han_su_dung": r.han_su_dung,
			"so_luong": he_so * float(r.so_luong),
			"don_gia": float(r.don_gia or 0),
			"chung_tu_row": r.name,
		} for r in self.items])

	def before_cancel(self):
		"""Các kiểm tra chặn huỷ phải chạy TRƯỚC khi docstatus=2 được ghi vào DB.

		`on_cancel` chạy sau `db_update()`: nếu đặt guard ở đó, dưới một
		request HTTP bình thường thì rollback của Frappe che giấu vấn đề,
		nhưng bất kỳ lời gọi nào trong cùng transaction mà bắt ValidationError
		(bench script, background job, test suite) sẽ để lại tài liệu đã ở
		trạng thái "Đã huỷ" trong DB dù lỗi đã được ném ra. Đây là phiên bản
		lặp lại của lỗi mà sổ kho (Task 3) từng mắc, ở tầng phiếu.
		"""
		voucher.block_cancel_of_reversal(self, "loai_nhap")
		self._chan_neu_dao_lam_am_ton()

	def on_cancel(self):
		"""Huỷ phiếu KHÔNG xoá dòng sổ nào.

		Thay vào đó sinh một phiếu đảo đã submit với số lượng ngược dấu, rồi
		đánh dấu các dòng sổ gốc là đã bị đảo. Sổ vẫn cộng dồn ra đúng tồn.
		Các kiểm tra chặn huỷ đã chạy xong ở before_cancel; ở đây chỉ còn lại
		hiệu ứng (effect), không còn validation.
		"""
		self._tao_phieu_dao()
		ledger.mark_reversed(self.doctype, self.name)

	def _chan_neu_dao_lam_am_ton(self):
		"""Không cho huỷ nếu hàng của lô đó đã bị xuất mất rồi.

		Đảo lại sẽ kéo tồn xuống âm, mà sổ này không cho phép tồn âm. Phải
		CỘNG DỒN theo (vat_tu, so_lo) trước khi so với tồn: một phiếu có hai
		dòng cùng lô (hai giá khác nhau, ví dụ) mà so từng dòng riêng lẻ với
		tồn hiện tại sẽ đánh giá sai — cả hai dòng đều "đủ" khi xét độc lập dù
		tổng hai dòng cộng lại vượt quá tồn, vì chưa dòng nào thật sự bị trừ
		lúc so sánh.
		"""
		tong_theo_lo = {}
		for r in self.items:
			key = (r.vat_tu, r.so_lo)
			info = tong_theo_lo.setdefault(
				key, {"so_luong": 0.0, "ten_vat_tu": r.ten_vat_tu, "dvt": r.dvt}
			)
			info["so_luong"] += float(r.so_luong)

		for (vat_tu, so_lo), info in tong_theo_lo.items():
			bal = ledger.get_lot_balance(self.kho, vat_tu, so_lo)
			con = float(bal["so_luong"]) if bal else 0.0
			if con < info["so_luong"] - ledger.EPS:
				frappe.throw(
					f"Không thể huỷ phiếu: lô {so_lo} của {info['ten_vat_tu']} chỉ "
					f"còn {con:g} {info['dvt'] or ''} trong khi phiếu này đã nhập "
					f"{info['so_luong']:g}. Hàng đã được xuất đi, hãy huỷ phiếu "
					f"xuất tương ứng trước.",
					frappe.ValidationError,
				)

	def _tao_phieu_dao(self):
		dao = frappe.new_doc("Customer Stock Receipt")
		dao.kho = self.kho
		dao.ngay = frappe.utils.today()
		dao.loai_nhap = voucher.LOAI_DAO
		dao.phieu_goc = self.name
		dao.dien_giai = f"Đảo phiếu {self.name}"
		for r in self.items:
			dao.append("items", {
				"vat_tu": r.vat_tu,
				"so_lo": r.so_lo,
				"han_su_dung": r.han_su_dung,
				"so_luong": r.so_luong,
				"don_gia": r.don_gia,
			})
		# Cho _chan_tu_tao_phieu_dao() biết đây là phiếu đảo hợp lệ, không phải
		# một phiếu "Phiếu đảo" người dùng tự chọn từ dropdown.
		dao.flags.dang_tao_dao = True
		dao.insert(ignore_permissions=True)
		dao.submit()
		return dao
