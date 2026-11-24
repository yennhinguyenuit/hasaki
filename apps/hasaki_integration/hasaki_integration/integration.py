"""HTTP-only integration helpers: bounded JSON, atomic events and safe responses."""

import hashlib
import json

import frappe
from frappe.utils import now_datetime
from redis.exceptions import LockError

ENDPOINTS = {
	"/api/method/hasaki_integration.wordpress.receive_lead",
	"/api/method/hasaki_integration.woocommerce.receive_order",
}


class APIError(Exception):
	def __init__(self, code, message, status=400):
		super().__init__(message)
		self.code, self.message, self.status = code, message, status


def failure(code, message, status=400):
	frappe.local.response["http_status_code"] = status
	return {"ok": False, "code": code, "data": {}, "error": {"message": message}}


def error_response(exc):
	return failure(exc.code, exc.message, exc.status)


def success(reference_doctype, reference_name, event_name, idempotent=False, **extra):
	key = "lead" if reference_doctype == "CRM Lead" else "order"
	return {
		"ok": True,
		"code": "ALREADY_PROCESSED" if idempotent else "PROCESSED",
		"data": {key: reference_name, "event": event_name, **extra},
		"idempotent": idempotent,
	}


def read_json(limit):
	if not frappe.request.is_json:
		raise APIError("VALIDATION_ERROR", "Content-Type must be application/json", 415)
	raw = frappe.request.get_data(cache=True)
	if len(raw) > limit:
		raise APIError("VALIDATION_ERROR", "Request body is too large", 413)
	try:
		payload = json.loads(raw)
	except (ValueError, UnicodeDecodeError):
		raise APIError("VALIDATION_ERROR", "Request must contain valid JSON")
	if not isinstance(payload, dict):
		raise APIError("VALIDATION_ERROR", "Request must be a JSON object")
	return payload, raw


def text(payload, key, required=False, maximum=140):
	value = payload.get(key, "")
	if not isinstance(value, str):
		raise APIError("VALIDATION_ERROR", f"{key} must be a string")
	value = value.strip()
	if (required and not value) or len(value) > maximum or "\x00" in value:
		raise APIError("VALIDATION_ERROR", f"{key} is missing or invalid")
	return value


def digest(payload):
	return hashlib.sha256(
		json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
	).hexdigest()


def require_lead_token():
	# Frappe validates api_key:api_secret before dispatch. Also reject cookie-only
	# sessions and API keys belonging to a different session user.
	authorization = frappe.get_request_header("Authorization", "")
	parts = authorization.split()
	if len(parts) != 2 or parts[0].lower() != "token" or parts[1].count(":") != 1:
		raise APIError("UNAUTHORIZED", "A Frappe API Token is required", 401)
	api_key, api_secret = parts[1].split(":", 1)
	user = frappe.db.get_value("User", {"api_key": api_key, "enabled": 1}, "name")
	if not api_secret or not user or user != frappe.session.user or user == "Guest":
		raise APIError("UNAUTHORIZED", "Invalid API Token", 401)
	if not frappe.has_permission("CRM Lead", "create"):
		raise APIError("UNAUTHORIZED", "The API user cannot create CRM Lead", 403)


def process_event(source, event_id, object_id, event_type, key, payload_hash, handler):
	"""Own the HTTP transaction. Commit business data and event before releasing lock.

	A failed handler is rolled back to the event savepoint, preserving only a
	minimal failure event. No request body or credentials are persisted in logs.
	"""
	lock_name = "hasaki:event:" + hashlib.sha256(key.encode()).hexdigest()
	try:
		with frappe.cache.lock(lock_name, timeout=120, blocking_timeout=10):
			# Authentication did read-only queries before this lock. Start a fresh
			# transaction so MariaDB REPEATABLE READ sees the prior request's commit.
			frappe.db.rollback()
			row = frappe.db.get_value(
				"HSK Integration Event", {"idempotency_key": key},
				["name", "payload_sha256", "status", "reference_doctype", "reference_name"],
				as_dict=True, for_update=True,
			)
			if row:
				if row.payload_sha256 != payload_hash:
					raise APIError("CONFLICT", "The event key was already used with a different payload", 409)
				if row.status == "Processed":
					if not frappe.db.exists(row.reference_doctype, row.reference_name):
						raise APIError("CONFLICT", "The original referenced record no longer exists", 409)
					return success(row.reference_doctype, row.reference_name, row.name, idempotent=True)
				event = frappe.get_doc("HSK Integration Event", row.name)
				event.status = "Received"
				event.error_summary = None
			else:
				event = frappe.get_doc({
					"doctype": "HSK Integration Event", "source": source, "event_id": event_id,
					"idempotency_key": key, "external_object_id": object_id,
					"event_type": event_type, "payload_sha256": payload_hash, "status": "Received",
				}).insert(ignore_permissions=True)
			frappe.db.savepoint("hasaki_business")
			try:
				doctype, name, extra = handler()
			except Exception as exc:
				frappe.db.rollback(save_point="hasaki_business")
				if not isinstance(exc, APIError):
					if isinstance(exc, frappe.PermissionError):
						exc = APIError("UNAUTHORIZED", "The integration user lacks required permissions", 403)
					elif isinstance(exc, frappe.ValidationError):
						exc = APIError("VALIDATION_ERROR", "Transaction validation failed")
					else:
						exc = APIError("INTERNAL_ERROR", "Integration processing failed", 500)
				event.status = "Failed"
				event.error_summary = f"{exc.code}: {exc.message}"
				event.processed_at = now_datetime()
				event.save(ignore_permissions=True)
				frappe.db.commit()
				return error_response(exc)
			event.status = "Processed"
			event.reference_doctype, event.reference_name = doctype, name
			event.processed_at = now_datetime()
			event.error_summary = None
			event.save(ignore_permissions=True)
			frappe.db.commit()
			return success(doctype, name, event.name, **extra)
	except LockError:
		raise APIError("CONFLICT", "This event is being processed; retry later", 409)


def normalize_error_response(request, response):
	"""Scope framework errors to these two methods; never change other CRM APIs."""
	if request.path not in ENDPOINTS or response is None or response.status_code < 400:
		return
	current = response.get_json(silent=True) or {}
	if isinstance(current, dict) and isinstance(current.get("message"), dict) and "ok" in current["message"]:
		return
	status = response.status_code
	code = {
		401: "UNAUTHORIZED", 403: "UNAUTHORIZED", 405: "VALIDATION_ERROR",
		409: "CONFLICT", 413: "VALIDATION_ERROR", 415: "VALIDATION_ERROR",
	}.get(status, "INTERNAL_ERROR" if status >= 500 else "VALIDATION_ERROR")
	message = "Authentication or permission denied" if code == "UNAUTHORIZED" else "Request rejected"
	response.set_data(json.dumps({"message": {
		"ok": False, "code": code, "data": {}, "error": {"message": message},
	}}))
	response.content_type = "application/json"
