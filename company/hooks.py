app_name = "company"
app_title = "Constrmart"
app_publisher = "deepak"
app_description = "Company "
app_email = "deepak@gmail.com"
app_license = "mit"

app_include_js = [
    # "/assets/company/js/leads.js",
    "/assets/company/js/quotation.js",
    "/assets/company/js/estimation.js",
    "/assets/company/js/invoice.js",
    "/assets/company/js/purchase.js",
    "/assets/company/js/expenses.js",
    "/assets/company/js/custom.js",
    "/assets/company/js/attendance.js",
    "/assets/company/js/salary_slip.js",
    "/assets/company/js/salary_list.js",
    "/assets/company/js/leave_allocation.js",
    "/assets/company/js/attendance_list.js",
    "/assets/company/js/wfh_attendance_list.js",
    "/assets/company/js/firebase_init.js?v=1",
    "/assets/company/js/pwa_init.js?v=1",
    # "/assets/company/js/socket.io.min.js",
    # "/assets/company/js/socket_init.js",
    "/assets/company/js/custom_link_formatter.js",
    # "/assets/company/js/custom_badge.js",
    "/assets/company/js/custom_back_button.js",
    "/assets/company/js/birthday_animation.js",
    "/assets/company/js/custom-sidebar-menu.js",
    "/assets/company/js/default_phone_no.js",
    "/assets/company/js/logo.js", 
    "/assets/company/js/clear_cache.js?v=1",
    "/assets/company/js/profile_picture.js",
    "/assets/company/js/event_popup.js",
    "/assets/company/js/parent_sidebar.js?v=1",
    "/assets/company/js/sidebar-active-state.js",
    "/assets/company/js/roundoff_buttons.js",
    "/assets/company/js/global_list_actions.js",
    "/assets/company/js/pagination.js",
    "/assets/company/js/auto_refresh.js",
    # "/assets/company/js/force_calendar_view.js",
    # "/assets/company/js/expense_list.js",
    # "/assets/company/js/income_list.js",
    "/assets/company/js/expense_tracker.js",
    # "/assets/company/js/import_button.js",
    # "/assets/company/js/sales_pipeline.js",
]

app_include_css = "/assets/company/css/custom.css?v=11"


doc_events = {
    "Estimation": {
        "before_insert": "company.company.api.before_insert_estimation"
    },
    "Invoice": {
        "before_insert": "company.company.api.before_insert_invoice"
    },
    "Invoice Collection": {
        "validate": "company.company.api.validate_invoice_collection",
        "after_insert": "company.company.api.update_invoice_received_balance",
        "on_update": "company.company.api.update_invoice_received_balance",
        "on_trash": "company.company.api.update_invoice_received_balance"
    },
    "Expenses": {
        "before_insert": "company.company.api.before_insert_expense"
    },
    "Leave Application": {
        "validate": "company.company.api.validate_leave_balance",
        "before_submit": "company.company.api.validate_leave_balance",
        "on_submit": ["company.company.api.create_unread_entry_for_hr"],
        "on_change": [
            "company.company.api.update_permission_allocation"
        ],
        "after_insert": "company.company.api.auto_submit_leave_application"
    },
    "Attendance": {
        "on_update": "company.company.api.update_leave_allocation_from_attendance",
    },
    "WFH Attendance": {
        "on_submit": "company.company.api.create_unread_entry_for_hr"
    },
    "Request": {
        "on_submit": "company.company.api.create_unread_entry_for_hr"
    },
    "Salary Slip": {
        "on_submit": "company.company.api.salary_slip_after_submit"
    },
    "Event": {
        "on_update": [
            "company.company.crm_api.sync_event_to_call",
            "company.company.crm_api.sync_event_to_meeting",
            "company.company.crm_api.sync_event_to_todo"
        ],
        "validate": "company.company.crm_api.validate_event"
    }
}


scheduler_events = {
    "daily": [
        "company.company.api.update_expired_renewals"
    ],
    "cron": {
        "*/5 * * * *": [
            "company.company.reminders.run_email_reminders"
        ]
    }
}


# --- Safe Print Patch to Suppress BrokenPipeError ---
import builtins

_original_print = print

def safe_print(*args, **kwargs):
    """Print wrapper that ignores BrokenPipeError when client disconnects."""
    try:
        _original_print(*args, **kwargs)
    except BrokenPipeError:
        pass

# Apply globally so any print() in Frappe or custom apps is safe
builtins.print = safe_print


extend_bootinfo = "company.company.api.extend_bootinfo"



# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "company",
# 		"logo": "/assets/company/logo.png",
# 		"title": "Company",
# 		"route": "/company",
# 		"has_permission": "company.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/company/css/company.css"
# app_include_js = "/assets/company/js/company.js"

# include js, css files in header of web template
# web_include_css = "/assets/company/css/company.css"
# web_include_js = "/assets/company/js/company.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "company/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "company/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "company.utils.jinja_methods",
# 	"filters": "company.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "company.install.before_install"
# after_install = "company.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "company.uninstall.before_uninstall"
# after_uninstall = "company.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "company.utils.before_app_install"
# after_app_install = "company.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "company.utils.before_app_uninstall"
# after_app_uninstall = "company.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "company.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
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
# 		"company.tasks.all"
# 	],
# 	"daily": [
# 		"company.tasks.daily"
# 	],
# 	"hourly": [
# 		"company.tasks.hourly"
# 	],
# 	"weekly": [
# 		"company.tasks.weekly"
# 	],
# 	"monthly": [
# 		"company.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "company.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "company.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "company.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "company.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["company.utils.before_request"]
# after_request = ["company.utils.after_request"]

# Job Events
# ----------
# before_job = ["company.utils.before_job"]
# after_job = ["company.utils.after_job"]

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
# 	"company.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

