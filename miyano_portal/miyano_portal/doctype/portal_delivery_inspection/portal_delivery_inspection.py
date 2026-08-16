# Copyright (c) 2026, Miyano and contributors
# For license information, please see license.txt
"""Biên bản kiểm hàng — khách xác nhận đợt giao, báo hàng thiếu/hỏng.

Thiết kế: `docs/superpowers/specs/2026-08-16-kiem-hang-tra-hang-hong-design.md`.

Doctype này CỐ Ý độc lập với module kho (`Customer Stock Receipt`). Đọc §4.4
của spec trước khi định "hợp nhất hai cái cho gọn": phiếu nhập kho ghi sổ tồn
NỘI BỘ của khách và chỉ tồn tại cho 5/21 khách đã mở kho; biên bản này là cuộc
đối thoại với Miyano về một đợt giao và phải chạy được cho MỌI khách.
"""

import frappe
from frappe.model.document import Document

# Sai số so sánh số thực. Cùng bậc với `kho.ledger.EPS` nhưng KHÔNG import từ
# đó: doctype này không phụ thuộc module kho (spec §6 "module kho đứng yên"),
# và một hằng số 8 ký tự không đáng để tạo ra một cạnh phụ thuộc.
EPS = 1e-6

TT_NHAP = "Nháp"
TT_CHO_XU_LY = "Chờ xử lý"
TT_DA_XAC_NHAN = "Đã xác nhận"
TT_DA_DUYET_TRA = "Đã duyệt trả"
TT_DA_THU_HOI = "Đã thu hồi"
TT_DA_XU_LY = "Đã xử lý"
TT_TU_CHOI = "Từ chối"


