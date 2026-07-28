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

NAME_DN = "Miyano - Phiếu giao hàng"
HTML_DN = """
<div class="print-heading"><h2>PHIẾU GIAO HÀNG / DELIVERY NOTE</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số phiếu / Delivery No:</b> {{ doc.name }}
   &nbsp; <b>Ngày / Date:</b> {{ frappe.utils.formatdate(doc.posting_date, "dd/mm/yyyy") }}</p>
<p><b>Đơn hàng / Sales Order:</b> {{ doc.items[0].against_sales_order if doc.items else "" }}</p>
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

NAME_SI = "Miyano - Hoá đơn"
HTML_SI = """
<div class="print-heading"><h2>HOÁ ĐƠN BÁN HÀNG / SALES INVOICE</h2></div>
<p><b>Khách hàng / Customer:</b> {{ doc.customer_name }}</p>
<p><b>Số hoá đơn / Invoice No:</b> {{ doc.name }}
   &nbsp; <b>Ngày / Date:</b> {{ frappe.utils.formatdate(doc.posting_date, "dd/mm/yyyy") }}</p>
<p><b>Đơn hàng / Sales Order:</b> {{ doc.items[0].sales_order if doc.items else "" }}</p>
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
<p class="text-right"><b>Còn nợ / Outstanding:</b> {{ "{:,.0f}".format(doc.outstanding_amount) }} ₫</p>
"""

FORMATS = [
    (NAME, "Sales Order", HTML),
    (NAME_DN, "Delivery Note", HTML_DN),
    (NAME_SI, "Sales Invoice", HTML_SI),
]


def install_portal_print_formats():
    for name, doc_type, html in FORMATS:
        if frappe.db.exists("Print Format", name):
            continue
        frappe.get_doc({
            "doctype": "Print Format",
            "name": name,
            "doc_type": doc_type,
            "standard": "No",
            "custom_format": 1,
            "print_format_type": "Jinja",
            "html": html,
        }).insert(ignore_permissions=True)
