import json
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.api import portal


class TestTracking(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        bo = portal.portal_contracts()[0]["name"]
        self.so = portal.portal_order_place(
            bo, json.dumps([{"item_code": "VT0005", "qty": 10}])
        )["sales_order"]

    def test_history_shows_order(self):
        names = {r["name"] for r in portal.portal_order_history()}
        self.assertIn(self.so, names)

    def test_track_has_milestones(self):
        t = portal.portal_order_track(self.so)
        self.assertEqual(t["status_vi"], "Chờ xác nhận")
        self.assertTrue(any(m["key"] == "ordered" and m["done"] for m in t["milestones"]))

    def test_track_milestones_include_preparing_between_confirmed_and_delivering(self):
        t = portal.portal_order_track(self.so)
        keys = [m["key"] for m in t["milestones"]]
        self.assertEqual(
            keys, ["ordered", "confirmed", "preparing", "delivering", "invoiced"]
        )
        preparing = next(m for m in t["milestones"] if m["key"] == "preparing")
        self.assertEqual(preparing["label"], "Soạn hàng")

    def test_track_items_include_item_name(self):
        t = portal.portal_order_track(self.so)
        self.assertTrue(t["items"])
        for item in t["items"]:
            self.assertTrue(item.get("item_name"), f"item_name missing for {item['item_code']}")

    def test_cancel_request_on_draft(self):
        res = portal.portal_request_cancel(self.so, "Đặt nhầm")
        self.assertTrue(res["ok"])

    def test_cross_customer_cannot_track_or_cancel(self):
        frappe.set_user("pxnabc@demo.miyano")
        self.assertRaises(frappe.PermissionError, portal.portal_order_track, self.so)
        self.assertRaises(
            frappe.PermissionError, portal.portal_request_cancel, self.so, "x"
        )

    def test_status_vi_is_delivery_aware(self):
        # The bug: partial delivery under "To Deliver and Bill" used to show
        # "Đang xử lý" instead of progressing to "Đang giao".
        self.assertEqual(
            portal._so_status_vi("To Deliver and Bill", 50), "Đang giao"
        )
        self.assertEqual(
            portal._so_status_vi("To Deliver and Bill", 0), "Đang xử lý"
        )
        self.assertEqual(portal._so_status_vi("To Bill", 0), "Đang xử lý")
        self.assertEqual(portal._so_status_vi("Draft", 0), "Chờ xác nhận")
        self.assertEqual(portal._so_status_vi("Draft", None), "Chờ xác nhận")
        # Completed/Cancelled must win even if per_delivered is still > 0.
        self.assertEqual(portal._so_status_vi("Completed", 100), "Hoàn thành")
        self.assertEqual(portal._so_status_vi("Cancelled", 50), "Đã huỷ")
        self.assertEqual(portal._so_status_vi("Closed", 0), "Đã huỷ")
