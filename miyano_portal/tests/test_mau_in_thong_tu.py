"""Mẫu in theo chế độ kế toán — yêu cầu chủ đầu tư 2026-08-16.

Điều file này canh giữ: **không chứng từ nào rơi về mẫu Standard của ERPNext**.
Cài đủ mẫu mà quên gán mặc định thì mẫu chỉ nằm đó chờ ai nhớ chọn trong
dropdown — đúng hiện trạng trước bản này, và không test nào bắt được.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.www.printview import get_html_and_style

from miyano_portal.setup.gan_mau_in_mac_dinh import MAC_DINH, gan_mau_in_mac_dinh
from miyano_portal.setup.install_bien_ban_print_formats import (
	FORMATS,
	NAME_BIEN_BAN_TT107,
	NAME_BIEN_BAN_TT200,
	NAME_PHIEU_XUAT_02VT,
	install_bien_ban_print_formats,
)
from miyano_portal.tien_bang_chu import tien_bang_chu


class TestMauInDaCai(FrappeTestCase):
	def test_cai_idempotent(self):
		install_bien_ban_print_formats()
		lan_hai = install_bien_ban_print_formats()
		self.assertEqual(lan_hai, [], "Chạy lại phải không tạo thêm mẫu nào.")
		for name, doc_type, _html in FORMATS:
			self.assertTrue(frappe.db.exists("Print Format", name), f"thiếu mẫu {name}")
			self.assertEqual(
				frappe.db.get_value("Print Format", name, "doc_type"), doc_type
			)

	def test_moi_doctype_deu_co_mau_mac_dinh(self):
		"""Chốt chính của cả file: không chứng từ nào dùng mẫu ERPNext."""
		gan_mau_in_mac_dinh()
		for doctype, mau, ly_do in MAC_DINH:
			with self.subTest(doctype=doctype):
				gan = frappe.db.get_value(
					"Property Setter",
					{"doc_type": doctype, "property": "default_print_format"},
					"value",
				)
				self.assertEqual(
					gan, mau,
					f"{doctype} chưa gán mẫu mặc định ({ly_do}) → bấm In sẽ ra "
					"mẫu Standard của ERPNext.",
				)
				self.assertTrue(
					frappe.db.exists("Print Format", mau),
					f"{doctype} trỏ vào mẫu KHÔNG TỒN TẠI — Frappe sẽ im lặng "
					"quay lại mẫu Standard, tệ hơn cả không gán.",
				)


class TestMauBienBanKiemNghiem(FrappeTestCase):
	"""Mẫu 03-VT phải render qua ĐÚNG pipeline Desk, với context tối thiểu
	{doc, frappe} — đọc docstring install_kho_print_formats về hai đường render."""

	def setUp(self):
		install_bien_ban_print_formats()
		# Bốc biên bản CÓ CẢ hàng hỏng lẫn hàng thiếu, không bốc tuỳ ý: một
		# `get_value` không điều kiện sẽ trúng biên bản nhận đủ và test cột
		# "Thiếu" tự bỏ qua chính mình — một test bỏ qua trong im lặng là một
		# test không tồn tại (bài học Ruling 18).
		self.bb = frappe.db.sql("""
			select distinct p.name from `tabPortal Delivery Inspection` p
			inner join `tabPortal Delivery Inspection Item` i on i.parent = p.name
			where p.docstatus = 1
			  and ifnull(i.sl_giao,0) - ifnull(i.sl_nhan,0) - ifnull(i.sl_tra,0) > 0
			order by p.creation desc limit 1
		""")
		self.bb = self.bb[0][0] if self.bb else None
		if not self.bb:
			self.bb = self._tao_bien_ban_co_thieu()

	def _render(self, pf):
		doc = frappe.get_doc("Portal Delivery Inspection", self.bb)
		return get_html_and_style(doc=doc.as_json(), print_format=pf)["html"]

	def test_dung_cau_truc_mau_03_vt(self):
		h = self._render(NAME_BIEN_BAN_TT107)
		for phai_co in (
			"Mẫu số 03 - VT",
			"BIÊN BẢN KIỂM NGHIỆM",
			"Ban kiểm nghiệm",
			"Số lượng đúng quy cách, phẩm chất",
			"Số lượng không đúng quy cách, phẩm chất",
			"Ý kiến của Ban kiểm nghiệm",
			"Trưởng ban",
		):
			self.assertIn(phai_co, h, f"mẫu 03-VT thiếu «{phai_co}»")

	def test_hai_bien_the_trich_dung_thong_tu(self):
		h107 = self._render(NAME_BIEN_BAN_TT107)
		h200 = self._render(NAME_BIEN_BAN_TT200)
		self.assertIn("107/2017/TT-BTC", h107)
		self.assertNotIn("200/2014/TT-BTC", h107)
		self.assertIn("200/2014/TT-BTC", h200)
		self.assertNotIn("107/2017/TT-BTC", h200)

	def test_hang_thieu_khong_bi_gop_vao_cot_hang_hong(self):
		"""Thiếu hàng và hàng hỏng là HAI sự việc. Gộp chúng vào cùng cột
		"không đúng quy cách" là khai sai trên một chứng từ pháp lý."""
		h = self._render(NAME_BIEN_BAN_TT107)
		self.assertIn("Thiếu", h, "Phần hàng thiếu phải hiện ở cột Ghi chú")
		# ...và KHÔNG bị cộng dồn vào cột "không đúng quy cách".
		doc = frappe.get_doc("Portal Delivery Inspection", self.bb)
		for r in doc.items:
			thieu = (r.sl_giao or 0) - (r.sl_nhan or 0) - (r.sl_tra or 0)
			if thieu > 0:
				gop = (r.sl_tra or 0) + thieu
				self.assertNotIn(
					f'class="num">{gop:g}<', h,
					"Số hàng hỏng bị cộng dồn với số hàng thiếu — hai sự việc "
					"khác nhau bị khai thành một.",
				)

	def _tao_bien_ban_co_thieu(self):
		"""Dựng biên bản có CẢ hỏng lẫn thiếu khi site chưa có cái nào.

		Không `skipTest`: mẫu in này tồn tại chính vì trường hợp đó, và một
		test tự bỏ qua mình khi thiếu dữ liệu là một test không bảo vệ gì.
		"""
		from miyano_portal.tests.test_e9_kiem_hang import _KiemHangBase  # noqa: F401

		doc = frappe.get_doc({
			"doctype": "Portal Delivery Inspection",
			"customer": frappe.db.get_value("Customer", {}, "name"),
			"delivery_note": f"DN-MAUIN-{frappe.generate_hash(length=6)}",
			"ngay_kiem": frappe.utils.nowdate(),
			"nguoi_kiem": "test@mauin.miyano",
			"trang_thai": "Nháp",
			"items": [{
				"item_code": frappe.db.get_value("Item", {"disabled": 0}, "name"),
				"item_name": "Vật tư test mẫu in", "uom": "Hộp",
				"sl_giao": 10, "sl_nhan": 6, "sl_tra": 2,
				"ly_do": "2 hỏng, 2 không tới",
			}],
		})
		doc.insert(ignore_permissions=True)
		doc.flags.ignore_permissions = True
		doc.submit()
		return doc.name


class TestMauPhieuXuat02VT(FrappeTestCase):
	"""Mẫu 02-VT bản **TT 99/2025** — "Phiếu xuất kho kiêm biên bản bàn giao".

	Nguồn của mẫu là `docs/04_MVL_PhieuXuatKho_GiaoHang(DN).docx` do chủ đầu
	tư giao 25/08/2026. Thông tư trích dẫn trên một chứng từ kế toán là thứ
	CHỈ chủ đầu tư/kế toán được chốt, nên bài dưới đây ghim cả vế DƯƠNG (có
	99/2025) lẫn vế ÂM (không còn 200/2014): thêm dòng mới mà quên gỡ dòng cũ
	là in ra một chứng từ trích hai thông tư.
	"""

	def setUp(self):
		install_bien_ban_print_formats()
		self.dn = frappe.db.get_value(
			"Delivery Note", {"docstatus": 1, "is_return": 0}, "name"
		)
		if not self.dn:
			self.skipTest("Site chưa có phiếu giao nào đã ghi sổ")

	def _render(self):
		doc = frappe.get_doc("Delivery Note", self.dn)
		return get_html_and_style(doc=doc.as_json(), print_format=NAME_PHIEU_XUAT_02VT)["html"]

	def test_dung_cau_truc_mau_02_vt(self):
		h = self._render()
		for phai_co in (
			"Mẫu số: 02 - VT",
			"Kèm theo Thông tư số 99/2025/TT-BTC",
			"ngày 27 tháng 10 năm 2025",
			"PHIẾU XUẤT KHO KIÊM BIÊN BẢN BÀN GIAO",
			"Số đơn hàng (SO/PO)", "Ngày, giờ bàn giao",
			"Số lô", "Hạn dùng", "SL thực xuất",
			"Tổng số tiền (viết bằng chữ)",
			"Hai bên đã kiểm tra và xác nhận",
			# Khối ký của bản mẫu: ĐÚNG bốn ô.
			"Người lập phiếu", "Thủ kho", "Người giao hàng", "Người nhận hàng",
			"info@miyano.com.vn",
		):
			self.assertIn(phai_co, h, f"mẫu 02-VT thiếu «{phai_co}»")

	def test_khong_con_dau_vet_ban_TT200(self):
		"""Vế ÂM. Không có bài này, một bản vá "thêm dòng TT 99/2025" mà quên
		gỡ dòng cũ vẫn xanh — và chứng từ in ra trích hai thông tư."""
		h = self._render()
		for khong_duoc_con in (
			"200/2014", "22/12/2014",
			# Bản mẫu bỏ hai ô ký này; giữ lại là bắt bệnh viện ký một biên
			# bản có ô trống mà không ai được phép ký vào.
			"Kế toán trưởng", "Giám đốc",
		):
			self.assertNotIn(khong_duoc_con, h, f"còn sót bản cũ: «{khong_duoc_con}»")

	def test_in_ra_DU_LIEU_THAT_cua_phieu(self):
		"""Răng cho bài cấu trúc: mọi khẳng định `assertIn` ở trên vẫn xanh
		khi từng ô dữ liệu TRỐNG. Bài này ghim đúng số liệu của phiếu."""
		doc = frappe.get_doc("Delivery Note", self.dn)
		h = self._render()
		self.assertIn(doc.name, h, "thiếu Mã phiếu")
		self.assertIn(doc.customer_name or doc.customer, h, "thiếu tên khách")
		for i in doc.items:
			self.assertIn(i.item_code, h, f"thiếu mã vật tư {i.item_code}")

	def test_cot_so_lo_va_han_dung_in_ra_lo_THAT(self):
		"""Hai cột mới của bản TT 99/2025.

		BẪY đã lường: quy tắc đọc lô của build này là **bundle TRƯỚC,
		`batch_no` sau** (`kho/delivery_hook`), nên một mẫu tự viết
		`{{ i.batch_no }}` in ô TRỐNG cho đúng những dòng tách nhiều lô — im
		lặng, trên một biên bản dược phẩm có chữ ký hai bên. Bài này dựng một
		`Batch` THẬT có `expiry_date` THẬT rồi khẳng định cả số lô lẫn hạn
		dùng đã định dạng ra được trên bản in.

		Dựng phiếu trong BỘ NHỚ (`as_json()` không cần bản ghi trong DB —
		đúng đường `printview` gọi): dựng một phiếu giao đã ghi sổ có lô đòi
		tồn kho thật, và một fixture phải nặn tồn kho ra để test một mẫu in
		là fixture sẽ hỏng vì lý do không liên quan gì tới mẫu in.
		"""
		from miyano_portal.kho.delivery_hook import lo_han_cho_in

		ma = "_TEST 02VT LO"
		if not frappe.db.exists("Item", ma):
			frappe.get_doc({
				"doctype": "Item", "item_code": ma, "item_name": ma,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Hộp", "is_stock_item": 1, "has_batch_no": 1,
				"create_new_batch": 1,
			}).insert(ignore_permissions=True)
		so_lo = "_TEST-LO-02VT-001"
		han = frappe.utils.add_days(frappe.utils.today(), 400)
		if not frappe.db.exists("Batch", so_lo):
			frappe.get_doc({
				"doctype": "Batch", "batch_id": so_lo, "item": ma,
				"expiry_date": han,
			}).insert(ignore_permissions=True)
		frappe.db.set_value("Batch", so_lo, "expiry_date", han)

		goc = frappe.get_doc("Delivery Note", self.dn)
		phieu = frappe.copy_doc(goc)
		phieu.items = []
		phieu.append("items", {
			"item_code": ma, "item_name": ma, "uom": "Hộp", "qty": 3,
			"rate": 10000, "amount": 30000, "batch_no": so_lo,
			"warehouse": goc.items[0].warehouse,
		})
		# Tiền đề: hàm dùng chung PHẢI đọc ra lô này — nếu nó trả rỗng thì
		# khẳng định bên dưới xanh/đỏ vì lý do khác hẳn mẫu in.
		doc_lo = lo_han_cho_in(phieu.items[0])
		self.assertEqual(doc_lo["so_lo"], so_lo)
		self.assertEqual(doc_lo["han_dung"], frappe.utils.formatdate(han, "dd/MM/yyyy"))

		h = get_html_and_style(doc=phieu.as_json(), print_format=NAME_PHIEU_XUAT_02VT)["html"]
		self.assertIn(so_lo, h, "cột Số lô in ra ô trống cho một dòng CÓ lô")
		self.assertIn(
			frappe.utils.formatdate(han, "dd/MM/yyyy"), h,
			"cột Hạn dùng in ra ô trống cho một lô CÓ hạn",
		)

	def test_khong_in_sentinel_KHONG_LO_len_chung_tu(self):
		"""`LOT_KHONG_CO` ("KHONG-LO") là quy ước NỘI BỘ của sổ kho cho hàng
		không quản theo lô. Nó lọt lên một chứng từ pháp lý là một chuỗi vô
		nghĩa với bệnh viện — và không ai đọc lại bản in để phát hiện."""
		h = self._render()
		self.assertNotIn("KHONG-LO", h)

	def test_tien_bang_chu_la_TIENG_VIET(self):
		"""frappe.utils.money_in_words đọc theo ngôn ngữ hệ thống — site để
		tiếng Anh nên từng in ra "Nine Hundred And Fifty Thousand" trên một
		chứng từ kế toán Việt Nam."""
		h = self._render()
		self.assertIn("đồng.", h)
		for tieng_anh in ("Thousand", "Hundred", "Million", "only."):
			self.assertNotIn(tieng_anh, h, f"còn sót tiếng Anh: {tieng_anh}")


class TestTienBangChu(FrappeTestCase):
	"""Cách đọc số tiếng Việt có bốn chỗ bẫy mà một vòng lặp ngây thơ sẽ sai:
	mốt/tư/lăm ở hàng đơn vị, và "linh" khi hàng chục bằng 0."""

	def test_cac_truong_hop_dac_biet(self):
		for so, mong in (
			(0, "Không đồng."),
			(15, "Mười lăm đồng."),
			(21, "Hai mươi mốt đồng."),
			(24, "Hai mươi tư đồng."),
			(25, "Hai mươi lăm đồng."),
			(105, "Một trăm linh năm đồng."),
			(1000, "Một nghìn đồng."),
			(1105, "Một nghìn một trăm linh năm đồng."),
			(1000005, "Một triệu không trăm linh năm đồng."),
			(1005000, "Một triệu không trăm linh năm nghìn đồng."),
			(28500000, "Hai mươi tám triệu năm trăm nghìn đồng."),
		):
			with self.subTest(so=so):
				self.assertEqual(tien_bang_chu(so), mong)

	def test_lam_tron_va_gia_tri_la(self):
		# VND không có phần lẻ trên chứng từ — làm tròn, không đọc "phẩy".
		self.assertEqual(tien_bang_chu(1000.4), "Một nghìn đồng.")
		self.assertEqual(tien_bang_chu(None), "Không đồng.")
		self.assertEqual(tien_bang_chu("x"), "")
