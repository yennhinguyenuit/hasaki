"""Native WooCommerce order webhooks; no Product or Contact creation."""

import base64
import hashlib
import hmac
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import frappe
from redis.exceptions import LockError

from hasaki_integration.integration import APIError, error_response, process_event, read_json, text

ORDER_STATUS = {
	"pending": "Pending", "on-hold": "Pending", "failed": "Pending",
	"processing": "Processing", "completed": "Completed", "cancelled": "Cancelled",
	# An order-level refunded label is not proof of a completed refund transaction.
	"refunded": "Completed",
}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive_order(**kwargs):
	try:
		# WooCommerce performs an unsigned form-encoded delivery-URL probe on
		# activation. Acknowledge the probe without reading or writing any data.
		if not frappe.request.is_json and set(frappe.request.form) == {"webhook_id"}:
			if re.fullmatch(r"[1-9][0-9]*", frappe.request.form["webhook_id"]):
				return {"ok": True, "code": "WEBHOOK_PROBE", "data": {}}
		config = _authenticate()
		payload, raw = read_json(1024 * 1024)
		topic = frappe.get_request_header("X-WC-Webhook-Topic", "")
		if topic not in ("order.created", "order.updated"):
			raise APIError("VALIDATION_ERROR", "Unsupported WooCommerce topic")
		event_id = frappe.get_request_header("X-WC-Webhook-Delivery-ID", "")
		if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", event_id):
			raise APIError("VALIDATION_ERROR", "A valid X-WC-Webhook-Delivery-ID is required")
		order_id = _identifier(payload.get("id"), "id")
		store = config["source_store"]
		integration_key = f"woo:{store}:{order_id}"
		user = config["user"]
		if not frappe.db.exists("User", {"name": user, "enabled": 1}):
			raise APIError("CONFLICT", "The configured existing integration user is unavailable", 409)
		frappe.set_user(user)
		if not all(frappe.has_permission(dt, permission_type) for dt, permission_type in (
			("HSK Order", "create"), ("HSK Order", "write"), ("HSK Payment", "create"),
		)):
			raise APIError("UNAUTHORIZED", "The webhook user lacks Order or Payment permissions", 403)
		payload_hash = hashlib.sha256(raw).hexdigest()
		# Native WooCommerce can reuse a Delivery-ID for deliveries from the
		# same webhook in one second. Scope the deduplication key by the order,
		# topic and signed body as well, so distinct deliveries are not lost.
		event_hash = hashlib.sha256(f"{topic}\n{order_id}\n{event_id}\n{payload_hash}".encode()).hexdigest()
		# Different deliveries of the same order must serialize as well as exact
		# duplicate events. The inner transaction commits before either lock exits.
		lock_name = "hasaki:order:" + hashlib.sha256(integration_key.encode()).hexdigest()
		with frappe.cache.lock(lock_name, timeout=120, blocking_timeout=10):
			return process_event(
				"WooCommerce", event_id, order_id, topic, f"woo:event:{store}:{event_hash}",
				payload_hash, lambda: _sync_order(payload, topic, integration_key, store, payload_hash),
			)
	except LockError:
		return error_response(APIError("CONFLICT", "This order is being processed; retry later", 409))
	except APIError as exc:
		return error_response(exc)


def _authenticate():
	configs = frappe.conf.get("hasaki_woocommerce_stores") or {}
	source_url = frappe.get_request_header("X-WC-Webhook-Source", "").rstrip("/")
	config = configs.get(source_url)
	if not isinstance(config, dict) or not config.get("secret"):
		raise APIError("INVALID_SIGNATURE", "Unknown webhook source or invalid signature", 401)
	store = config.get("source_store", "")
	if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", store) or not config.get("user"):
		raise APIError("CONFLICT", "WooCommerce store configuration is incomplete", 409)
	raw = frappe.request.get_data(cache=True)
	if len(raw) > 1024 * 1024:
		raise APIError("VALIDATION_ERROR", "Request body is too large", 413)
	expected = base64.b64encode(hmac.new(config["secret"].encode(), raw, hashlib.sha256).digest()).decode()
	signature = frappe.get_request_header("X-WC-Webhook-Signature", "")
	if not hmac.compare_digest(expected, signature):
		raise APIError("INVALID_SIGNATURE", "Invalid webhook signature", 401)
	return config


