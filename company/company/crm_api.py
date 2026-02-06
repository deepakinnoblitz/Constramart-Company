import frappe
from frappe.utils import get_datetime, add_days
from frappe.utils import strip_html
from frappe.utils import get_datetime, now_datetime

@frappe.whitelist()
def convert_lead(lead_name):
    lead = frappe.get_doc("Lead", lead_name)
    messages = []

    # ----------------------------------------------------
    # 0️⃣ VALIDATIONS
    # ----------------------------------------------------

    if not lead.company_name:
        frappe.throw("Company Name is required to create an Account")

    if not (lead.email or lead.phone_number):
        frappe.throw("Email or Phone is required to create a Contact")

    # ----------------------------------------------------
    # 1️⃣ ACCOUNT (Accounts)
    # ----------------------------------------------------
    account_name = frappe.db.get_value(
        "Accounts",
        {"account_name": lead.company_name},
        "name"
    )

    if account_name:
        messages.append({
            "type": "warning",
            "text": f"Account already exists: {account_name}"
        })
    else:
        account = frappe.new_doc("Accounts")
        account.account_name = lead.company_name
        account.phone_number = lead.phone_number
        account.gstin = lead.gstin
        account.country = lead.country
        account.state = lead.state
        account.city = lead.city
        account.insert()

        account_name = account.name
        messages.append({
            "type": "success",
            "text": f"New Account created: {account_name}"
        })

    # ----------------------------------------------------
    # 2️⃣ CONTACT (Contacts)
    # ----------------------------------------------------
    contact = frappe.get_all(
        "Contacts",
        or_filters=[
            ["email", "=", lead.email],
            ["phone", "=", lead.phone_number]
        ],
        fields=["name"],
        limit=1
    )

    if contact:
        contact_name = contact[0].name
        messages.append({
            "type": "warning",
            "text": f"Contact already exists: {contact_name}"
        })
    else:
        contact_doc = frappe.new_doc("Contacts")
        contact_doc.first_name = lead.lead_name
        contact_doc.company_name = lead.company_name
        contact_doc.email = lead.email
        contact_doc.phone = lead.phone_number
        contact_doc.country = lead.country
        contact_doc.state = lead.state
        contact_doc.city = lead.city
        contact_doc.address = lead.billing_address
        contact_doc.source_lead = lead.name
        contact_doc.insert()

        contact_name = contact_doc.name
        messages.append({
            "type": "success",
            "text": f"New Contact created: {contact_name}"
        })

    # ----------------------------------------------------
    # 4️⃣ UPDATE LEAD (LOCK)
    # ----------------------------------------------------
    lead.status = "Converted"
    lead.db_set("converted_account", account_name)
    lead.db_set("converted_contact", contact_name)

    return {
        "account": account_name,
        "contact": contact_name,
        "messages": messages
    }



@frappe.whitelist()
def get_call_events(doctype, start, end, field_map, filters=None, fields=None):
    import json
    field_map = frappe._dict(json.loads(field_map))
    fields = frappe.parse_json(fields)

    # Detect Color field dynamically
    doc_meta = frappe.get_meta(doctype)
    for d in doc_meta.fields:
        if d.fieldtype == "Color":
            field_map.update({"color": d.fieldname})

    # Wrap SQL keyword fields
    start_col = f"`{field_map.start}`"
    end_col   = f"`{field_map.end}`"

    # STEP 1 → Find valid calls
    call_names = frappe.db.sql(
        f"""
        SELECT name
        FROM `tab{doctype}`
        WHERE IFNULL({start_col}, '0001-01-01 00:00:00') <= %s
          AND IFNULL({end_col},   '2199-12-31 00:00:00') >= %s
        """,
        (end, start),
        as_list=True
    )

    call_names = [c[0] for c in call_names]

    if not call_names:
        return []

    # STEP 2 → Fetch required fields
    if not fields:
        fields = [
            field_map.start,
            field_map.end,
            field_map.title,
            "name",
            "outgoing_call_status",
        ]

    if field_map.color:
        fields.append(field_map.color)

    events = frappe.get_list(
        doctype,
        fields=list(set(fields)),
        filters={"name": ["in", call_names]}
    )

    # STEP 3 → Format for FullCalendar
    for e in events:
        
        start_dt = e.get(field_map.start)
        end_dt   = e.get(field_map.end)

        # Required for FullCalendar
        e["id"] = e["name"]

        # ISO formatting
        if start_dt:
            e["start"] = start_dt.isoformat() + "+05:30"
        if end_dt:
            e["end"] = end_dt.isoformat() + "+05:30"

        # Title formatting (SAFE)
        title = e.get(field_map.title) or e["name"]

        # Safe time strings
        start_str = start_dt.strftime('%I:%M %p') if start_dt else None
        end_str   = end_dt.strftime('%I:%M %p') if end_dt else None

        # Build the title
        if start_str and end_str:
            # Both start and end exist
            e["title"] = f"{title} ({start_str} - {end_str})"
        elif start_str:
            # Only start time exists → no dash, no NULL
            e["title"] = f"{title} ({start_str})"
        else:
            # No times
            e["title"] = title

        # Colors
        status = e.get("outgoing_call_status")
        color_map = {
            "Scheduled": "#FBC02D",
            "Completed": "#0F8A4D",
        }
        e["color"] = color_map.get(status, "#FFFFFF")


        # All-day
        if start_dt and end_dt:
            e["allDay"] = start_dt.date() == end_dt.date()
        else:
            e["allDay"] = True

    return events



