"""Patch chép ngược chín trường CR-03 từ PHIẾU sang các ĐƠN đã duyệt trước.

`dat_hang._xay_don` từng chép dòng "hàng chưa có trong hệ thống" bằng một
danh sách trắng bốn trường, nên chín trường CR-03 không bao giờ tới đơn. Vá ở
`999b39d` chỉ chữa cho đơn duyệt TỪ NAY; patch này chữa cho đơn cũ.

Đo trên site trước khi viết: 8 dòng đơn thiếu dữ liệu, trong đó 3 dòng có
phiếu gốc còn dữ liệu để chép ngược.

BỐN NGUYÊN TẮC, mỗi cái một bài — và hai bài quan trọng nhất là hai bài VẾ ÂM
(không đè, không đoán), vì đó là chỗ một patch chép dữ liệu gây hại được.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.patches.v1_33 import chep_nguoc_cr03_sang_don_cu as patch

DT = "Sales Order Dat Ngoai Item"
_ANH = '["/private/files/_test_patch_cr03.jpg"]'


class TestChepNguocCR03(FrappeTestCase):
	"""Dựng thẳng bản ghi con bằng SQL thô.

	CỐ Ý không dựng một Sales Order thật: patch chỉ đọc/ghi hai bảng con và
	field `custom_de_xuat`, còn dựng một đơn hàng ERPNext hợp lệ kéo theo kho,
	giá, thuế, công ty — toàn thứ không liên quan tới điều bài này canh, và
	mỗi thứ đó là một cách bài đỏ vì lý do sai.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		self.phieu = "_TEST-PATCH-PHIEU-" + frappe.generate_hash(length=6)
		self.don = "_TEST-PATCH-DON-" + frappe.generate_hash(length=6)
		frappe.db.sql(
			"""INSERT INTO `tabSales Order` (name, creation, modified, owner,
			     modified_by, docstatus, customer, custom_de_xuat)
			   VALUES (%s, NOW(), NOW(), 'Administrator', 'Administrator', 1,
			           '_TEST PATCH KH', %s)""",
			(self.don, self.phieu),
		)

	def tearDown(self):
		frappe.db.sql("DELETE FROM `tabSales Order` WHERE name = %s", self.don)
		frappe.db.sql(
			"DELETE FROM `tabSales Order Dat Ngoai Item` WHERE parent IN (%s, %s)",
			(self.don, self.phieu),
		)
		frappe.set_user("Administrator")

	def _dong(self, parent, parenttype, ten_hang, dvt="Hộp", **truong):
		ten = frappe.generate_hash(length=10)
		cot = {"name": ten, "parent": parent, "parenttype": parenttype,
		       "parentfield": "dat_ngoai" if parenttype == "Portal De Xuat Mua"
		                      else "custom_dat_ngoai",
		       "ten_hang": ten_hang, "dvt": dvt, "so_luong": 1, "idx": 1}
		cot.update(truong)
		khoa = ", ".join(f"`{k}`" for k in cot)
		gia = ", ".join(f"%({k})s" for k in cot)
		frappe.db.sql(
			f"""INSERT INTO `tabSales Order Dat Ngoai Item`
			    ({khoa}, creation, modified, owner, modified_by)
			    VALUES ({gia}, NOW(), NOW(), 'Administrator', 'Administrator')""",
			cot,
		)
		return ten

	def test_chep_du_chin_truong_bao_gom_ANH(self):
		"""Ảnh là thứ chủ đầu tư nêu đích danh — khẳng định nó tường minh."""
		self._dong(self.phieu, "Portal De Xuat Mua", "Thuốc thử Glucose",
		           model_ma="GLU-500", hang_san_xuat="Roche",
		           nuoc_san_xuat="Đức", quy_cach="hộp 100 test",
		           ncc_hien_tai="Công ty ABC", gia_hien_tai=1250000, anh=_ANH)
		d = self._dong(self.don, "Sales Order", "Thuốc thử Glucose")

		patch.execute()

		r = frappe.db.get_value(DT, d, patch.TRUONG_CHUOI + patch.TRUONG_SO,
		                        as_dict=True)
		self.assertEqual(r.anh, _ANH, "Trường ẢNH không được chép ngược")
		self.assertEqual(r.model_ma, "GLU-500")
		self.assertEqual(r.hang_san_xuat, "Roche")
		self.assertEqual(r.nuoc_san_xuat, "Đức")
		self.assertEqual(r.quy_cach, "hộp 100 test")
		self.assertEqual(r.ncc_hien_tai, "Công ty ABC")
		self.assertEqual(float(r.gia_hien_tai), 1250000.0)

	def test_KHONG_DE_len_o_da_co_gia_tri(self):
		"""Nguyên tắc 1 — vế âm quan trọng nhất.

		Nhân viên Miyano có thể đã tự gõ tay một model vào dòng đơn để làm
		việc. Đè lên là xoá công của họ để thay bằng dữ liệu cũ hơn — và một
		patch chạy hàng loạt thì xoá một lượt, không ai kịp thấy.
		"""
		self._dong(self.phieu, "Portal De Xuat Mua", "Dung dịch rửa",
		           model_ma="TU-PHIEU", hang_san_xuat="Roche")
		d = self._dong(self.don, "Sales Order", "Dung dịch rửa",
		               model_ma="NHAN-VIEN-TU-GO")

		patch.execute()

		r = frappe.db.get_value(DT, d, ["model_ma", "hang_san_xuat"], as_dict=True)
		self.assertEqual(
			r.model_ma, "NHAN-VIEN-TU-GO",
			"Patch ĐÈ lên giá trị nhân viên đã gõ — xoá công của họ",
		)
		# Ô đang rỗng thì VẪN điền: không đè không có nghĩa là không làm gì.
		self.assertEqual(r.hang_san_xuat, "Roche")

	def test_NHAP_NHANG_thi_bo_qua_khong_doan(self):
		"""Nguyên tắc 2 — hai dòng phiếu cùng tên cùng ĐVT thì không phân
		biệt được. Chép nhầm dữ liệu mặt hàng này sang mặt hàng kia còn tệ
		hơn để trống: người đọc không có cách nào biết mình đang đọc sai."""
		self._dong(self.phieu, "Portal De Xuat Mua", "Kim luồn", model_ma="A")
		self._dong(self.phieu, "Portal De Xuat Mua", "Kim luồn", model_ma="B")
		d = self._dong(self.don, "Sales Order", "Kim luồn")

		patch.execute()

		self.assertFalse(
			frappe.db.get_value(DT, d, "model_ma"),
			"Patch ĐOÁN khi có hai dòng phiếu trùng tên — chép nhầm dữ liệu "
			"mặt hàng này sang mặt hàng kia",
		)

	def test_khac_DVT_thi_khong_phai_mot_mat_hang(self):
		"""Nối bằng `ten_hang` MỘT MÌNH là quá lỏng: 'Găng tay' hộp và 'Găng
		tay' đôi là hai dòng khác nhau."""
		self._dong(self.phieu, "Portal De Xuat Mua", "Găng tay", dvt="Đôi",
		           model_ma="TU-PHIEU")
		d = self._dong(self.don, "Sales Order", "Găng tay", dvt="Hộp")

		patch.execute()

		self.assertFalse(frappe.db.get_value(DT, d, "model_ma"))

	def test_chay_lai_KHONG_doi_gi_them(self):
		"""Nguyên tắc 4 — patch chạy lại khi migrate; lần hai phải là no-op."""
		self._dong(self.phieu, "Portal De Xuat Mua", "Cuvette", model_ma="CUV-1")
		d = self._dong(self.don, "Sales Order", "Cuvette")

		patch.execute()
		lan1 = frappe.db.get_value(DT, d, ["model_ma", "modified"], as_dict=True)
		patch.execute()
		lan2 = frappe.db.get_value(DT, d, ["model_ma", "modified"], as_dict=True)

		self.assertEqual(lan1.model_ma, "CUV-1")
		self.assertEqual(lan2.model_ma, "CUV-1")
		self.assertEqual(lan1.modified, lan2.modified, "Lần hai vẫn ghi lại")

	def test_KHONG_dung_dau_thoi_gian_cua_dong_da_chot(self):
		"""Nguyên tắc 3 — ghi mà KHÔNG đổi `modified`.

		BÀI NÀY SINH RA TỪ MỘT PHÉP PHÁ KHÔNG ĐỎ: bỏ `update_modified=False`
		khỏi patch mà không bài nào đỏ, vì bài "chạy lại" chỉ canh tính bất
		biến — lần hai không ghi gì nên `modified` đứng yên bất kể. Nguyên tắc
		3 lúc đó không có lưới nào canh.

		Vì sao nó đáng canh: phần lớn đơn đã submit. Đổi `modified` của một
		chứng từ đã chốt là làm nhiễu mọi phép đối chiếu "ai sửa gì lúc nào" —
		và một patch chạy hàng loạt thì làm nhiễu một lượt, đúng thứ người ta
		sẽ cần tra khi có tranh chấp.

		Đặt `modified` về QUÁ KHỨ trước khi chạy: dùng `NOW()` thì lần ghi của
		patch rơi vào cùng một giây và phép so vẫn bằng nhau — bài xanh mà
		không canh gì.
		"""
		self._dong(self.phieu, "Portal De Xuat Mua", "Băng gạc", model_ma="BG-1")
		d = self._dong(self.don, "Sales Order", "Băng gạc")
		frappe.db.sql(
			"UPDATE `tabSales Order Dat Ngoai Item` SET modified = %s WHERE name = %s",
			("2020-01-01 00:00:00", d),
		)

		patch.execute()

		r = frappe.db.get_value(DT, d, ["model_ma", "modified"], as_dict=True)
		self.assertEqual(r.model_ma, "BG-1", "Patch đã không ghi gì — bài này "
		                 "chỉ có nghĩa khi lần ghi THẬT SỰ xảy ra")
		self.assertEqual(
			str(r.modified), "2020-01-01 00:00:00",
			"Patch đổi `modified` của dòng thuộc chứng từ đã chốt — làm nhiễu "
			"mọi phép đối chiếu 'ai sửa gì lúc nào'",
		)

	def test_don_KHONG_tro_ve_phieu_thi_bo_qua(self):
		"""Không có `custom_de_xuat` thì không có nguồn nào để chép — đoán
		theo khách/ngày là mời một phép nối sai."""
		frappe.db.set_value("Sales Order", self.don, "custom_de_xuat", None,
		                    update_modified=False)
		self._dong(self.phieu, "Portal De Xuat Mua", "Giấy in", model_ma="X")
		d = self._dong(self.don, "Sales Order", "Giấy in")

		patch.execute()

		self.assertFalse(frappe.db.get_value(DT, d, "model_ma"))