def _identifier(value, fieldname):
	if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,19}", str(value)):
		raise APIError("VALIDATION_ERROR", f"{fieldname} must be a positive integer ID")
	return str(value)


def _money(value, fieldname):
	if isinstance(value, bool):
		raise APIError("VALIDATION_ERROR", f"{fieldname} must be numeric")
	try:
		number = Decimal(str(value))
		if not number.is_finite() or number < 0 or number > Decimal("9999999999999.99"):
			raise InvalidOperation
	except (InvalidOperation, ValueError, TypeError):
		raise APIError("VALIDATION_ERROR", f"{fieldname} must be a finite nonnegative number")
	return number


def _date(value, fieldname, required=True):
	if not value and not required:
		return None
	try:
		parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
		if parsed.tzinfo is None:
			parsed = parsed.replace(tzinfo=timezone.utc)
		return parsed.astimezone(ZoneInfo(frappe.get_system_settings("time_zone"))).replace(tzinfo=None)
	except (AttributeError, TypeError, ValueError):
		raise APIError("VALIDATION_ERROR", f"{fieldname} must be an ISO datetime")


def _contact(billing):
	# Match exact existing email/phone keys. Ambiguous or inconsistent matches
	# stay as guests, rather than choosing an unrelated Contact.
	matches = set()
	for fieldname, value in (("email_id", billing.get("email")), ("mobile_no", billing.get("phone"))):
		if value:
			matches.update(frappe.get_all("Contact", filters={fieldname: value}, pluck="name"))
	return next(iter(matches)) if len(matches) == 1 else None