@frappe.whitelist()
def get_meeting_events(doctype, start, end, field_map, filters=None, fields=None):
    import json
    field_map = frappe._dict(json.loads(field_map))
    fields = frappe.parse_json(fields)

    # Detect Color field dynamically
    doc_meta = frappe.get_meta(doctype)
    for d in doc_meta.fields:
        if d.fieldtype == "Color":
            field_map.update({"color": d.fieldname})

    # Wrap SQL keyword fields
    start_col = f"`{field_map.start}`"
    end_col   = f"`{field_map.end}`"

    # ---------------------------------------
    # STEP 1 → RAW SQL (same as call events)
    # ---------------------------------------
    meeting_names = frappe.db.sql(
        f"""
        SELECT name
        FROM `tab{doctype}`
        WHERE IFNULL({start_col}, '0001-01-01 00:00:00') <= %s
          AND IFNULL({end_col},   '2199-12-31 00:00:00') >= %s
        """,
        (end, start),
        as_list=True
    )

    meeting_names = [m[0] for m in meeting_names]

    if not meeting_names:
        return []

    # ---------------------------------------
    # STEP 2 → Fetch required fields
    # ---------------------------------------
    if not fields:
        fields = [
            field_map.start,
            field_map.end,
            field_map.title,
            "name",
            "outgoing_call_status",
        ]

    if field_map.color:
        fields.append(field_map.color)

    events = frappe.get_list(
        doctype,
        fields=list(set(fields)),
        filters={"name": ["in", meeting_names]}
    )

    # ---------------------------------------
    # STEP 3 → Format output (IDENTICAL TO CALLS)
    # ---------------------------------------
    for e in events:

        start_dt = e.get(field_map.start)
        end_dt   = e.get(field_map.end)

        # FullCalendar ID
        e["id"] = e["name"]

        # ISO formatting for calendar
        if start_dt:
            e["start"] = start_dt.isoformat() + "+05:30"

        if end_dt:
            e["end"] = end_dt.isoformat() + "+05:30"

        # Title (SAFE)
        title = e.get(field_map.title) or e["name"]

        # Safe time strings
        start_str = start_dt.strftime("%I:%M %p") if start_dt else None
        end_str   = end_dt.strftime("%I:%M %p") if end_dt else None

        # Title building (identical logic from calls)
        if start_str and end_str:
            e["title"] = f"{title} ({start_str} - {end_str})"
        elif start_str:
            e["title"] = f"{title} ({start_str})"
        else:
            e["title"] = title

        # Colors (meeting version)
        status = e.get("outgoing_call_status")
        color_map = {
            "Scheduled": "#FBC02D",
            "Completed": "#0DB260",
        }
        e["color"] = color_map.get(status, "#FFFFFF")

        # All-day event logic
        if start_dt and end_dt:
            e["allDay"] = start_dt.date() == end_dt.date()
        else:
            e["allDay"] = True

    return events
 
 
 
