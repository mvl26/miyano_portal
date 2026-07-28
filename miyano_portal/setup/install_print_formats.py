import frappe

NAME = "Miyano - Xác nhận đơn hàng"
HTML = """
<div class="print-heading"><h2>XÁC NHẬN ĐƠN HÀNG / ORDER CONFIRMATION</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số đơn / Order No:</b> {{ doc.name }}
   &nbsp; <b>Ngày / Date:</b> {{ frappe.utils.formatdate(doc.transaction_date, "dd/mm/yyyy") }}</p>
<p><b>Số PO khách / Customer PO:</b> {{ doc.custom_so_po_khach or "" }}</p>
<table class="table table-bordered">
  <thead><tr>
    <th>Mã / Code</th><th>Tên hàng / Item</th><th>SL / Qty</th>
    <th>Đơn giá / Rate</th><th>Thành tiền / Amount</th>
  </tr></thead>
  <tbody>
  {% for i in doc.items %}
    <tr>
      <td>{{ i.item_code }}</td><td>{{ i.item_name }}</td>
      <td class="text-right">{{ i.qty }}</td>
      <td class="text-right">{{ "{:,.0f}".format(i.rate) }} ₫</td>
      <td class="text-right">{{ "{:,.0f}".format(i.amount) }} ₫</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
<p class="text-right"><b>Tổng cộng / Total:</b> {{ "{:,.0f}".format(doc.grand_total) }} ₫</p>
"""


def install_portal_print_formats():
    if frappe.db.exists("Print Format", NAME):
        return
    frappe.get_doc({
        "doctype": "Print Format",
        "name": NAME,
        "doc_type": "Sales Order",
        "standard": "No",
        "custom_format": 1,
        "print_format_type": "Jinja",
        "html": HTML,
    }).insert(ignore_permissions=True)