def _sync_order(payload, topic, key, store, payload_hash):
	modified = _date(payload.get("date_modified_gmt"), "date_modified_gmt")
	name = frappe.db.get_value("HSK Order", {"integration_key": key}, "name", for_update=True)
	order = frappe.get_doc("HSK Order", name) if name else frappe.new_doc("HSK Order")
	if name and order.last_source_modified_at:
		if modified < order.last_source_modified_at:
			return "HSK Order", name, {"ignored_stale": True}
		if modified == order.last_source_modified_at:
			if payload_hash == order.last_source_payload_sha256:
				return "HSK Order", name, {"unchanged": True}
			raise APIError("CONFLICT", "Different payloads have the same date_modified_gmt", 409)
	if not name and topic == "order.updated":
		raise APIError("CONFLICT", "Order does not exist yet; deliver order.created first", 409)
	if payload.get("currency") != "VND":
		raise APIError("VALIDATION_ERROR", "Only VND orders are supported")
	status = ORDER_STATUS.get(payload.get("status"))
	if not status:
		raise APIError("VALIDATION_ERROR", "Unsupported WooCommerce order status")
	billing = payload.get("billing", {})
	if not isinstance(billing, dict):
		raise APIError("VALIDATION_ERROR", "billing must be an object")
	first, last = text(billing, "first_name"), text(billing, "last_name")
	full_name = " ".join(filter(None, (first, last)))
	if len(full_name) > 140:
		raise APIError("VALIDATION_ERROR", "Combined billing name is too long")
	phone, email = text(billing, "phone", maximum=32), text(billing, "email")
	if email and frappe.utils.validate_email_address(email) != email:
		raise APIError("VALIDATION_ERROR", "billing.email is invalid")
	lines = payload.get("line_items")
	if not isinstance(lines, list) or not lines or len(lines) > 500:
		raise APIError("VALIDATION_ERROR", "line_items must contain 1 to 500 items")
	old_items = {row.external_line_id: row for row in order.items or []}
	items, line_ids = [], set()
	for line in lines:
		if not isinstance(line, dict):
			raise APIError("VALIDATION_ERROR", "Each line item must be an object")
		line_id = _identifier(line.get("id"), "line_items.id")
		if line_id in line_ids:
			raise APIError("VALIDATION_ERROR", "Duplicate line item ID")
		line_ids.add(line_id)
		sku = text(line, "sku", required=True)
		product = frappe.db.get_value("CRM Product", {"product_code": sku}, ["name", "custom_cost_price", "disabled"], as_dict=True)
		if not product:
			raise APIError("SKU_NOT_FOUND", "An order SKU is absent from existing CRM Products", 422)
		qty = _money(line.get("quantity"), "line_items.quantity")
		if not qty or qty > 1000000:
			raise APIError("VALIDATION_ERROR", "line_items.quantity must be greater than zero and at most 1000000")
		subtotal = _money(line.get("subtotal"), "line_items.subtotal")
		total = _money(line.get("total"), "line_items.total")
		if total > subtotal:
			raise APIError("VALIDATION_ERROR", "line_items.total cannot exceed subtotal")
		old = old_items.get(line_id)
		if product.disabled and (not old or old.product != product.name):
			raise APIError("CONFLICT", "An order product is disabled", 409)
		items.append({
			"product": product.name, "external_line_id": line_id, "sku": sku, "qty": float(qty),
			"unit_price": float(subtotal / qty), "discount_amount": float(subtotal - total),
			"line_total": float(total),
			"cost_price": old.cost_price if old and old.product == product.name else product.custom_cost_price,
			"loyalty_eligible": old.loyalty_eligible if old else 0,
		})
	total = _money(payload.get("total"), "total")
	paid_at = _date(payload.get("date_paid_gmt"), "date_paid_gmt", required=False)
	if paid_at and status in ("Pending", "Cancelled"):
		raise APIError("CONFLICT", "Payment confirmation conflicts with the order status", 409)
	order.update({
		"source_channel": "WooCommerce", "source_store": store,
		"external_order_id": str(payload["id"]), "integration_key": key,
		"order_date": _date(payload.get("date_created_gmt"), "date_created_gmt"),
		"status": status, "currency": "VND", "grand_total": float(total),
		"discount_total": float(_money(payload.get("discount_total"), "discount_total")),
		"shipping_total": float(_money(payload.get("shipping_total"), "shipping_total")),
		"customer": _contact(billing), "guest_full_name": full_name,
		"guest_phone": phone, "guest_email": email,
		"last_source_modified_at": modified, "last_source_payload_sha256": payload_hash,
		"items": items,
	})
	order.save()
	if paid_at:
		_save_payment(order, payload, paid_at)
	return "HSK Order", order.name, {}


def _save_payment(order, payload, paid_at):
	key = order.integration_key + ":payment"
	name = frappe.db.get_value("HSK Payment", {"payment_integration_key": key}, "name", for_update=True)
	method = text(payload, "payment_method", required=True)
	transaction_id = text(payload, "transaction_id")
	if name:
		payment = frappe.get_doc("HSK Payment", name)
		# A later order payload must not mutate a financial record or reverse a
		# refund handled by its owning app. Conflicts require explicit resolution.
		if Decimal(str(payment.amount)) != Decimal(str(order.grand_total)):
			raise APIError("CONFLICT", "The confirmed payment amount cannot be changed", 409)
		if payment.transaction_id != transaction_id or payment.payment_method != method:
			raise APIError("CONFLICT", "Confirmed payment identity cannot be changed", 409)
		return
	frappe.get_doc({
		"doctype": "HSK Payment", "order": order.name, "amount": order.grand_total,
		"payment_method": method, "transaction_id": transaction_id, "paid_at": paid_at,
		"status": "Paid", "payment_integration_key": key,
	}).insert()
