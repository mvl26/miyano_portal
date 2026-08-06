import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.kho import ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestPhieuXuat(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        # FINDING 4: những lô "còn hạn" / "đã hết hạn" phải tính tương đối so
        # với hôm nay, không hardcode. `_chan_lo_het_han_chua_xac_nhan` so
        # han_su_dung với frappe.utils.today() tại THỜI ĐIỂM CHẠY TEST — một
        # mốc hạn dùng hardcode trong tương lai (ví dụ "2027-01-01") sẽ tự
        # biến thành "đã hết hạn" một khi đồng hồ đi qua nó, làm
        # test_submit_reduces_balance và test_cancel_returns_stock_via_reversal
        # đỏ dù không có gì thay đổi trong code.
        self.han_con_han = frappe.utils.add_days(frappe.utils.today(), 400)
        self.han_da_het = frappe.utils.add_days(frappe.utils.today(), -30)
        self._nhap("LO-A", 100, 50000, han=self.han_con_han)

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
        # FINDING 2: phải NHỒI giá trị sai vào dòng nhập rồi khẳng định nó bị
        # ghi đè - nếu test không tự cung cấp don_gia/thanh_tien/han_su_dung
        # của người dùng, test này vẫn PASS ngay cả khi code lỡ tin theo giá
        # người dùng nhập (đã xác nhận bằng mutation: honour user don_gia vẫn
        # để 11/11 test cũ pass).
        doc = self._xuat(lines=[{
            "vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 10,
            "don_gia": 999999, "thanh_tien": 123, "han_su_dung": "2099-01-01",
        }])
        self.assertEqual(doc.items[0].don_gia, 50000)
        self.assertEqual(doc.items[0].thanh_tien, 500000)
        self.assertEqual(doc.items[0].han_su_dung.isoformat(), self.han_con_han)

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
        self._nhap("LO-HET-HAN", 20, 10000, han=self.han_da_het)
        doc = self._xuat(so_luong=5, so_lo="LO-HET-HAN", xac_nhan=0)
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("hết hạn", str(ctx.exception))

    def test_expired_lot_allowed_when_confirmed(self):
        self._nhap("LO-HET-HAN", 20, 10000, han=self.han_da_het)
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

    def test_reversal_voucher_cannot_be_cancelled(self):
        """FINDING 5: mirror của test_kho_receipt's
        test_reversal_voucher_cannot_be_cancelled. Chốt chặn phải nằm ở
        before_cancel (chạy TRƯỚC db_update()) chứ không phải on_cancel: nếu
        đặt guard ở on_cancel, docstatus=2 đã ghi xuống DB trước khi exception
        được ném ra, nên assertion docstatus == 1 dưới đây sẽ FAIL dù lỗi đã
        xuất hiện đúng chỗ khác.
        """
        doc = self._xuat(so_luong=30)
        doc.submit()
        doc.cancel()
        dao_name = frappe.db.get_value(
            "Customer Stock Issue", {"phieu_goc": doc.name}, "name"
        )
        dao = frappe.get_doc("Customer Stock Issue", dao_name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            dao.cancel()
        self.assertIn("phiếu đảo", str(ctx.exception).lower())
        self.assertEqual(
            frappe.db.get_value("Customer Stock Issue", dao_name, "docstatus"), 1
        )

    def test_cancel_reprices_from_original_row_not_current_lot_avg(self):
        """FINDING 1: huỷ phiếu xuất phải hoàn trả ĐÚNG giá trị đã trừ lúc
        xuất, không phải giá bình quân gia quyền HIỆN TẠI của lô - giá đó có
        thể đã đổi do những lần nhập xảy ra SAU phiếu xuất, giữa lúc xuất và
        lúc huỷ. Số lượng và tồn cuối vẫn khớp dù giá trị hoàn trả sai, nên
        phải kiểm bằng tổng giá trị sổ và đơn giá lô sau khi huỷ, không phải
        chỉ so_luong.

        Trình tự tái hiện đúng như báo cáo review:
            nhập 100 @ 50.000   -> giá bình quân lô 50.000
            xuất 30             -> sổ ghi -1.500.000
            nhập 100 @ 70.000   -> giá bình quân lô 61.764,71
            huỷ phiếu xuất      -> phiếu đảo PHẢI hoàn 30 @ 50.000 (giá gốc),
                                    không phải 30 @ 61.764,71 (giá lô hiện tại)
        """
        doc = self._xuat(so_luong=30)  # LO-A: 100 @ 50.000 từ setUp
        doc.submit()
        self._nhap("LO-A", 100, 70000, han=self.han_con_han)
        doc.cancel()

        tong_gia_tri = frappe.db.sql(
            """select sum(gia_tri) from `tabCustomer Stock Ledger Entry`
               where kho=%s""",
            self.kho["kho_bm"],
        )[0][0]
        # 100*50.000 - 30*50.000 + 100*70.000 + 30*50.000 (hoàn đúng giá gốc)
        # = 12.000.000. Bản lỗi hoàn theo giá lô hiện tại (61.764,71) cho ra
        # 12.352.941 - dư 352.941 VND từ hư không.
        self.assertAlmostEqual(float(tong_gia_tri), 12_000_000, places=2)

        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        # (170*61.764,71 + 30*50.000) / 200 = 60.000 đúng bằng giá vốn thật
        # của 200 đơn vị đã mua (100 @ 50.000 + 100 @ 70.000) / 200.
        self.assertAlmostEqual(float(bal["don_gia"]), 60000, places=2)
