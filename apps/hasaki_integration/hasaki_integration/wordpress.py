import hashlib
import html
import re

import frappe
from frappe.utils import validate_email_address

from hasaki_integration.integration import (
	APIError,
	digest,
	error_response,
	process_event,
	read_json,
	require_lead_token,
	text,
)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive_lead(**kwargs):
	"""Accept a server-to-server WordPress form using native Frappe API Tokens."""
	try:
		require_lead_token()
		payload, _ = read_json(64 * 1024)
		submission_id = text(payload, "submission_id", required=True)
		key = "wp:lead:" + hashlib.sha256(submission_id.encode()).hexdigest()
		return process_event(
			"WordPress", submission_id, submission_id, "lead.submitted", key, digest(payload),
			lambda: _create_lead(payload),
		)
	except APIError as exc:
		return error_response(exc)


def _create_lead(payload):
	allowed = {"submission_id", "first_name", "last_name", "phone", "email", "message", "consent"}
	if set(payload) - allowed:
		raise APIError("VALIDATION_ERROR", "Unexpected request fields")
	if payload.get("consent") is not True:
		raise APIError("VALIDATION_ERROR", "consent must be the JSON boolean true")
	first = text(payload, "first_name", required=True)
	last = text(payload, "last_name")
	phone = text(payload, "phone", required=True, maximum=32)
	if not re.fullmatch(r"\+?[0-9][0-9 ().-]{5,30}", phone) or not 7 <= len(re.sub(r"\D", "", phone)) <= 15:
		raise APIError("VALIDATION_ERROR", "phone must contain 7 to 15 digits")
	email = text(payload, "email")
	if email and validate_email_address(email) != email:
		raise APIError("VALIDATION_ERROR", "email is invalid")
	message = text(payload, "message", required=True, maximum=10000)
	if not frappe.db.exists("CRM Lead Source", "Web Form"):
		raise APIError("CONFLICT", "The existing Web Form lead source is required", 409)
	lead = frappe.get_doc({
		"doctype": "CRM Lead", "first_name": first, "last_name": last,
		"mobile_no": phone, "email": email, "source": "Web Form",
	}).insert()
	# Escape user HTML before using CRM's normal Comment API. The framework also
	# sanitizes Comment content; multiline plain text is represented with <br>.
	lead.add_comment("Comment", text=html.escape(message).replace("\n", "<br>"))
	return "CRM Lead", lead.name, {}
