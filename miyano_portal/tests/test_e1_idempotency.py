"""BR-O12 / US-E1.1 / NL-1.8 — chống tạo đơn trùng. TC-E1-01, TC-E1-02.

Cũng phủ phần API của US-E1.2 (bội số, ngày giao) vì cả ba quy tắc nối vào
cùng một chỗ trong `portal_order_place` — TC-E1-03, TC-E1-04.

Chốt chặn thật là ràng buộc `unique` trên `Sales Order.custom_request_id`,
tức **CSDL** làm trọng tài chứ không phải một phép kiểm trước-khi-ghi. Đó là
toàn bộ điểm mấu chốt của TC-E1-02: kiểm-rồi-ghi vẫn để lọt hai đơn khi hai
tiến trình cùng đọc thấy "chưa có".
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import seed_demo

VT = "VT0005"  # hạn mức 10.000 trong seed_demo — thoải mái cho các ca dưới


def _rid() -> str:
    return frappe.generate_hash(length=12)


class TestIdempotencyDatHang(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        self.bo = portal.portal_contracts()[0]["name"]

    def _dat(self, request_id, qty=1):
        return portal.portal_order_place(
            self.bo,
            json.dumps([{"item_code": VT, "qty": qty}]),
            request_id=request_id,
        )

    # ---------- TC-E1-01 ----------
    def test_goi_hai_lan_cung_request_id_chi_tao_mot_don(self):
        rid = _rid()
        lan1 = self._dat(rid)
        self.assertFalse(lan1["da_ton_tai"])

        lan2 = self._dat(rid)
        self.assertTrue(lan2["da_ton_tai"])
        self.assertEqual(lan2["sales_order"], lan1["sales_order"])

        self.assertEqual(
            frappe.db.count("Sales Order", {"custom_request_id": rid}),
            1,
            "CSDL chỉ được có đúng một đơn cho mỗi mã yêu cầu",
        )

    def test_lan_hai_tra_dung_tong_tien_cua_don_cu(self):
        """Không chỉ trả tên đơn: giao diện hiển thị lại tổng tiền, trả 0 sẽ
        làm khách tưởng đơn rỗng."""
        rid = _rid()
        lan1 = self._dat(rid, qty=3)
        lan2 = self._dat(rid, qty=3)
        self.assertEqual(lan2["total"], lan1["total"])
        self.assertGreater(lan2["total"], 0)

    def test_request_id_khac_nhau_tao_don_khac_nhau(self):
        a = self._dat(_rid())
        b = self._dat(_rid())
        self.assertNotEqual(a["sales_order"], b["sales_order"])

    def test_thieu_request_id_bi_tu_choi(self):
        """Bắt buộc, không tuỳ chọn. Để tuỳ chọn thì một client cũ vẫn tạo
        được đơn trùng và quy tắc chỉ còn là trang trí."""
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal.portal_order_place(
                self.bo, json.dumps([{"item_code": VT, "qty": 1}])
            )
        self.assertIn("mã yêu cầu", str(ctx.exception).lower())

    # ---------- TC-E1-02: đua ----------
    def test_csdl_that_su_co_rang_buoc_unique(self):
        """Ghi thẳng bằng SQL, bỏ qua mọi tầng Python — đúng thứ CSDL gặp khi
        hai tiến trình cùng ghi.

        KHÔNG dùng thread thật: `FrappeTestCase` chạy trong MỘT transaction
        nên hai thread sẽ không thấy nhau và test sẽ xanh một cách vô nghĩa.

        Ở tầng này lỗi là `IntegrityError` thô của driver — Frappe chưa map
        gì cả vì ta không đi qua `Document`.
        """
        import pymysql

        rid = _rid()
        self._dat(rid)
        with self.assertRaises(pymysql.err.IntegrityError):
            frappe.db.sql(
                """insert into `tabSales Order`
                   (name, customer, custom_request_id, docstatus,
                    creation, modified, owner, modified_by)
                   values (%s, 'Bệnh viện Bạch Mai', %s, 0,
                           now(), now(), 'Administrator', 'Administrator')""",
                (f"_TEST-DUP-{rid}", rid),
            )

    def test_tang_document_map_loi_thanh_UniqueValidationError(self):
        """Chốt đúng loại exception mà `portal_order_place` phải bắt.

        Bản cài đặt đầu tiên bắt `DuplicateEntryError` và SAI: `Document.insert`
        map lỗi 1062 của MariaDB thành `UniqueValidationError`
        (`base_document.py:672`), còn `DuplicateEntryError` dành cho trùng
        `name`. Bắt nhầm loại thì nhánh xử lý đua không bao giờ chạy và khách
        nhận lỗi 500 — một bug chỉ lộ ra dưới tải thật. Test này khoá lại
        điều đó.
        """
        rid = _rid()
        self._dat(rid)
        khac = frappe.new_doc("Sales Order")
        khac.customer = "Bệnh viện Bạch Mai"
        khac.transaction_date = frappe.utils.today()
        khac.delivery_date = frappe.utils.add_days(frappe.utils.today(), 5)
        khac.custom_request_id = rid
        khac.append("items", {
            "item_code": VT, "qty": 1, "rate": 1000,
            "delivery_date": frappe.utils.add_days(frappe.utils.today(), 5),
        })
        with self.assertRaises(frappe.UniqueValidationError):
            khac.insert(ignore_permissions=True)

    def test_ma_yeu_cau_cua_khach_khac_khong_bi_lo(self):
        """Trả 403 chứ không trả đơn: xác nhận sự tồn tại của một mã yêu cầu
        thuộc khách khác đã là rò rỉ."""
        rid = _rid()
        self._dat(rid)
        frappe.set_user("Administrator")
        khach_khac = frappe.get_all(
            "Customer", filters={"name": ["!=", "Bệnh viện Bạch Mai"]}, pluck="name"
        )
        if not khach_khac:
            self.skipTest("Site không có khách hàng thứ hai để thử cách ly.")
        frappe.db.set_value(
            "Sales Order",
            {"custom_request_id": rid},
            "customer",
            khach_khac[0],
        )
        frappe.set_user("bvbm@demo.miyano")
        with self.assertRaises(frappe.PermissionError):
            self._dat(rid)


class TestBoiSoVaNgayGiaoQuaAPI(FrappeTestCase):
    """Phần API của US-E1.2 — server là chốt cuối, client bỏ qua được."""

    def setUp(self):
        seed_demo()
        frappe.db.set_value("Item", VT, "custom_boi_so_dat", 10)
        self.addCleanup(frappe.db.set_value, "Item", VT, "custom_boi_so_dat", 0)
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        self.bo = portal.portal_contracts()[0]["name"]

    # TC-E1-03
    def test_sai_boi_so_bi_chan_du_gui_thang_api(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal.portal_order_place(
                self.bo,
                json.dumps([{"item_code": VT, "qty": 15}]),
                request_id=_rid(),
            )
        loi = str(ctx.exception)
        self.assertIn("bội số của 10", loi)
        self.assertIn("Gần nhất: 20", loi)

    def test_dung_boi_so_thi_di_qua(self):
        kq = portal.portal_order_place(
            self.bo, json.dumps([{"item_code": VT, "qty": 20}]), request_id=_rid()
        )
        self.assertEqual(
            frappe.db.get_value("Sales Order", kq["sales_order"], "docstatus"), 0
        )

    # TC-E1-04
    def test_ngay_giao_qua_khu_bi_chan(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal.portal_order_place(
                self.bo,
                json.dumps([{"item_code": VT, "qty": 10}]),
                delivery_date=frappe.utils.add_days(frappe.utils.today(), -1),
                request_id=_rid(),
            )
        self.assertIn("Ngày giao sớm nhất là", str(ctx.exception))

    def test_khong_truyen_ngay_giao_thi_mac_dinh_la_ngay_lam_viec(self):
        from frappe.utils import getdate

        kq = portal.portal_order_place(
            self.bo, json.dumps([{"item_code": VT, "qty": 10}]), request_id=_rid()
        )
        ngay = getdate(
            frappe.db.get_value("Sales Order", kq["sales_order"], "delivery_date")
        )
        self.assertLess(ngay.weekday(), 5, "ngày giao mặc định rơi vào cuối tuần")
        self.assertGreater(ngay, getdate(frappe.utils.today()))