@frappe.whitelist()
def get_expense_events(doctype, start, end, field_map, filters=None, fields=None):
    import json
    field_map = frappe._dict(json.loads(field_map))
    fields = frappe.parse_json(fields)
 
    # Detect Color field dynamically
    doc_meta = frappe.get_meta(doctype)
    for d in doc_meta.fields:
        if d.fieldtype == "Color":
            field_map.update({"color": d.fieldname})
 
    # Wrap SQL keyword fields
    start_col = f"`{field_map.start}`"
    end_col   = f"`{field_map.end}`"
 
    # STEP 1 → Find valid expenses
    expense_names = frappe.db.sql(
        f"""
        SELECT name
        FROM `tab{doctype}`
        WHERE IFNULL({start_col}, '0001-01-01 00:00:00') <= %s
          AND IFNULL({end_col},   '2199-12-31 00:00:00') >= %s
        """,
        (end, start),
        as_list=True
    )
 
    expense_names = [e[0] for e in expense_names]
 
    if not expense_names:
        return []
 
    # STEP 2 → Fetch required fields
    if not fields:
        fields = [
            field_map.start,
            field_map.end,
            field_map.title,
            "name",
            "type",
            "amount"
        ]
 
    if field_map.color:
        fields.append(field_map.color)
 
    events = frappe.get_list(
        doctype,
        fields=list(set(fields)),
        filters={"name": ["in", expense_names]}
    )
 
    # STEP 3 → Format for FullCalendar
    for e in events:
        start_dt = e.get(field_map.start)
        end_dt   = e.get(field_map.end)
 
        # Required for FullCalendar
        e["id"] = e["name"]
 
        # ISO formatting
        if start_dt:
            e["start"] = start_dt.isoformat() + "+05:30"
        if end_dt:
            e["end"] = end_dt.isoformat() + "+05:30"
 
        # Title formatting: "Amount - Title"
        title = e.get(field_map.title) or ""
        amount = e.get("amount") or 0
        e["title"] = f"₹{amount} - {title}"
 
        # Colors: Income (Green), Expense (Red)
        type_ = e.get("type")
        color_map = {
            "Income": "#28a745",
            "Expense": "#dc3545",
        }
        e["color"] = color_map.get(type_, "#6c757d")
 
        # All-day
        e["allDay"] = True
 
    return events




@frappe.whitelist()
def get_events_with_category(start, end, filters=None):
    events = frappe.db.sql("""
        SELECT 
            name, subject, event_category, event_type,
            starts_on,
            COALESCE(ends_on, starts_on) AS ends_on,
            color
        FROM `tabEvent`
        WHERE starts_on <= %s
        AND COALESCE(ends_on, starts_on) >= %s
    """, (end, start), as_dict=True)

    # Fix ending date for FullCalendar → must be exclusive
    for e in events:
        if e.get("ends_on"):
            start_dt = get_datetime(e["starts_on"])
            end_dt   = get_datetime(e["ends_on"])

            # Only add +1 day when event spans multiple days
            if end_dt.date() > start_dt.date():
                e["ends_on"] = add_days(end_dt, 1)

    return events


def sync_event_to_call(doc, method):
    """Sync Event changes back to Calls (bi-directional sync)."""

    # Avoid infinite loop
    if frappe.flags.get("ignore_event_sync"):
        return

    # Only sync when event is linked to Calls
    if doc.reference_doctype != "Calls" or not doc.reference_docname:
        return

    call = frappe.get_doc("Calls", doc.reference_docname)

    # Title (subject before '- hh:mm')
    if doc.subject:
        call.title = doc.subject.split("-")[0].strip()

    # Time
    call.call_start_time = doc.starts_on
    call.call_end_time = doc.ends_on

    # Status
    call.outgoing_call_status = "Completed" if doc.status == "Completed" else "Scheduled"

    # Prevent loop
    frappe.flags.ignore_call_sync = True

    call.save(ignore_permissions=True)



def sync_event_to_meeting(doc, method):
    """Sync Event changes back to Meeting (bi-directional sync)."""

    # Avoid infinite loop
    if frappe.flags.get("ignore_meeting_sync"):
        return

    # Only sync when event is linked to Meeting
    if doc.reference_doctype != "Meeting" or not doc.reference_docname:
        return

    meeting = frappe.get_doc("Meeting", doc.reference_docname)

    # Title (subject before '- hh:mm')
    if doc.subject:
        meeting.title = doc.subject.split("-")[0].strip()

    # Time — MUST use update() because 'from' is a Python keyword
    meeting.update({
        "from": doc.starts_on,
        "to": doc.ends_on
    })

    # Status
    meeting.outgoing_call_status = (
        "Completed" if doc.status == "Completed" else "Scheduled"
    )

    # Prevent loop
    frappe.flags.ignore_meeting_sync = True
    meeting.save(ignore_permissions=True)
    frappe.flags.ignore_meeting_sync = False


