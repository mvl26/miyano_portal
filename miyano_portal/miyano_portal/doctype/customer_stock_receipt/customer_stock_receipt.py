import frappe
from frappe.model.document import Document

from miyano_portal.kho import ledger, voucher


class CustomerStockReceipt(Document):
	def autoname(self):
		self.name = voucher.next_voucher_name(
			"PN", "Customer Stock Receipt", self.kho, self.ngay
		)

	def validate(self):
		voucher.validate_ngay(self)
		voucher.validate_vat_tu_thuoc_kho(self)
		voucher.validate_so_luong_don_gia(self)
		voucher.fill_item_details(self)

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

	def on_cancel(self):
		"""Huỷ phiếu KHÔNG xoá dòng sổ nào.

		Thay vào đó sinh một phiếu đảo đã submit với số lượng ngược dấu, rồi
		đánh dấu các dòng sổ gốc là đã bị đảo. Sổ vẫn cộng dồn ra đúng tồn.
		"""
		voucher.block_cancel_of_reversal(self, "loai_nhap")
		self._chan_neu_dao_lam_am_ton()
		self._tao_phieu_dao()
		ledger.mark_reversed(self.doctype, self.name)
		# Frappe tự chạy check_no_back_links_exist() ngay sau on_cancel(), trong
		# cùng lời gọi cancel() này. Phiếu đảo vừa tạo ở trên đã submit và trỏ
		# `phieu_goc` về chính self, nên nếu không tắt kiểm tra này thì việc huỷ
		# sẽ tự chặn chính nó bằng LinkExistsError — chỉ vì bằng chứng nó vừa
		# sinh ra. Không có doctype nào khác của module này link tới Customer
		# Stock Receipt như một chứng từ submit được, nên tắt an toàn ở đây.
		self.flags.ignore_links = True

	def _chan_neu_dao_lam_am_ton(self):
		"""Không cho huỷ nếu hàng của lô đó đã bị xuất mất rồi.

		Đảo lại sẽ kéo tồn xuống âm, mà sổ này không cho phép tồn âm.
		"""
		for r in self.items:
			bal = ledger.get_lot_balance(self.kho, r.vat_tu, r.so_lo)
			con = float(bal["so_luong"]) if bal else 0.0
			if con < float(r.so_luong) - ledger.EPS:
				frappe.throw(
					f"Không thể huỷ phiếu: lô {r.so_lo} của {r.ten_vat_tu} chỉ còn "
					f"{con:g} {r.dvt or ''} trong khi phiếu này đã nhập "
					f"{float(r.so_luong):g}. Hàng đã được xuất đi, hãy huỷ phiếu "
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
		dao.flags.ignore_permissions = True
		# ignore_links=True: tại thời điểm này self (phiếu gốc) đã có docstatus=2
		# trong DB — on_cancel chạy SAU khi bản ghi gốc đã được lưu là "Đã huỷ".
		# Không có cờ này, Frappe chặn việc tạo một liên kết (phieu_goc) trỏ tới
		# một chứng từ đã huỷ, dù đó chính là hành vi ta cố tình muốn ở đây.
		dao.insert(ignore_permissions=True, ignore_links=True)
		dao.submit()
		return dao
