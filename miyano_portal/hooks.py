app_name = "miyano_portal"
app_title = "Miyano Portal"
app_publisher = "SupplyCore Project"
app_description = "Miyano customer portal for ERPNext"
app_email = "info@miyano.com.vn"
app_license = "mit"

# Apps
# ------------------

required_apps = ["frappe/frappe", "erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "miyano_portal",
# 		"logo": "/assets/miyano_portal/logo.png",
# 		"title": "Miyano Portal",
# 		"route": "/miyano_portal",
# 		"has_permission": "miyano_portal.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/miyano_portal/css/miyano_portal.css"
# app_include_js = "/assets/miyano_portal/js/miyano_portal.js"

# include js, css files in header of web template
# web_include_css = "/assets/miyano_portal/css/miyano_portal.css"
# web_include_js = "/assets/miyano_portal/js/miyano_portal.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "miyano_portal/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "miyano_portal/public/icons.svg"

# Website route rules
# --------------------
# SPA Vue phục vụ tại /portal (www/portal/index.html). Các route phía client
# như /portal/orders, /portal/dashboard phải trả về cùng shell để vue-router xử
# lý. Rule /portal/login đặt trước (werkzeug ưu tiên segment tĩnh hơn <path:>)
# để trang đăng nhập www/portal/login.html KHÔNG bị catch-all chiếm mất.
website_route_rules = [
	{"from_route": "/portal/login", "to_route": "portal/login"},
	{"from_route": "/portal/<path:app_path>", "to_route": "portal/index"},
]

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "miyano_portal.utils.jinja_methods",
# 	"filters": "miyano_portal.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "miyano_portal.install.before_install"
# after_install = "miyano_portal.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "miyano_portal.uninstall.before_uninstall"
# after_uninstall = "miyano_portal.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "miyano_portal.utils.before_app_install"
# after_app_install = "miyano_portal.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "miyano_portal.utils.before_app_uninstall"
# after_app_uninstall = "miyano_portal.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "miyano_portal.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Sales Order": "miyano_portal.permissions.sales_query",
	"Delivery Note": "miyano_portal.permissions.delivery_query",
	"Sales Invoice": "miyano_portal.permissions.invoice_query",
	"Blanket Order": "miyano_portal.permissions.blanket_query",
}

has_permission = {
	"Sales Order": "miyano_portal.permissions.sales_has_permission",
	"Delivery Note": "miyano_portal.permissions.generic_has_permission",
	"Sales Invoice": "miyano_portal.permissions.generic_has_permission",
	"Blanket Order": "miyano_portal.permissions.generic_has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"miyano_portal.tasks.all"
# 	],
# 	"daily": [
# 		"miyano_portal.tasks.daily"
# 	],
# 	"hourly": [
# 		"miyano_portal.tasks.hourly"
# 	],
# 	"weekly": [
# 		"miyano_portal.tasks.weekly"
# 	],
# 	"monthly": [
# 		"miyano_portal.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "miyano_portal.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "miyano_portal.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "miyano_portal.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["miyano_portal.utils.before_request"]
# after_request = ["miyano_portal.utils.after_request"]

# Job Events
# ----------
# before_job = ["miyano_portal.utils.before_job"]
# after_job = ["miyano_portal.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"miyano_portal.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

