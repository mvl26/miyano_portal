import frappe
def run():
    for c in frappe.get_all("Contact", filters={"user":["like","%kiemhang%"]}, fields=["name","user"]):
        print("contact", c, frappe.get_all("Dynamic Link", filters={"parent":c.name}, fields=["link_doctype","link_name"]))
    print("customers", frappe.get_all("Customer", filters={"name":["like","KH Test Kiểm Hàng%"]}, pluck="name"))
    print("users", frappe.get_all("User", filters={"name":["like","%kiemhang%"]}, pluck="name"))
