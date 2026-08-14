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

    def test_dua_that_qua_endpoint_tra_don_cu_khong_nem_500(self):
        """TC-E1-02, phần chưa từng chạy end-to-end (P2 #8, kiểm thử hệ
        thống): `except frappe.UniqueValidationError` trong
        `_insert_so_idempotent()` — chốt "khách bấm lại không nhận lỗi 500"
        — chỉ được `test_tang_document_map_loi_thanh_UniqueValidationError`
        khoá đúng LOẠI exception, không có test nào từng gọi
        `portal_order_place()` LẦN THỨ HAI theo cách chạm được nhánh đó: một
        `request_id` đã tồn tại luôn bị chặn SỚM bởi phép kiểm-trước-khi-ghi
        ở đầu hàm (dòng `da_co = frappe.db.get_value(...)`), nên `so.insert()`
        — và do đó cả nhánh `except` — không bao giờ được thực thi qua
        đường thật.

        Không dùng thread thật (cùng lý do đã ghi ở
        `test_csdl_that_su_co_rang_buoc_unique`: `FrappeTestCase` chạy trong
        một transaction, hai thread sẽ không thấy nhau). Thay vào đó vá TẠM
        đúng MỘT lệnh đọc để mô phỏng chính xác thứ tự sự kiện của một cuộc
        đua thật: tại thời điểm đọc, tiến trình kia CHƯA commit (get_value
        trả None) — nhưng tại thời điểm ghi, nó ĐÃ commit (đơn gốc thật đã
        nằm trong DB), nên `so.insert()` ăn đúng lỗi 1062 → `UniqueValidationError`
        thật của MariaDB, không phải một ngoại lệ giả lập tay."""
        rid = _rid()
        goc = self._dat(rid)

        goc_get_value = frappe.db.get_value
        da_bo_qua_mot_lan = {"xong": False}

        def _gia_lap_doc_som(doctype, filters=None, *args, **kwargs):
            if (
                not da_bo_qua_mot_lan["xong"]
                and doctype == "Sales Order"
                and isinstance(filters, dict)
                and filters.get("custom_request_id") == rid
            ):
                da_bo_qua_mot_lan["xong"] = True
                return None  # mô phỏng: đọc xảy ra TRƯỚC khi bản ghi kia commit
            return goc_get_value(doctype, filters, *args, **kwargs)

        frappe.db.get_value = _gia_lap_doc_som
        try:
            lan2 = self._dat(rid)  # KHÔNG được ném 500
        finally:
            frappe.db.get_value = goc_get_value

        self.assertTrue(da_bo_qua_mot_lan["xong"], "phép vá không chạm nhánh nào — test tự vô nghĩa")
        self.assertTrue(lan2["da_ton_tai"])
        self.assertEqual(lan2["sales_order"], goc["sales_order"])
        self.assertEqual(lan2["total"], goc["total"])
        self.assertEqual(
            frappe.db.count("Sales Order", {"custom_request_id": rid}), 1,
            "CSDL vẫn chỉ có đúng một đơn — ràng buộc unique đã chặn bản ghi thứ hai",
        )

    def test_uniquevalidationerror_cua_truong_khac_khong_bi_nuot_thanh_da_ton_tai(self):
        """Nhánh con `if not cu: raise` bên trong cùng `except` — cùng
        UniqueValidationError, nhưng do MỘT trường unique KHÁC trên Sales
        Order bị vi phạm (không phải custom_request_id của lần gọi này). Nếu
        `_insert_so_idempotent` nuốt mọi UniqueValidationError thành "đơn đã
        tồn tại" bất kể nguyên nhân, một lỗi dữ liệu THẬT sẽ biến mất, khách
        thấy 'đơn đã tồn tại' cho một đơn không hề tồn tại.

        Ép cả hai lệnh đọc `frappe.db.get_value(..., custom_request_id=rid)`
        trong `_insert_so_idempotent` đều trả None (không riêng lệnh đầu như
        test trên) — mô phỏng đúng tình huống "cu = None": `so.insert()` vẫn
        ăn UniqueValidationError thật (đơn gốc đã tồn tại thật trong DB), nhưng
        khi hàm tự tra lại theo custom_request_id để xác nhận nguyên nhân, nó
        không tìm thấy gì — phải re-raise, không được trả về như thành công."""
        rid = _rid()
        self._dat(rid)

        goc_get_value = frappe.db.get_value

        def _luon_khong_thay(doctype, filters=None, *args, **kwargs):
            if (
                doctype == "Sales Order"
                and isinstance(filters, dict)
                and filters.get("custom_request_id") == rid
            ):
                return None
            return goc_get_value(doctype, filters, *args, **kwargs)

        frappe.db.get_value = _luon_khong_thay
        try:
            with self.assertRaises(frappe.UniqueValidationError):
                self._dat(rid)
        finally:
            frappe.db.get_value = goc_get_value

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
