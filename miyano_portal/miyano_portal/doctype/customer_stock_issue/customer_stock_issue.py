from collections import defaultdict

import frappe
from frappe.model.document import Document

from miyano_portal.kho import ledger, voucher


class CustomerStockIssue(Document):
	def autoname(self):
		self.name = voucher.next_voucher_name(
			"PX", "Customer Stock Issue", self.kho, self.ngay
		)

	def validate(self):
		voucher.validate_ngay(self)
		voucher.validate_vat_tu_thuoc_kho(self)
		self._chan_dao_thu_cong()
		self._validate_so_luong()
		self._lay_gia_va_han_tu_lo()

	def _chan_dao_thu_cong(self):
		"""Chỉ _tao_phieu_dao mới được đặt loai_xuat = "Phiếu đảo".

		Nếu để hở, người dùng chọn "Phiếu đảo" từ dropdown là tạo được một
		phiếu XUẤT mang hệ số +1: nó CỘNG tồn thay vì trừ, đẻ ra hàng ma, đồng
		thời before_submit bỏ qua toàn bộ kiểm tra tồn và lô hết hạn. Tệ hơn,
		block_cancel_of_reversal khiến phiếu đó vĩnh viễn không huỷ được.
		"""
		if self.loai_xuat != voucher.LOAI_DAO:
			return
		# Điều kiện DUY NHẤT là cờ in-memory do _tao_phieu_dao đặt. Tuyệt đối
		# không chấp nhận `or self.phieu_goc`: phieu_goc là Data, ai cũng ghi
		# được, nên điền một chuỗi bất kỳ là thoả mệnh đề or và guard thành vô
		# dụng. Cờ này không lưu xuống database nên không giả mạo qua form được.
		if not self.flags.dang_tao_dao:
			frappe.throw(
				"Không thể tạo phiếu đảo bằng tay. Phiếu đảo chỉ được hệ thống "
				"sinh tự động khi huỷ một phiếu xuất đã ghi sổ.",
				frappe.ValidationError,
			)

	def _validate_so_luong(self):
		for row in self.items:
			if float(row.so_luong or 0) <= 0:
				frappe.throw(
					f"Dòng {row.idx}: số lượng phải lớn hơn 0.",
					frappe.ValidationError,
				)

	def _lay_gia_va_han_tu_lo(self):
		"""Đơn giá và hạn dùng của dòng xuất LUÔN lấy từ lô, không nhận từ người dùng.

		Đây là điều làm cho báo cáo nhập-xuất-tồn có cột thành tiền mà không cần
		engine định giá: giá vốn xuất chính là đơn giá đang có của lô.
		"""
		tong = 0.0
		for row in self.items:
			vt = frappe.db.get_value(
				"Customer Warehouse Item", row.vat_tu,
				["ten_vat_tu", "dvt"], as_dict=True,
			)
			if vt:
				row.ten_vat_tu = vt.ten_vat_tu
				row.dvt = vt.dvt
			bal = ledger.get_lot_balance(self.kho, row.vat_tu, row.so_lo)
			row.don_gia = float(bal["don_gia"]) if bal else 0.0
			row.han_su_dung = bal["han_su_dung"] if bal else None
			row.thanh_tien = float(row.so_luong or 0) * float(row.don_gia or 0)
			tong += row.thanh_tien
		self.tong_tien = tong

	def before_submit(self):
		if self.loai_xuat != voucher.LOAI_DAO:
			self._chan_xuat_qua_ton()
			self._chan_lo_het_han_chua_xac_nhan()

	def _chan_xuat_qua_ton(self):
		"""Cộng dồn theo (vật tư, lô) TRƯỚC khi so với tồn.

		Nếu kiểm tra từng dòng riêng lẻ, người dùng tách một lần xuất thành hai
		dòng cùng lô là lọt qua cả hai lần kiểm tra mà tổng vẫn vượt tồn.
		"""
		gop = defaultdict(float)
		for row in self.items:
			gop[(row.vat_tu, row.so_lo)] += float(row.so_luong or 0)

		for (vat_tu, so_lo), can in gop.items():
			bal = ledger.get_lot_balance(self.kho, vat_tu, so_lo)
			con = float(bal["so_luong"]) if bal else 0.0
			if can > con + ledger.EPS:
				ten = frappe.db.get_value(
					"Customer Warehouse Item", vat_tu, "ten_vat_tu"
				)
				dvt = frappe.db.get_value("Customer Warehouse Item", vat_tu, "dvt")
				frappe.throw(
					f"Lô {so_lo} của {ten} chỉ còn {con:g} {dvt or ''}, "
					f"không đủ để xuất {can:g}.",
					frappe.ValidationError,
				)

	def _chan_lo_het_han_chua_xac_nhan(self):
		hom_nay = frappe.utils.getdate(frappe.utils.today())
		for row in self.items:
			if not row.han_su_dung:
				continue
			if frappe.utils.getdate(row.han_su_dung) < hom_nay and not row.xac_nhan_het_han:
				frappe.throw(
					f"Dòng {row.idx}: lô {row.so_lo} của {row.ten_vat_tu} đã hết hạn "
					f"ngày {frappe.utils.formatdate(row.han_su_dung)}. Tích ô "
					f"\"Xác nhận xuất lô hết hạn\" nếu vẫn muốn xuất.",
					frappe.ValidationError,
				)

	def on_submit(self):
		he_so = 1.0 if self.loai_xuat == voucher.LOAI_DAO else -1.0
		ledger.post_lines(self, [{
			"vat_tu": r.vat_tu,
			"so_lo": r.so_lo,
			"han_su_dung": r.han_su_dung,
			"so_luong": he_so * float(r.so_luong),
			"don_gia": float(r.don_gia or 0),
			"chung_tu_row": r.name,
		} for r in self.items])

	def before_cancel(self):
		# Chốt chặn phải nằm ở before_cancel, KHÔNG phải on_cancel: on_cancel
		# chạy sau db_update() nên docstatus=2 đã ghi xuống database rồi. Ai bắt
		# ValidationError trong cùng transaction (bench script, background job,
		# test suite) sẽ để lại phiếu đã huỷ mà lẽ ra phải bị chặn.
		voucher.block_cancel_of_reversal(self, "loai_xuat")

	def on_cancel(self):
		# Đây là tác dụng phụ, không phải kiểm tra, nên đặt sau đổi trạng thái.
		self._tao_phieu_dao()
		ledger.mark_reversed(self.doctype, self.name)

	def _tao_phieu_dao(self):
		dao = frappe.new_doc("Customer Stock Issue")
		dao.flags.dang_tao_dao = True
		dao.kho = self.kho
		dao.ngay = frappe.utils.today()
		dao.loai_xuat = voucher.LOAI_DAO
		dao.phieu_goc = self.name
		dao.noi_nhan = self.noi_nhan
		dao.dien_giai = f"Đảo phiếu {self.name}"
		for r in self.items:
			dao.append("items", {
				"vat_tu": r.vat_tu, "so_lo": r.so_lo,
				"so_luong": r.so_luong, "xac_nhan_het_han": 1,
			})
		dao.flags.ignore_permissions = True
		dao.insert(ignore_permissions=True)
		dao.submit()
		return dao
