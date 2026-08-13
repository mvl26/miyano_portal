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
		voucher.validate_so_luong(self)
		self._lay_gia_va_han_tu_lo()
		self._kiem_do_dai_nguoi_nhan()
		self._validate_khoa_phong_thuoc_kho()

	def _validate_khoa_phong_thuoc_kho(self):
		"""E8/BR-CP2 — cùng khuôn voucher.validate_vat_tu_thuoc_kho(): chặn
		phiếu trỏ tới khoa phòng của một kho khác. Đây vừa là kiểm tra dữ
		liệu vừa là hàng rào cách ly, chạy ở TẦNG CONTROLLER nên áp dụng cho
		MỌI đường ghi (kho_phieu_xuat_save lẫn Desk) — endpoint cố tình
		KHÔNG lặp lại kiểm tra này (xem comment trong api/kho.py).
		"""
		if not self.khoa_phong:
			return
		kho_cua_khoa = frappe.db.get_value("Customer Department", self.khoa_phong, "kho")
		if kho_cua_khoa != self.kho:
			frappe.throw(
				f"Khoa phòng {self.khoa_phong} không thuộc kho {self.kho}.",
				frappe.ValidationError,
			)

	def _kiem_do_dai_nguoi_nhan(self):
		"""BR-CP3: Người nhận là ô nhập tự do, không quản danh mục, nhưng vẫn
		giới hạn ≤100 ký tự (US-E8.3). CỐ Ý kiểm ở đây thay vì đánh "length":
		100 trên field trong JSON: field `nguoi_nhan` đã tồn tại từ trước E8
		với cột DB varchar(140) và có dữ liệu thật — đổi "length" sẽ khiến
		`bench migrate` ALTER cột xuống varchar(100), lỗi hoặc cắt cụt bất kỳ
		giá trị cũ nào đã dài hơn 100. Kiểm bằng tay ở validate() vừa an toàn
		schema vừa cho thông báo tiếng Việt (JSON constraint vi phạm sẽ ném
		lỗi MariaDB tiếng Anh, dịch qua _phieu_action trong api/kho.py rồi
		vẫn không nêu rõ ký tự thứ mấy)."""
		if self.nguoi_nhan and len(self.nguoi_nhan) > 100:
			frappe.throw(
				"Người nhận không được quá 100 ký tự.", frappe.ValidationError
			)

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

	def _lay_gia_va_han_tu_lo(self):
		"""Đơn giá và hạn dùng của dòng xuất LUÔN lấy từ lô, không nhận từ người dùng.

		Đây là điều làm cho báo cáo nhập-xuất-tồn có cột thành tiền mà không cần
		engine định giá: giá vốn xuất chính là đơn giá đang có của lô.

		NGOẠI LỆ DUY NHẤT: khi đang tạo phiếu đảo (self.flags.dang_tao_dao),
		KHÔNG được đọc lại đơn giá/hạn dùng từ lô ở đây, vì lô có thể đã đổi giá
		bình quân gia quyền do những lần nhập xảy ra SAU phiếu xuất gốc (giữa
		lúc xuất và lúc huỷ). Đọc lại sẽ khiến phiếu đảo hoàn trả một giá trị
		khác với giá trị phiếu xuất gốc đã trừ đi - tự sinh hoặc tự huỷ tiền
		mà không có giao dịch nào giải thích được, dù số lượng và tồn cuối vẫn
		khớp nên không có gì tự lộ ra lỗi. _tao_phieu_dao() đã copy đúng
		don_gia/han_su_dung từ dòng gốc trước khi insert(); ở đây chỉ cần giữ
		nguyên giá trị đó.

		Phần điền tên/ĐVT và phần tính thành tiền/tổng tiền dùng CHUNG hàm với
		phiếu nhập (`voucher.fill_ten_dvt` / `voucher.tinh_tien`, FINDING N4);
		riêng bước lấy giá từ lô là của riêng phiếu xuất nên phải chen vào
		GIỮA hai bước đó — đó cũng là lý do fill_item_details() không gọi trọn
		gói được ở đây.
		"""
		voucher.fill_ten_dvt(self)
		if not self.flags.dang_tao_dao:
			for row in self.items:
				bal = ledger.get_lot_balance(self.kho, row.vat_tu, row.so_lo)
				row.don_gia = float(bal["don_gia"]) if bal else 0.0
				row.han_su_dung = bal["han_su_dung"] if bal else None
		voucher.tinh_tien(self)

	def before_submit(self):
		if self.loai_xuat != voucher.LOAI_DAO:
			self._chan_xuat_qua_ton()
			# US-E4.4 / BR-K20: chỉ "Xuất sử dụng" mới bắt xác nhận lô hết hạn.
			# "Xuất huỷ - hết hạn" đúng nghĩa LÀ để xuất hàng hết hạn — hỏi lại
			# ở đó là hỏi thừa. Các loại xuất khác (Xuất trả lại, Điều chỉnh
			# kiểm kê) cũng không hỏi, đúng AC US-E4.4.
			if self.loai_xuat == "Xuất sử dụng":
				self._chan_lo_het_han_chua_xac_nhan()
				self._chan_thieu_khoa_phong()
			# NL-4.12: khoa phòng đã tắt (active=0) còn nằm trên phiếu nháp —
			# kiểm ở MỌI loại xuất (không chỉ "Xuất sử dụng") vì field không bị
			# ràng buộc chỉ dùng cho loại đó; kiểm khi GHI SỔ, không phải khi
			# lưu nháp, để không khoá một dòng nháp cũ trong lúc thủ kho còn
			# đang sửa dở. Nằm trong nhánh "khác Phiếu đảo" ở trên: phiếu đảo
			# (BR-K9, hệ tự tạo trong on_cancel) copy nguyên khoa_phong của
			# phiếu gốc mà KHÔNG được phép ngã vào chốt này — một khoa bị tắt
			# GIỮA lúc xuất và lúc huỷ không được làm sập luôn thao tác huỷ
			# (on_cancel không được phép ném lỗi, xem docstring on_cancel).
			if self.khoa_phong:
				self._chan_khoa_phong_da_tat()

	def _chan_thieu_khoa_phong(self):
		"""US-E8.2/BR-CP2/NL-4.11 — chỉ áp cho loại "Xuất sử dụng", và chỉ cho
		phiếu TẠO SAU thời điểm kho bật cờ `bat_buoc_khoa_phong` (so với
		`self.creation`, mốc phiếu được TẠO — tức lần insert() đầu tiên/Lưu
		nháp — KHÔNG PHẢI thời điểm hàm này chạy, vốn là lúc GHI SỔ). Đây là
		lý do `Customer Warehouse.bat_buoc_khoa_phong_tu` phải tồn tại: một
		Check đơn thuần không mang đủ thông tin để so hai mốc thời gian này.

		Xem `_ghi_moc_bat_buoc_khoa_phong()` (customer_warehouse.py) cho quyết
		định ca biên "cờ bật nhưng thiếu mốc" (áp bắt buộc cho MỌI phiếu).
		"""
		bat, moc = frappe.db.get_value(
			"Customer Warehouse", self.kho,
			["bat_buoc_khoa_phong", "bat_buoc_khoa_phong_tu"],
		)
		if not frappe.utils.cint(bat):
			return
		if moc:
			# self.creation rỗng CHỈ khi phiếu chưa từng insert() — không thể
			# xảy ra ở before_submit (submit() luôn chạy sau insert() thật),
			# nhưng phòng thủ bằng `or now()` thay vì để get_datetime(None)
			# ném lỗi nếu giả định đó có ngày sai.
			tao_luc = frappe.utils.get_datetime(self.creation or frappe.utils.now_datetime())
			if tao_luc <= frappe.utils.get_datetime(moc):
				return
		if not self.khoa_phong:
			frappe.throw(
				"Kho đã bật \"Bắt buộc chọn khoa phòng\" cho phiếu Xuất sử "
				"dụng tạo sau thời điểm đó. Hãy chọn Khoa phòng nhận trước "
				"khi ghi sổ.",
				frappe.ValidationError,
			)

	def _chan_khoa_phong_da_tat(self):
		active = frappe.db.get_value("Customer Department", self.khoa_phong, "active")
		if not frappe.utils.cint(active):
			ten = frappe.db.get_value("Customer Department", self.khoa_phong, "ten_khoa_phong")
			frappe.throw(
				f"Khoa phòng \"{ten or self.khoa_phong}\" đã bị tắt hoạt động. "
				"Hãy chọn lại một khoa phòng đang hoạt động trước khi ghi sổ.",
				frappe.ValidationError,
			)

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
		"""BR-K20: "hết hạn" so với NGÀY PHIẾU (self.ngay), KHÔNG phải ngày hệ
		thống chạy validate. Sai chỗ này đi theo cả hai chiều:
		  * chặn nhầm — phiếu lập bù cho một ngày trong quá khứ (lô CÒN hạn
		    tại ngày đó) sẽ bị bắt xác nhận một điều SAI SỰ THẬT, và vì sổ
		    append-only nên chứng từ mang xác nhận sai đó vĩnh viễn.
		  * bỏ lọt — phiếu ghi ngày tương lai (không bị chặn bởi
		    voucher.validate_ngay, hàm đó chỉ chặn NGÀY TRƯỚC ngay_bat_dau của
		    kho) cho một lô sẽ hết hạn trước ngày đó nhưng chưa hết hạn ở ngày
		    hệ thống hôm nay sẽ lọt qua guard, đúng ca BR-K20 sinh ra để bắt.
		"""
		hom_nay = frappe.utils.getdate(self.ngay)
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
		dao.khoa_phong = self.khoa_phong
		dao.noi_nhan = self.noi_nhan
		dao.nguoi_nhan = self.nguoi_nhan
		dao.dien_giai = f"Đảo phiếu {self.name}"
		for r in self.items:
			# don_gia và han_su_dung PHẢI copy từ dòng gốc, không được để
			# _lay_gia_va_han_tu_lo() đọc lại từ lô: giá bình quân gia quyền
			# của lô có thể đã đổi (do nhập thêm) giữa lúc xuất và lúc huỷ,
			# và đọc lại sẽ hoàn trả sai giá trị (xem docstring
			# _lay_gia_va_han_tu_lo). dang_tao_dao chặn việc đọc lại đó;
			# ở đây ta chỉ cần nạp đúng giá trị gốc vào dòng.
			dao.append("items", {
				"vat_tu": r.vat_tu, "so_lo": r.so_lo,
				"so_luong": r.so_luong, "don_gia": r.don_gia,
				"han_su_dung": r.han_su_dung, "xac_nhan_het_han": 1,
			})
		# Giữ ĐÚNG một hình thức bỏ qua phân quyền, giống hệt phiếu nhập
		# (customer_stock_receipt.py): kwarg của insert(). Bản trước còn đặt
		# thêm `dao.flags.ignore_permissions = True` ngay trước đó — thừa,
		# không sai: Document.insert() làm chính xác việc đó
		# (`if ignore_permissions is not None: self.flags.ignore_permissions =
		# ignore_permissions`), nên cờ vẫn còn hiệu lực ở dao.submit() trong
		# CẢ HAI phiếu. Bỏ dòng thừa đi để hai chứng từ đọc giống nhau và để
		# không ai hiểu nhầm rằng hai bên có mức kiểm quyền khác nhau.
		dao.insert(ignore_permissions=True)
		dao.submit()
		return dao
