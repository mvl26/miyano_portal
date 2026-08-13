"""NL-2.6 — báo cáo đơn chậm xử lý cho Sales Manager.

Query Report thay vì Script Report: nội dung chỉ là một câu SELECT, và Script
Report phải nằm trong module có thư mục report/ trên đĩa — thêm một chỗ nữa
phải giữ đồng bộ mà không được lợi gì.

Cột "Số giờ treo" dùng `timestampdiff` giờ đồng hồ, KHÔNG phải giờ làm việc —
SQL không biết quy ước bỏ T7/CN. Đây là số để sắp xếp và nhìn nhanh; chốt
chặn SLA thật nằm ở `portal_sla.gio_lam_viec_troi_qua`. Hai con số này KHÔNG
bắt buộc phải khớp nhau.
"""

import frappe

TEN = "Đơn chậm xử lý"

CAU_TRUY_VAN = """
select
    so.name            as "Đơn hàng:Link/Sales Order:140",
    so.customer        as "Khách hàng:Link/Customer:220",
    so.grand_total     as "Giá trị:Currency:120",
    so.modified        as "Chờ từ lúc:Datetime:160",
    round(timestampdiff(hour, so.modified, now()), 1) as "Số giờ treo:Float:110"
from `tabSales Order` so
where so.docstatus = 0
  and so.workflow_state = 'Chờ Miyano xác nhận'
order by so.modified asc
"""


def execute():
    if frappe.db.exists("Report", TEN):
        return
    frappe.get_doc({
        "doctype": "Report",
        "report_name": TEN,
        "ref_doctype": "Sales Order",
        "report_type": "Query Report",
        "module": "Miyano Portal",
        "is_standard": "No",
        "query": CAU_TRUY_VAN,
        "roles": [{"role": "Sales Manager"}, {"role": "Sales User"}],
    }).insert(ignore_permissions=True)
