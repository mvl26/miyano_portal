import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.kho import ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestPhieuXuat(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        self._nhap("LO-A", 100, 50000, han="2027-01-01")

    def _nhap(self, so_lo, so_luong, don_gia, han):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"], "ngay": "2026-02-01",
            "loai_nhap": "Nhập khác",
            "items": [{
                "vat_tu": self.kho["vt_bm"], "so_lo": so_lo, "han_su_dung": han,
                "so_luong": so_luong, "don_gia": don_gia,
            }],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    def _xuat(self, so_luong=10, so_lo="LO-A", xac_nhan=0, lines=None):
        items = lines or [{
            "vat_tu": self.kho["vt_bm"], "so_lo": so_lo,
            "so_luong": so_luong, "xac_nhan_het_han": xac_nhan,
        }]
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": self.kho["kho_bm"], "ngay": "2026-03-01",
            "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa Hồi sức tích cực",
            "nguoi_nhan": "Điều dưỡng Lan",
            "items": items,
        })
        doc.insert(ignore_permissions=True)
        return doc

    def test_naming(self):
        self.assertTrue(self._xuat().name.startswith("PX-BM-2026-"))

    def test_price_taken_from_lot_not_user(self):
        doc = self._xuat(so_luong=10)
        self.assertEqual(doc.items[0].don_gia, 50000)
        self.assertEqual(doc.items[0].thanh_tien, 500000)
        self.assertEqual(doc.items[0].han_su_dung.isoformat(), "2027-01-01")

    def test_submit_reduces_balance(self):
        self._xuat(so_luong=30).submit()
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 70)

    def test_over_issue_blocked(self):
        doc = self._xuat(so_luong=150)
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        msg = str(ctx.exception)
        self.assertIn("LO-A", msg)
        self.assertIn("chỉ còn 100", msg)

    def test_split_rows_cannot_bypass_balance(self):
        """Tách hai dòng cùng lô để mỗi dòng đều lọt kiểm tra riêng lẻ."""
        doc = self._xuat(lines=[
            {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 60},
            {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 60},
        ])
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("chỉ còn 100", str(ctx.exception))

    def test_unknown_lot_blocked(self):
        doc = self._xuat(so_lo="LO-KHONG-CO")
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("LO-KHONG-CO", str(ctx.exception))

    def test_expired_lot_requires_confirmation(self):
        self._nhap("LO-HET-HAN", 20, 10000, han="2026-01-01")
        doc = self._xuat(so_luong=5, so_lo="LO-HET-HAN", xac_nhan=0)
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("hết hạn", str(ctx.exception))

    def test_expired_lot_allowed_when_confirmed(self):
        self._nhap("LO-HET-HAN", 20, 10000, han="2026-01-01")
        self._xuat(so_luong=5, so_lo="LO-HET-HAN", xac_nhan=1).submit()
        bal = ledger.get_lot_balance(
            self.kho["kho_bm"], self.kho["vt_bm"], "LO-HET-HAN"
        )
        self.assertEqual(bal["so_luong"], 15)

    def test_cancel_returns_stock_via_reversal(self):
        doc = self._xuat(so_luong=30)
        doc.submit()
        doc.cancel()
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)
        self.assertEqual(
            frappe.db.count("Customer Stock Issue", {"phieu_goc": doc.name}), 1
        )
        # Không dòng sổ nào bị xoá: 1 nhập + 1 xuất + 1 đảo
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 3
        )

    def test_noi_nhan_is_free_text(self):
        doc = self._xuat()
        self.assertEqual(doc.noi_nhan, "Khoa Hồi sức tích cực")
        self.assertFalse(frappe.db.exists("DocType", "Customer Department"))

    def test_manual_reversal_cannot_be_forged_via_phieu_goc(self):
        """phieu_goc là Data field tự do; đặt nó thủ công tuyệt đối không được
        coi là "đang tạo phiếu đảo hợp lệ" - chỉ self.flags.dang_tao_dao (cờ
        in-memory, không giả được qua form/API) mới được phép mở khoá
        loai_xuat = "Phiếu đảo". Nếu guard lỡ chấp nhận `or self.phieu_goc`,
        test này sẽ chèn được một phiếu đảo giả, submit thành công, và kéo
        tồn từ 100 xuống 0 - đúng lỗ hổng mà một vòng review trước đã bắt.
        """
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": self.kho["kho_bm"], "ngay": "2026-03-01",
            "loai_xuat": "Phiếu đảo",
            "phieu_goc": "PX-BM-2026-99999-KHONG-TON-TAI",
            "items": [{
                "vat_tu": self.kho["vt_bm"], "so_lo": "LO-A",
                "so_luong": 100, "xac_nhan_het_han": 1,
            }],
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("Không thể tạo phiếu đảo bằng tay", str(ctx.exception))
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)
