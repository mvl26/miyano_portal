"""US-E1.5 — đặt lại đơn cũ (TC-E1-10).

Từ spec 2026-10-09 (giá theo Price List, §4.2) đường ĐẶT HÀNG không còn chặn
đơn vì thiếu giá — mặt hàng chưa có giá thành dòng chờ báo giá. Thông báo
"Portal - Thiếu giá" cho sales (US-E1.4, hàm `portal_thong_bao.bao_thieu_gia`)
vì thế không còn nơi gọi và đã gỡ cùng các bài của nó; tên file giữ nguyên để
lịch sử git của các bài đặt lại không đứt.

§4.4 cùng spec: ĐẶT LẠI đơn cũ cũng theo Price List — không còn loại dòng vì
"ngoài hợp đồng" / "hết hạn mức" / "thiếu giá", không còn hạ số lượng theo hạn
mức. Chỉ mặt hàng ngừng kinh doanh mới vào `bi_loai`.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bang_gia_khach
from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.tests.fixtures_hop_dong import hop_dong_hieu_luc_dau_tien

BVBM = "Bệnh viện Bạch Mai"
USER_BVBM = "bvbm@demo.miyano"
VT = "VT0005"
HC = "HC0009"


def _rid() -> str:
    return frappe.generate_hash(length=12)


class TestReorder(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user(USER_BVBM)
        self.addCleanup(frappe.set_user, "Administrator")
        self.bo = hop_dong_hieu_luc_dau_tien()
        for item_code, qty, da_dat in ((VT, 10000, 0), (HC, 500, 0)):
            frappe.db.set_value(
                "Blanket Order Item",
                {"parent": self.bo, "item_code": item_code},
                {"qty": qty, "ordered_qty": da_dat},
            )
        # Tiền đề của cả lớp: hai mã đều CÓ GIÁ lúc lập đơn cũ, nên giỏ ra
        # MỘT đơn (giỏ trộn có giá / chưa giá sẽ tách thành hai phiếu).
        for ma in (VT, HC):
            self.assertIsNotNone(bang_gia_khach.gia_bang_gia(BVBM, ma))
        self.don = portal.portal_order_place(
            self.bo,
            json.dumps([{"item_code": VT, "qty": 2}, {"item_code": HC, "qty": 3}]),
            request_id=_rid(),
        )["sales_order"]

    def _mat_gia(self, item_code):
        """Làm `item_code` MẤT GIÁ trong Price List của BVBM sau khi đơn cũ
        đã lập: hạ mọi dòng giá bán của mã về 0 (bộ đọc bỏ qua dòng `<= 0`).

        `FrappeTestCase` rollback một lần mỗi CLASS — phải trả giá lại ngay
        sau bài, nếu không `setUp` của bài sau lập đơn với một mã chưa giá."""
        frappe.set_user("Administrator")
        bang = frappe.db.get_value("Customer", BVBM, "default_price_list")
        for r in frappe.get_all(
            "Item Price",
            filters={"item_code": item_code, "price_list": bang, "selling": 1},
            fields=["name", "price_list_rate"],
        ):
            frappe.db.set_value("Item Price", r.name, "price_list_rate", 0)
            self.addCleanup(
                frappe.db.set_value, "Item Price", r.name, "price_list_rate",
                r.price_list_rate,
            )
        self.assertIsNone(
            bang_gia_khach.gia_bang_gia(BVBM, item_code),
            "tiền đề: mã phải THẬT SỰ không còn giá",
        )
        frappe.set_user(USER_BVBM)

    # ---------- TC-E1-10 ----------
    def test_reorder_dua_ca_hang_chua_co_gia_vao_gio(self):
        # Đảo theo spec 2026-10-09 (giá theo Price List). Bài cũ khẳng định
        # dòng không đặt được theo hợp đồng bị LOẠI khỏi giỏ; giờ mã chưa có
        # giá vào giỏ ở tầng chờ báo giá, như khi khách chọn nó từ danh mục.
        self._mat_gia(HC)
        kq = portal.portal_reorder(self.don)
        theo_ma = {d["item_code"]: d for d in kq["gio_hang"]}
        self.assertEqual(set(theo_ma), {VT, HC})
        self.assertEqual(theo_ma[VT]["tang"], "bang_gia")
        self.assertEqual(
            theo_ma[VT]["gia_hien_hanh"], bang_gia_khach.gia_bang_gia(BVBM, VT)
        )
        self.assertEqual(theo_ma[HC]["tang"], "cho_bao_gia")
        self.assertIsNone(theo_ma[HC]["gia_hien_hanh"])
        self.assertEqual(kq["bi_loai"], [])

    def test_reorder_loai_hang_ngung_kinh_doanh(self):
        frappe.db.set_value("Item", VT, "disabled", 1)
        self.addCleanup(frappe.db.set_value, "Item", VT, "disabled", 0)
        kq = portal.portal_reorder(self.don)
        self.assertEqual(
            kq["bi_loai"],
            [{"item_code": VT, "ly_do": "mat_hang_ngung_kinh_doanh"}],
        )
        self.assertEqual({d["item_code"] for d in kq["gio_hang"]}, {HC})

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_gio_hang_du_thong_tin_de_ve_man_hinh(self):
        """Giỏ dựng thẳng từ payload này — thiếu tên hoặc ĐVT thì khách nhìn
        thấy mã hàng trần."""
        kq = portal.portal_reorder(self.don)
        self.assertEqual(len(kq["gio_hang"]), 2)
        for d in kq["gio_hang"]:
            with self.subTest(item=d["item_code"]):
                self.assertTrue(d["item_name"])
                self.assertNotEqual(d["item_name"], d["item_code"])
                self.assertTrue(d["uom"])
                self.assertEqual(d["tang"], "bang_gia")
                self.assertGreater(d["gia_hien_hanh"], 0)

    def test_reorder_bo_qua_dong_giu_cho(self):
        """Dòng giữ chỗ kỹ thuật không phải thứ khách đặt: không vào giỏ, cũng
        không vào `bi_loai`."""
        frappe.set_user("Administrator")
        ten_dong = frappe.db.get_value(
            "Sales Order Item", {"parent": self.don, "item_code": HC}, "name"
        )
        frappe.db.set_value(
            "Sales Order Item", ten_dong, "item_code", ITEM_GIU_CHO,
            update_modified=False,
        )
        frappe.set_user(USER_BVBM)
        kq = portal.portal_reorder(self.don)
        self.assertEqual([d["item_code"] for d in kq["gio_hang"]], [VT])
        self.assertEqual(kq["bi_loai"], [])

    # Đảo theo spec 2026-10-09 (giá theo Price List).
    def test_gia_la_gia_hien_hanh_khong_phai_gia_luu_tren_don_cu(self):
        """Giá lấy từ Price List HÔM NAY, không lấy giá đóng trên đơn cũ."""
        gia_cu = float(
            frappe.db.get_value(
                "Sales Order Item", {"parent": self.don, "item_code": VT}, "rate"
            )
        )
        self.assertNotEqual(gia_cu, 9999.0, "tiền đề: giá đơn cũ khác giá sắp đặt")
        frappe.set_user("Administrator")
        bang = frappe.db.get_value("Customer", BVBM, "default_price_list")
        gia_truoc = bang_gia_khach.ghi_gia_vao_bang(bang, BVBM, VT, 9999)
        self.addCleanup(bang_gia_khach.ghi_gia_vao_bang, bang, BVBM, VT, gia_truoc)
        frappe.set_user(USER_BVBM)
        kq = portal.portal_reorder(self.don)
        dong_vt = next(d for d in kq["gio_hang"] if d["item_code"] == VT)
        self.assertEqual(dong_vt["gia_hien_hanh"], 9999.0)

    def test_het_han_muc_hop_dong_khong_con_loai_hay_ha_so_luong(self):
        # Đảo theo spec 2026-10-09 (giá theo Price List). Hai bài cũ: hết hạn
        # mức thì loại dòng (`het_han_muc`), còn 1 thì hạ 3 xuống 1. Cổng
        # không còn đặt theo hạn mức hợp đồng — số lượng đơn cũ giữ nguyên.
        frappe.db.set_value(
            "Blanket Order Item",
            {"parent": self.bo, "item_code": HC},
            "ordered_qty",
            500,
        )
        kq = portal.portal_reorder(self.don)
        dong_hc = next(d for d in kq["gio_hang"] if d["item_code"] == HC)
        self.assertEqual(dong_hc["qty"], 3.0)
        self.assertEqual(kq["bi_loai"], [])

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