class PortalDeliveryInspection(Document):
	def validate(self):
		self._chan_trung_phieu_giao()
		self._kiem_dong()

	def _chan_trung_phieu_giao(self):
		"""Một phiếu giao chỉ có MỘT biên bản còn sống (spec §4.3).

		`delivery_note` là **Data**, không phải Link — cùng lựa chọn đã có ở
		`Customer Stock Receipt.delivery_note`. Một Link sẽ khiến Frappe chặn
		nhân viên HUỶ phiếu giao ("Cannot cancel because it is linked with...")
		chỉ vì khách đã lập biên bản kiểm hàng theo nó: một chứng từ của khách
		khoá tay nghiệp vụ của Miyano. Ràng buộc tồn tại/sở hữu của phiếu giao
		được kiểm ở tầng endpoint (`api/portal.py`), nơi `customer` suy từ
		phiên chứ không nhận từ client.


		`docstatus < 2` — biên bản đã huỷ không chặn khách lập lại, đó chính
		là đường lùi khi nhân viên "Từ chối" và khách cần gửi lại. Bản amend
		(`amended_from`) đi kèm việc bản gốc đã sang docstatus=2 nên không tự
		đụng vào chính nó.
		"""
		trung = frappe.db.get_value(
			"Portal Delivery Inspection",
			{
				"delivery_note": self.delivery_note,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
			"name",
		)
		if trung:
			frappe.throw(
				f"Phiếu giao {self.delivery_note} đã có biên bản kiểm hàng {trung}.",
				frappe.ValidationError,
			)

	def _kiem_dong(self):
		"""BR-KH1..KH4 — xem spec §4.1.

		Chạy trong `validate()` (không phải `before_submit`) để chặn được CẢ
		lưu nháp lẫn gửi, cùng lý do `Customer Stock Receipt.
		_validate_doi_soat_giao_nhan()` đã chọn chỗ đứng đó: khách thấy lỗi
		ngay lúc gõ, không phải đợi tới lúc bấm gửi.
		"""
		co_hong = False
		for row in self.items:
			sl_giao = float(row.sl_giao or 0)
			sl_nhan = float(row.sl_nhan or 0)
			sl_tra = float(row.sl_tra or 0)

			if sl_nhan < 0 or sl_tra < 0:
				frappe.throw(
					f"Dòng {row.idx}: số lượng không được âm.", frappe.ValidationError
				)

			# Không có "nhận thừa" trên biên bản này — cùng nguyên tắc NL-3.10
			# của phiếu nhập kho. Hàng về nhiều hơn phiếu giao là một sự kiện
			# khác, xử lý bằng một đợt giao/chứng từ riêng chứ không phải bằng
			# cách sửa con số trên biên bản đối chiếu với chính phiếu giao đó.
			if sl_nhan + sl_tra > sl_giao + EPS:
				frappe.throw(
					f"Dòng {row.idx}: nhận tốt ({sl_nhan:g}) + trả lại ({sl_tra:g}) "
					f"không được vượt SL giao ({sl_giao:g}).",
					frappe.ValidationError,
				)

			lech = abs(sl_nhan + sl_tra - sl_giao) > EPS
			if (sl_tra > EPS or lech) and not (row.get("ly_do") or "").strip():
				frappe.throw(
					f"Dòng {row.idx}: giao {sl_giao:g}, nhận tốt {sl_nhan:g}, "
					f"trả lại {sl_tra:g}. Nhập lý do để tiếp tục.",
					frappe.ValidationError,
				)
			if sl_tra > EPS:
				co_hong = True

		self.co_hang_hong = 1 if co_hong else 0

	def co_van_de(self) -> bool:
		"""Có hàng hỏng HOẶC có hàng thiếu — hai thứ đều cần Miyano nhìn tới.

		Thiếu (`sl_nhan + sl_tra < sl_giao`) không sinh phiếu trả hàng nhưng
		vẫn là một khiếu nại: hàng đã ghi trên phiếu giao mà không tới nơi.
		Gộp chung một cổng "Chờ xử lý" thay vì để nó rơi vào "Đã xác nhận" —
		rơi vào đó là mất tín hiệu, đúng kiểu lỗi C1 của BR-K17.
		"""
		if self.co_hang_hong:
			return True
		return any(
			abs(float(r.sl_nhan or 0) + float(r.sl_tra or 0) - float(r.sl_giao or 0)) > EPS
			for r in self.items
		)

	def before_submit(self):
		self.trang_thai = TT_CHO_XU_LY if self.co_van_de() else TT_DA_XAC_NHAN

	def on_submit(self):
		self._bao_miyano_neu_co_van_de()

	def _bao_miyano_neu_co_van_de(self):
		"""Biên bản đã ghi nhận thật rồi; một trục trặc ở khâu thông báo nội
		bộ không được phép biến một lần gửi thành công thành submit lỗi —
		cùng nguyên tắc `Customer Stock Receipt._bao_chenh_lech_neu_co()`."""
		if not self.co_van_de():
			return
		try:
			from miyano_portal.portal_thong_bao import bao_kiem_hang_co_van_de

			bao_kiem_hang_co_van_de(self)
		except Exception:
			frappe.log_error(
				title="Kiểm hàng: lỗi khi báo nội bộ biên bản có vấn đề",
				reference_doctype=self.doctype,
				reference_name=self.name,
			)

	def before_cancel(self):
		"""Không huỷ được biên bản mà Miyano đã lập phiếu trả hàng theo nó.

		Huỷ ở đây sẽ để lại một Delivery Note trả hàng mồ côi, trỏ về một biên
		bản không còn hiệu lực — nhân viên kho nhìn vào không biết còn phải
		thu hồi hay không.
		"""
		if self.phieu_tra_hang and frappe.db.exists("Delivery Note", self.phieu_tra_hang):
			docstatus = frappe.db.get_value("Delivery Note", self.phieu_tra_hang, "docstatus")
			if docstatus != 2:
				frappe.throw(
					f"Biên bản này đã có phiếu trả hàng {self.phieu_tra_hang}. "
					"Huỷ phiếu trả hàng trước.",
					frappe.ValidationError,
				)