def sync_event_to_todo(doc, method):    
    """Sync Event changes back to ToDo (bi-directional sync)."""

    # Avoid infinite loop
    if frappe.flags.get("ignore_todo_sync"):
        return

    # Only sync when event is linked to ToDo
    if doc.reference_doctype != "ToDo" or not doc.reference_docname:
        return

    todo = frappe.get_doc("ToDo", doc.reference_docname)

    # Title (subject before '- hh:mm')
    if doc.subject:
        todo.description = doc.subject.split("-")[0].strip()

    todo.update({
        "date": doc.starts_on,
    })

    todo.priority = doc.priority
    # Status
    todo.status = (
        "Closed" if doc.status == "Closed" else "Open"
    )   

    # Prevent loop
    frappe.flags.ignore_todo_sync = True
    todo.save(ignore_permissions=True)
    frappe.flags.ignore_todo_sync = False



def validate_event(doc, method=None):
    """
    Calendar validation for Calls, Meetings, and ToDo
    """

    # No reference → ignore
    if not doc.reference_doctype or not doc.reference_docname:
        return

    # -------------------------
    # CALLS
    # -------------------------
    if doc.reference_doctype == "Calls":
        _validate_call_event(doc)

    # -------------------------
    # MEETINGS
    # -------------------------
    elif doc.reference_doctype == "Meeting":
        _validate_meeting_event(doc)

    # -------------------------
    # TODO
    # -------------------------
    elif doc.reference_doctype == "ToDo":
        _validate_todo_event(doc)


def _validate_call_event(doc):
    """
    Calendar-level validation for Calls
    """

    start_dt = get_datetime(doc.starts_on) if doc.starts_on else None
    end_dt   = get_datetime(doc.ends_on) if doc.ends_on else None
    now_dt   = now_datetime()

    # -------------------------
    # BASIC SANITY
    # -------------------------
    if start_dt and end_dt and start_dt > end_dt:
        frappe.throw("Call start time cannot be after end time.")

    # -------------------------
    # 🔑 USE EVENT STATUS ONLY
    # -------------------------

    # 🔵 Scheduled (Open)
    if doc.status == "Open":
        if not start_dt:
            frappe.throw("Call start time is required.")

        if start_dt < now_dt:
            frappe.throw("Scheduled Call Time cannot be in the past.")

    # 🟢 Completed
    elif doc.status == "Completed":
        if not end_dt:
            frappe.throw("Completed Call must have an end time.")

        if end_dt > now_dt:
            frappe.throw("Completed Call End Time cannot be in the future.")



# ------------------------------------------------
# MEETING VALIDATION (FIXED)
# ------------------------------------------------
def _validate_meeting_event(doc):
    meeting = frappe.get_doc("Meeting", doc.reference_docname)

    if not doc.starts_on:
        frappe.throw("Meeting start time is required.")

    start_dt = get_datetime(doc.starts_on)
    now_dt = now_datetime()

    # Scheduled → future only
    if meeting.outgoing_call_status == "Scheduled":
        if start_dt < now_dt:
            frappe.throw("Scheduled Meeting cannot be in the past.")

    # Completed → past only
    elif meeting.outgoing_call_status == "Completed":
        if start_dt > now_dt:
            frappe.throw("Completed Meeting cannot be in the future.")


# ------------------------------------------------
# TODO VALIDATION (TODAY ALLOWED)
# ------------------------------------------------
def _validate_todo_event(doc):

    todo = frappe.get_doc("ToDo", doc.reference_docname)

    if not doc.starts_on:
        frappe.throw("ToDo due date is required.")

    start_dt = get_datetime(doc.starts_on)
    today = now_datetime().date()
    start_date = start_dt.date()

    # -------------------------
    # OPEN TODO
    # -------------------------
    if todo.status == "Open":
        # ❌ Yesterday or earlier
        if start_date < today:
            frappe.throw("Open ToDo cannot have a past due date.")

    # -------------------------
    # CLOSED TODO
    # -------------------------
    elif todo.status == "Closed":
        # ❌ Future dates
        if start_date > today:
            frappe.throw("Completed ToDo cannot be in the future.")


