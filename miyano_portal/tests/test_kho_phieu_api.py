"""Test cho các endpoint chứng từ kho (Phase 3): danh sách/chi tiết phiếu,
tạo/sửa nháp, ghi sổ, huỷ, gợi ý lô FEFO, và in PDF.

Theo đúng khuôn của test_kho_api.py: gọi thẳng hàm trong miyano_portal.api.kho
dưới frappe.set_user(...), không đi qua HTTP — nhưng đây CHÍNH LÀ cổng duy
nhất mà portal dùng, nên test này phủ đúng đường đi thật.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import kho as kho_api
from miyano_portal.kho import ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


class _KhoApiFixture(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete(
            "Customer Stock Ledger Entry",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )
        frappe.db.delete(
            "Customer Stock Lot Balance",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )

    def tearDown(self):
        frappe.set_user("Administrator")

    def _nhap(self, kho=None, vat_tu=None, so_lo="LO-A", so_luong=100, don_gia=50000,
              han=None, submit=True, user=None):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": kho or self.kho["kho_bm"],
            "ngay": "2026-02-01",
            "loai_nhap": "Nhập khác",
            "nguoi_giao": "Trần Văn Giao",
            "items": [{
                "vat_tu": vat_tu or self.kho["vt_bm"],
                "so_lo": so_lo,
                "han_su_dung": han,
                "so_luong": so_luong,
                "don_gia": don_gia,
            }],
        })
        doc.insert(ignore_permissions=True)
        if submit:
            doc.submit()
        return doc


class TestKhoPhieuList(_KhoApiFixture):
    def test_list_shows_only_own_kho_newest_first(self):
        r1 = self._nhap(so_lo="LO-A")
        r2 = self._nhap(kho=self.kho["kho_pxn"], vat_tu=self.kho["vt_pxn"], so_lo="LO-PXN")
        r3 = self._nhap(so_lo="LO-C")

        frappe.set_user(BM_USER)
        rows = kho_api.kho_phieu_list("nhap")
        names = [r["name"] for r in rows]
        self.assertIn(r1.name, names)
        self.assertIn(r3.name, names)
        # Positive control: PXN really has a receipt, proving the absence
        # below is filtering, not "nobody has data".
        self.assertTrue(frappe.db.exists("Customer Stock Receipt", r2.name))
        self.assertNotIn(r2.name, names)
        self.assertEqual(names[0], r3.name, "mới nhất phải đứng đầu")

    def test_list_reports_vietnamese_status(self):
        doc = self._nhap()
        frappe.set_user(BM_USER)
        rows = kho_api.kho_phieu_list("nhap")
        row = next(r for r in rows if r["name"] == doc.name)
        self.assertEqual(row["trang_thai"], "Đã ghi sổ")

    def test_invalid_loai_rejected_in_vietnamese(self):
        """Khẳng định đúng thông điệp "không hợp lệ", không chỉ "có lỗi nào
        đó": nếu guard trong _doctype_tu_loai() bị gỡ, `doctype` trở thành
        None và kho_phieu_list ném KeyError khi tra `_LOAI_FIELD[None]` —
        _phieu_action vẫn dịch nó thành ValidationError chung chung, nên một
        assertion lỏng kiểu "assertRaises(ValidationError)" sẽ xanh giả (đã tự
        kiểm chứng bằng mutation). Chỉ có khẳng định đúng câu chữ mới bắt
        được guard cụ thể này.
        """
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_list("banana")
        msg = str(ctx.exception)
        self.assertIn("không hợp lệ", msg)
        self.assertNotIn("Traceback", msg)


class TestKhoPhieuGet(_KhoApiFixture):
    def test_get_own_voucher(self):
        doc = self._nhap()
        frappe.set_user(BM_USER)
        out = kho_api.kho_phieu_get("Customer Stock Receipt", doc.name)
        self.assertEqual(out["name"], doc.name)
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["vat_tu"], self.kho["vt_bm"])

    def test_get_other_customers_voucher_denied(self):
        doc = self._nhap(kho=self.kho["kho_pxn"], vat_tu=self.kho["vt_pxn"])
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_phieu_get("Customer Stock Receipt", doc.name)

    def test_get_rejects_doctype_outside_whitelist(self):
        """Kiểm thẳng _phieu_cua_kho(), không đi qua kho_phieu_get(): hàm đó
        được bọc bởi _phieu_action, vốn dịch MỌI ngoại lệ lạ (kể cả một
        DB error do doctype không có field `kho`) thành cùng một
        ValidationError chung chung — nếu test gọi qua kho_phieu_get() và chỉ
        khẳng định "có ValidationError, không traceback", nó sẽ pass ngay cả
        khi guard danh sách trắng bị gỡ (đã tự kiểm chứng bằng mutation:
        xoá guard nhưng vẫn xanh vì lưới an toàn của decorator che mất).
        Muốn bắt đúng guard, phải khẳng định đúng thông điệp "không hợp lệ"
        VÀ gọi thẳng hàm chứa guard đó.
        """
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api._phieu_cua_kho("Sales Invoice", "SOMETHING", self.kho["kho_bm"])
        self.assertIn("không hợp lệ", str(ctx.exception))
        self.assertNotIn("Traceback", str(ctx.exception))

        # Positive control qua endpoint thật: vẫn phải bị chặn (dù không phải
        # luôn cùng loại ngoại lệ do decorator có thể dịch lại).
        with self.assertRaises((frappe.ValidationError, frappe.PermissionError)) as ctx2:
            kho_api.kho_phieu_get("Sales Invoice", "SOMETHING")
        self.assertNotIn("Traceback", str(ctx2.exception))

    def test_get_nonexistent_name_denied_not_crashed(self):
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError) as ctx:
            kho_api.kho_phieu_get("Customer Stock Receipt", "PN-KHONG-TON-TAI-9999")
        self.assertNotIn("Traceback", str(ctx.exception))
        self.assertNotIn("DoesNotExist", str(ctx.exception))


class TestKhoPhieuNhapSave(_KhoApiFixture):
    def _payload(self, **overrides):
        p = {
            "ngay": "2026-02-10",
            "loai_nhap": "Nhập khác",
            "nguoi_giao": "Anh Giao Hàng",
            "chung_tu_kem": "HD-001",
            "dien_giai": "Nhập thử",
            "items": [{
                "vat_tu": self.kho["vt_bm"], "so_lo": "LO-NEW",
                "han_su_dung": "2027-06-01", "so_luong": 20, "don_gia": 30000,
            }],
        }
        p.update(overrides)
        return p

    def test_creates_draft(self):
        frappe.set_user(BM_USER)
        out = kho_api.kho_phieu_nhap_save(self._payload())
        self.assertEqual(out["docstatus"], 0)
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", out["name"], "kho"),
            self.kho["kho_bm"],
        )
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}),
            0, "nháp không được ghi sổ",
        )

    def test_kho_always_forced_from_session_not_payload(self):
        """Client gửi kèm kho của khách khác vẫn phải bị ép về kho của
        chính mình — never trust a client-supplied warehouse."""
        frappe.set_user(BM_USER)
        out = kho_api.kho_phieu_nhap_save(self._payload(kho=self.kho["kho_pxn"]))
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", out["name"], "kho"),
            self.kho["kho_bm"],
        )

    def test_can_edit_own_draft(self):
        frappe.set_user(BM_USER)
        out = kho_api.kho_phieu_nhap_save(self._payload())
        out2 = kho_api.kho_phieu_nhap_save(self._payload(
            name=out["name"], nguoi_giao="Người giao mới",
            items=[{
                "vat_tu": self.kho["vt_bm"], "so_lo": "LO-NEW", "han_su_dung": "2027-06-01",
                "so_luong": 99, "don_gia": 30000,
            }],
        ))
        self.assertEqual(out2["name"], out["name"])
        self.assertEqual(out2["nguoi_giao"], "Người giao mới")
        self.assertEqual(out2["items"][0]["so_luong"], 99)

    def test_cannot_edit_submitted_voucher(self):
        """Khẳng định đúng THÔNG ĐIỆP của guard tường minh trong
        kho_phieu_nhap_save (docstatus != 0), không chỉ "có ValidationError
        nào đó" — Document.save() của framework CŨNG tự chặn ghi đè một
        chứng từ đã submit (không phải amend), nên nếu chỉ khẳng định kiểu
        lỗi chung chung, gỡ guard riêng của endpoint đi vẫn xanh nhờ lưới an
        toàn kép của framework + _phieu_action (đã tự kiểm chứng bằng
        mutation: xoá `if doc.docstatus != 0` ở kho_phieu_nhap_save, bài test
        cũ vẫn pass).
        """
        frappe.set_user(BM_USER)
        out = kho_api.kho_phieu_nhap_save(self._payload())
        kho_api.kho_phieu_submit("Customer Stock Receipt", out["name"])
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_nhap_save(self._payload(name=out["name"]))
        msg = str(ctx.exception)
        self.assertNotIn("Traceback", msg)
        self.assertIn("trạng thái nháp", msg)

    def test_cannot_edit_other_customers_draft(self):
        frappe.set_user(PXN_USER)
        theirs = kho_api.kho_phieu_nhap_save({
            "ngay": "2026-02-10", "loai_nhap": "Nhập khác",
            "items": [{"vat_tu": self.kho["vt_pxn"], "so_lo": "LO-X",
                       "so_luong": 5, "don_gia": 1000}],
        })
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_phieu_nhap_save(self._payload(name=theirs["name"]))

    def test_empty_items_rejected_in_vietnamese(self):
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_nhap_save(self._payload(items=[]))
        self.assertNotIn("Traceback", str(ctx.exception))
        self.assertNotIn("Customer Stock Receipt", str(ctx.exception))

    def test_cannot_forge_loai_phieu_dao(self):
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_nhap_save(self._payload(loai_nhap="Phiếu đảo"))
        self.assertIn("Phiếu đảo", str(ctx.exception))


class TestKhoPhieuXuatSave(_KhoApiFixture):
    def setUp(self):
        super().setUp()
        self.han_con_han = frappe.utils.add_days(frappe.utils.today(), 300)
        self._nhap(so_lo="LO-A", so_luong=100, don_gia=50000, han=self.han_con_han)

    def _payload(self, **overrides):
        p = {
            "ngay": "2026-03-01",
            "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa Hồi sức tích cực",
            "nguoi_nhan": "Điều dưỡng Lan",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 10}],
        }
        p.update(overrides)
        return p

    def test_creates_draft_price_not_shown_until_submit_validate(self):
        frappe.set_user(BM_USER)
        out = kho_api.kho_phieu_xuat_save(self._payload())
        self.assertEqual(out["docstatus"], 0)
        self.assertEqual(out["items"][0]["don_gia"], 50000)  # lấy từ lô, không phải người dùng

    def test_can_edit_own_draft(self):
        """PHẢI khẳng định out2["name"] == out["name"]: nếu endpoint bỏ qua
        `name` trong payload và luôn tạo phiếu mới, các assertion về nội dung
        vẫn đúng (phiếu MỚI cũng mang đúng nội dung vừa gửi) nên bài test cũ
        (không so tên) xanh giả — đã tự kiểm chứng bằng mutation: bỏ dòng
        `name = payload.get("name")` (luôn None) vẫn xanh cho tới khi thêm
        assertion so tên.
        """
        frappe.set_user(BM_USER)
        out = kho_api.kho_phieu_xuat_save(self._payload())
        out2 = kho_api.kho_phieu_xuat_save(self._payload(
            name=out["name"], noi_nhan="Khoa Nội",
            items=[{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 15}],
        ))
        self.assertEqual(out2["name"], out["name"])
        self.assertEqual(out2["noi_nhan"], "Khoa Nội")
        self.assertEqual(out2["items"][0]["so_luong"], 15)
        self.assertEqual(
            frappe.db.count("Customer Stock Issue", {"kho": self.kho["kho_bm"]}), 1,
            "sửa nháp không được tạo thêm phiếu mới",
        )


class TestKhoPhieuSubmitCancel(_KhoApiFixture):
    def setUp(self):
        super().setUp()
        self.han_con_han = frappe.utils.add_days(frappe.utils.today(), 300)
        self.han_da_het = frappe.utils.add_days(frappe.utils.today(), -10)

    def test_submit_posts_ledger_and_changes_stock(self):
        frappe.set_user(BM_USER)
        rc = kho_api.kho_phieu_nhap_save({
            "ngay": "2026-02-01", "loai_nhap": "Nhập khác",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A",
                       "han_su_dung": self.han_con_han, "so_luong": 100, "don_gia": 50000}],
        })
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 0
        )
        out = kho_api.kho_phieu_submit("Customer Stock Receipt", rc["name"])
        self.assertEqual(out["docstatus"], 1)
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)

        ix = kho_api.kho_phieu_xuat_save({
            "ngay": "2026-03-01", "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa X", "nguoi_nhan": "A",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 30}],
        })
        kho_api.kho_phieu_submit("Customer Stock Issue", ix["name"])
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 70)

    def test_cancel_receipt_creates_reversal_and_restores_stock(self):
        frappe.set_user(BM_USER)
        rc = kho_api.kho_phieu_nhap_save({
            "ngay": "2026-02-01", "loai_nhap": "Nhập khác",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A",
                       "han_su_dung": self.han_con_han, "so_luong": 100, "don_gia": 50000}],
        })
        kho_api.kho_phieu_submit("Customer Stock Receipt", rc["name"])
        out = kho_api.kho_phieu_cancel("Customer Stock Receipt", rc["name"])
        self.assertEqual(out["docstatus"], 2)
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 0)
        self.assertEqual(
            frappe.db.count("Customer Stock Receipt",
                             {"phieu_goc": rc["name"], "loai_nhap": "Phiếu đảo"}), 1
        )

    def test_cancel_issue_restores_stock(self):
        frappe.set_user(BM_USER)
        rc = self._nhap(so_lo="LO-A", so_luong=100, don_gia=50000, han=self.han_con_han)
        ix = kho_api.kho_phieu_xuat_save({
            "ngay": "2026-03-01", "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa X", "nguoi_nhan": "A",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 30}],
        })
        kho_api.kho_phieu_submit("Customer Stock Issue", ix["name"])
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 70)

        kho_api.kho_phieu_cancel("Customer Stock Issue", ix["name"])
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)

    def test_over_issue_message_survives_endpoint_boundary(self):
        frappe.set_user(BM_USER)
        self._nhap(so_lo="LO-A", so_luong=100, don_gia=50000, han=self.han_con_han)
        ix = kho_api.kho_phieu_xuat_save({
            "ngay": "2026-03-01", "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa X", "nguoi_nhan": "A",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 999}],
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_submit("Customer Stock Issue", ix["name"])
        msg = str(ctx.exception)
        self.assertIn("LO-A", msg)
        self.assertIn("100", msg)
        self.assertNotIn("Traceback", msg)

    def test_expired_lot_without_tick_refused(self):
        frappe.set_user(BM_USER)
        self._nhap(so_lo="LO-HH", so_luong=20, don_gia=10000, han=self.han_da_het)
        ix = kho_api.kho_phieu_xuat_save({
            "ngay": "2026-03-01", "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa X", "nguoi_nhan": "A",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-HH", "so_luong": 5,
                       "xac_nhan_het_han": 0}],
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_submit("Customer Stock Issue", ix["name"])
        self.assertIn("hết hạn", str(ctx.exception))

    def test_expired_lot_with_tick_allowed(self):
        frappe.set_user(BM_USER)
        self._nhap(so_lo="LO-HH", so_luong=20, don_gia=10000, han=self.han_da_het)
        ix = kho_api.kho_phieu_xuat_save({
            "ngay": "2026-03-01", "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa X", "nguoi_nhan": "A",
            "items": [{"vat_tu": self.kho["vt_bm"], "so_lo": "LO-HH", "so_luong": 5,
                       "xac_nhan_het_han": 1}],
        })
        out = kho_api.kho_phieu_submit("Customer Stock Issue", ix["name"])
        self.assertEqual(out["docstatus"], 1)

    def test_submit_other_customers_voucher_denied(self):
        other = self._nhap(kho=self.kho["kho_pxn"], vat_tu=self.kho["vt_pxn"], submit=False)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_phieu_submit("Customer Stock Receipt", other.name)

    def test_cancel_other_customers_voucher_denied(self):
        other = self._nhap(kho=self.kho["kho_pxn"], vat_tu=self.kho["vt_pxn"], submit=True)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_phieu_cancel("Customer Stock Receipt", other.name)
        # Và phiếu của PXN không hề bị huỷ dù bị tấn công
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", other.name, "docstatus"), 1
        )

    def test_double_submit_rejected_in_vietnamese(self):
        frappe.set_user(BM_USER)
        rc = self._nhap(so_lo="LO-A", so_luong=10, don_gia=1000, submit=False)
        kho_api.kho_phieu_submit("Customer Stock Receipt", rc.name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_submit("Customer Stock Receipt", rc.name)
        self.assertNotIn("Traceback", str(ctx.exception))

    def test_cannot_cancel_draft_voucher(self):
        """kho_phieu_cancel trên một phiếu còn NHÁP (docstatus 0) phải bị
        chặn ở tầng endpoint bằng thông điệp tiếng Việt — không được để lọt
        xuống doc.cancel(), vốn ném lỗi framework tiếng Anh cho một doc chưa
        submit ("Only Submitted document can be cancelled")."""
        frappe.set_user(BM_USER)
        rc = self._nhap(so_lo="LO-A", so_luong=10, don_gia=1000, submit=False)
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_cancel("Customer Stock Receipt", rc.name)
        msg = str(ctx.exception)
        self.assertIn("đã được ghi sổ", msg)
        self.assertNotIn("Traceback", msg)

    def test_cannot_cancel_already_cancelled_voucher(self):
        frappe.set_user(BM_USER)
        rc = self._nhap(so_lo="LO-A", so_luong=10, don_gia=1000, submit=True)
        kho_api.kho_phieu_cancel("Customer Stock Receipt", rc.name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            kho_api.kho_phieu_cancel("Customer Stock Receipt", rc.name)
        self.assertIn("đã được ghi sổ", str(ctx.exception))


class TestKhoLoGoiY(_KhoApiFixture):
    def test_fefo_order_no_expiry_last(self):
        today = frappe.utils.getdate(frappe.utils.today())
        self._nhap(so_lo="LO-FAR", so_luong=50, don_gia=1000,
                    han=frappe.utils.add_days(today, 60))
        self._nhap(so_lo="LO-NEAR", so_luong=30, don_gia=1000,
                    han=frappe.utils.add_days(today, 10))
        self._nhap(so_lo="LO-NONE", so_luong=20, don_gia=1000, han=None)

        frappe.set_user(BM_USER)
        out = kho_api.kho_lo_goi_y(self.kho["vt_bm"], 40)
        order = [l["so_lo"] for l in out["lots"]]
        self.assertEqual(order, ["LO-NEAR", "LO-FAR", "LO-NONE"])

    def test_greedy_allocation_across_lots(self):
        today = frappe.utils.getdate(frappe.utils.today())
        self._nhap(so_lo="LO-NEAR", so_luong=30, don_gia=1000,
                    han=frappe.utils.add_days(today, 10))
        self._nhap(so_lo="LO-FAR", so_luong=50, don_gia=1000,
                    han=frappe.utils.add_days(today, 60))

        frappe.set_user(BM_USER)
        out = kho_api.kho_lo_goi_y(self.kho["vt_bm"], 40)
        by_lo = {l["so_lo"]: l["de_xuat"] for l in out["lots"]}
        self.assertEqual(by_lo["LO-NEAR"], 30)
        self.assertEqual(by_lo["LO-FAR"], 10)
        self.assertEqual(out["thieu"], 0)

    def test_shortfall_reported_not_thrown(self):
        today = frappe.utils.getdate(frappe.utils.today())
        self._nhap(so_lo="LO-NEAR", so_luong=5, don_gia=1000,
                    han=frappe.utils.add_days(today, 10))
        frappe.set_user(BM_USER)
        out = kho_api.kho_lo_goi_y(self.kho["vt_bm"], 40)
        self.assertEqual(out["thieu"], 35)

    def test_expired_lot_flagged(self):
        today = frappe.utils.getdate(frappe.utils.today())
        self._nhap(so_lo="LO-HH", so_luong=10, don_gia=1000,
                    han=frappe.utils.add_days(today, -5))
        frappe.set_user(BM_USER)
        out = kho_api.kho_lo_goi_y(self.kho["vt_bm"], 1)
        row = next(l for l in out["lots"] if l["so_lo"] == "LO-HH")
        self.assertTrue(row["het_han"])

    def test_rejects_other_customers_item(self):
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_lo_goi_y(self.kho["vt_pxn"], 10)

    def test_no_internal_name_leaked(self):
        self._nhap(so_lo="LO-A", so_luong=10, don_gia=1000)
        frappe.set_user(BM_USER)
        out = kho_api.kho_lo_goi_y(self.kho["vt_bm"], 5)
        for row in out["lots"]:
            self.assertNotIn("name", row)


class TestKhoPhieuPdf(_KhoApiFixture):
    def test_pdf_renders_for_owner(self):
        doc = self._nhap(so_lo="LO-A", so_luong=10, don_gia=1000)
        frappe.set_user(BM_USER)
        html = kho_api._render_phieu_html("Customer Stock Receipt", doc.name, self.kho["kho_bm"])
        self.assertIn(doc.name, html)
        self.assertIn("PHIẾU NHẬP KHO", html)

        kho_api.kho_phieu_pdf("Customer Stock Receipt", doc.name)
        content = frappe.local.response.filecontent
        self.assertTrue(content[:4] == b"%PDF", "phải là PDF thật, không phải trang trắng lỗi")

    def test_pdf_denied_for_other_customer(self):
        doc = self._nhap(kho=self.kho["kho_pxn"], vat_tu=self.kho["vt_pxn"])
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_phieu_pdf("Customer Stock Receipt", doc.name)

    def test_pdf_uses_custom_format_when_configured(self):
        from miyano_portal.setup.install_kho_print_formats import (
            NAME_NHAP_TT200,
        )
        frappe.db.set_value("Customer Warehouse", self.kho["kho_bm"], "mau_phieu_nhap", NAME_NHAP_TT200)
        try:
            doc = self._nhap(so_lo="LO-A", so_luong=10, don_gia=1000)
            frappe.set_user(BM_USER)
            html = kho_api._render_phieu_html(
                "Customer Stock Receipt", doc.name, self.kho["kho_bm"]
            )
            self.assertIn("200/2014", html)
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Customer Warehouse", self.kho["kho_bm"], "mau_phieu_nhap", "")

    def test_pdf_falls_back_to_default_when_configured_format_is_wrong_doctype(self):
        """Nếu kho lỡ cấu hình mau_phieu_nhap trỏ sang một mẫu XUẤT (hoặc bất
        kỳ mẫu nào không phải Customer Stock Receipt), _print_format_cho_kho
        phải BỎ QUA mẫu đó và dùng mặc định TT107 — không render nhầm mẫu xuất
        cho phiếu nhập, và không để lộ lỗi framework nếu mẫu đó tham chiếu
        field không có trên doctype khác.
        """
        from miyano_portal.setup.install_kho_print_formats import NAME_XUAT_TT107

        frappe.db.set_value(
            "Customer Warehouse", self.kho["kho_bm"], "mau_phieu_nhap", NAME_XUAT_TT107
        )
        try:
            doc = self._nhap(so_lo="LO-A", so_luong=10, don_gia=1000)
            frappe.set_user(BM_USER)
            html = kho_api._render_phieu_html(
                "Customer Stock Receipt", doc.name, self.kho["kho_bm"]
            )
            self.assertIn("PHIẾU NHẬP KHO", html)
            self.assertNotIn("PHIẾU XUẤT KHO", html)
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Customer Warehouse", self.kho["kho_bm"], "mau_phieu_nhap", "")


class TestKhoPhieuCrossTenant(_KhoApiFixture):
    """Bốn thao tác then chốt: đọc, ghi sổ, huỷ, in. Khách A không được phép
    làm bất kỳ điều nào ở trên với phiếu của khách B qua bất kỳ endpoint nào.
    """

    def setUp(self):
        super().setUp()
        self.han = frappe.utils.add_days(frappe.utils.today(), 300)
        self.pxn_receipt = self._nhap(
            kho=self.kho["kho_pxn"], vat_tu=self.kho["vt_pxn"], so_lo="LO-PXN",
            so_luong=50, don_gia=1000, han=self.han, submit=True,
        )

    def test_all_four_operations_denied(self):
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_phieu_get("Customer Stock Receipt", self.pxn_receipt.name)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_phieu_submit("Customer Stock Receipt", self.pxn_receipt.name)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_phieu_cancel("Customer Stock Receipt", self.pxn_receipt.name)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_phieu_pdf("Customer Stock Receipt", self.pxn_receipt.name)
        # Vẫn còn nguyên vẹn, không bị đụng vào
        self.assertEqual(
            frappe.db.get_value("Customer Stock Receipt", self.pxn_receipt.name, "docstatus"), 1
        )
