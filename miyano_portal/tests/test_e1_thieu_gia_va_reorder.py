"""US-E1.4 (thiếu giá → báo sales) và US-E1.5 (đặt lại đơn cũ).

TC-E1-09, TC-E1-10.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_thong_bao import bao_thieu_gia
from miyano_portal.setup.seed_demo import seed_demo

BVBM = "Bệnh viện Bạch Mai"
USER_BVBM = "bvbm@demo.miyano"
USER_SALES = "sales_user@demo.miyano"
VT = "VT0005"
HC = "HC0009"


def _rid() -> str:
    return frappe.generate_hash(length=12)


class TestThieuGia(FrappeTestCase):
    def setUp(self):
        seed_demo()
        # Gán sales phụ trách để có người nhận thông báo. Không có thì
        # `bao_thieu_gia` im lặng bỏ qua — đúng thiết kế, nhưng test sẽ không
        # kiểm được gì.
        frappe.db.set_value("Customer", BVBM, "account_manager", USER_SALES)
        # Xoá giá của HC0009 bằng cách đặt về 0 (falsy) — cách rẻ nhất để tái
        # lập "mặt hàng có trong hợp đồng nhưng chưa có giá bán".
        self.gia_cu = frappe.db.get_value(
            "Item Price", {"item_code": HC, "price_list": "HĐNT-BVBM-2026"}, "name"
        )
        frappe.db.set_value("Item Price", self.gia_cu, "price_list_rate", 0)

        # `FrappeTestCase` rollback một lần mỗi CLASS, không phải mỗi test:
        # `Notification Log` do ca chạy trước tạo ra vẫn còn khi ca sau chạy,
        # và cơ chế chống spam theo ngày sẽ trả False. Không dọn ở đây thì
        # các ca phụ thuộc thứ tự chạy — đúng loại phụ thuộc ngầm đã làm đỏ
        # suite một lần rồi.
        frappe.db.delete("Notification Log", {"subject": ("like", "Portal - Thiếu giá%")})

        frappe.set_user(USER_BVBM)
        self.addCleanup(frappe.set_user, "Administrator")
        self.bo = portal.portal_contracts()[0]["name"]

    # ---------- TC-E1-09 ----------
    def test_dat_hang_thieu_gia_bi_chan_dung_nguyen_van(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal.portal_order_place(
                self.bo, json.dumps([{"item_code": HC, "qty": 1}]), request_id=_rid()
            )
        loi = str(ctx.exception)
        self.assertIn(HC, loi)
        # Nguyên văn ma trận FormSpec §5, dòng NL-1.4.
        self.assertIn("chưa có giá trong hợp đồng", loi)
        self.assertIn("Miyano đã nhận được thông báo", loi)

    def test_bi_chan_thi_sales_nhan_duoc_thong_bao(self):
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                self.bo, json.dumps([{"item_code": HC, "qty": 1}]), request_id=_rid()
            )
        frappe.set_user("Administrator")
        self.assertTrue(
            frappe.db.exists(
                "Notification Log", {"for_user": USER_SALES, "subject": ("like", f"%{HC}%")}
            ),
            "sales phụ trách phải nhận được thông báo thiếu giá",
        )

    def test_chi_bao_mot_lan_moi_ngay_cho_moi_cap_khach_mat_hang(self):
        """Khách mở danh mục mười lần trong ngày không được thành mười thông
        báo cho cùng một nhân viên."""
        frappe.set_user("Administrator")
        self.assertTrue(bao_thieu_gia(BVBM, HC))
        self.assertFalse(bao_thieu_gia(BVBM, HC), "lần thứ hai trong ngày không gửi lại")
        self.assertEqual(
            frappe.db.count(
                "Notification Log",
                {"for_user": USER_SALES, "subject": ("like", f"%{HC}%")},
            ),
            1,
        )

    def test_mat_hang_khac_van_duoc_bao_rieng(self):
        """Chống spam theo CẶP (khách, mặt hàng), không phải theo khách —
        chặn cả mặt hàng thứ hai là giấu mất một nhu cầu thật."""
        frappe.set_user("Administrator")
        self.assertTrue(bao_thieu_gia(BVBM, HC))
        self.assertTrue(bao_thieu_gia(BVBM, VT))

    def test_khach_khong_co_sales_phu_trach_thi_im_lang(self):
        """Không có người nhận thì không tạo bản ghi rác, và tuyệt đối không
        được ném lỗi — khách vẫn phải nhận đúng thông điệp thiếu giá."""
        frappe.set_user("Administrator")
        frappe.db.set_value("Customer", BVBM, "account_manager", None)
        self.assertFalse(bao_thieu_gia(BVBM, HC))


class TestReorder(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user(USER_BVBM)
        self.addCleanup(frappe.set_user, "Administrator")
        self.bo = portal.portal_contracts()[0]["name"]
        for item_code, qty, da_dat in ((VT, 10000, 0), (HC, 500, 0)):
            frappe.db.set_value(
                "Blanket Order Item",
                {"parent": self.bo, "item_code": item_code},
                {"qty": qty, "ordered_qty": da_dat},
            )
        self.don = portal.portal_order_place(
            self.bo,
            json.dumps([{"item_code": VT, "qty": 2}, {"item_code": HC, "qty": 3}]),
            request_id=_rid(),
        )["sales_order"]

    # ---------- TC-E1-10 ----------
    def test_reorder_dien_lai_gio_va_liet_ke_dong_bi_loai(self):
        # Vắt cạn hạn mức của HC0009 sau khi đơn cũ đã tồn tại.
        frappe.db.set_value(
            "Blanket Order Item",
            {"parent": self.bo, "item_code": HC},
            "ordered_qty",
            500,
        )
        kq = portal.portal_reorder(self.don)

        self.assertEqual({d["item_code"] for d in kq["gio_hang"]}, {VT})
        self.assertEqual(
            {d["item_code"]: d["ly_do"] for d in kq["bi_loai"]}, {HC: "het_han_muc"}
        )

    def test_gio_hang_du_thong_tin_de_ve_man_hinh(self):
        """Giỏ dựng thẳng từ payload này — thiếu tên hoặc ĐVT thì khách nhìn
        thấy mã hàng trần."""
        kq = portal.portal_reorder(self.don)
        for d in kq["gio_hang"]:
            with self.subTest(item=d["item_code"]):
                self.assertTrue(d["item_name"])
                self.assertNotEqual(d["item_name"], d["item_code"])
                self.assertTrue(d["uom"])
                self.assertIn("remaining", d)

    def test_gia_la_gia_hien_hanh_khong_phai_gia_luu_tren_don_cu(self):
        frappe.set_user("Administrator")
        frappe.db.set_value(
            "Item Price",
            {"item_code": VT, "price_list": "HĐNT-BVBM-2026"},
            "price_list_rate",
            9999,
        )
        frappe.set_user(USER_BVBM)
        kq = portal.portal_reorder(self.don)
        dong_vt = next(d for d in kq["gio_hang"] if d["item_code"] == VT)
        self.assertEqual(dong_vt["gia_hien_hanh"], 9999.0)

    def test_khong_gioi_han_thi_giu_nguyen_so_luong_cu(self):
        frappe.db.set_value(
            "Blanket Order Item", {"parent": self.bo, "item_code": HC}, "qty", 0
        )
        kq = portal.portal_reorder(self.don)
        dong_hc = next(d for d in kq["gio_hang"] if d["item_code"] == HC)
        self.assertEqual(dong_hc["qty"], 3.0)

    def test_so_luong_bi_ha_xuong_phan_con_dat_duoc(self):
        """Còn 1 mà đơn cũ đặt 3 thì điền 1, không phải loại cả dòng — khách
        vẫn đặt được phần còn lại."""
        frappe.db.set_value(
            "Blanket Order Item",
            {"parent": self.bo, "item_code": HC},
            "ordered_qty",
            499,
        )
        kq = portal.portal_reorder(self.don)
        dong_hc = next(d for d in kq["gio_hang"] if d["item_code"] == HC)
        self.assertEqual(dong_hc["qty"], 1.0)

    def test_reorder_don_cua_khach_khac_bi_tu_choi(self):
        frappe.set_user("Administrator")
        don_khac = frappe.get_all(
            "Sales Order", filters={"customer": ["!=", BVBM]}, pluck="name", limit=1
        )
        if not don_khac:
            self.skipTest("Site không có đơn của khách khác để thử cách ly.")
        frappe.set_user(USER_BVBM)
        with self.assertRaises((frappe.PermissionError, frappe.DoesNotExistError)):
            portal.portal_reorder(don_khac[0])
