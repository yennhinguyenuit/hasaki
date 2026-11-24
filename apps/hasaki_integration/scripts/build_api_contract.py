"""Generate the OpenAPI contract for the implemented Hasaki Method APIs."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ref(name):
	return {"$ref": "#/components/schemas/" + name}


def string(**extra):
	return {"type": "string", **extra}


def build():
	leads = {
		"submission_id": string(minLength=1, maxLength=140),
		"first_name": string(minLength=1, maxLength=140),
		"last_name": string(maxLength=140),
		"phone": string(minLength=7, maxLength=32, description="7 to 15 digits, optional leading + and formatting; stored in CRM Lead.mobile_no"),
		"email": string(format="email", maxLength=140, description="Optional; empty string is also accepted"),
		"message": string(minLength=1, maxLength=10000),
		"consent": {"type": "boolean", "enum": [True]},
	}
	responses = {
		"200": {"description": "Processed or a valid replay", "content": {"application/json": {"schema": ref("Envelope")}}},
		**{
			str(code): {"description": label, "content": {"application/json": {"schema": ref("Envelope")}}}
			for code, label in {
				400: "VALIDATION_ERROR", 401: "UNAUTHORIZED or INVALID_SIGNATURE", 403: "UNAUTHORIZED",
				409: "CONFLICT", 413: "VALIDATION_ERROR: body too large", 415: "VALIDATION_ERROR: media type",
				422: "SKU_NOT_FOUND", 500: "INTERNAL_ERROR",
			}.items()
		},
	}
	lead_operation = {
		"operationId": "receiveLead", "summary": "WordPress backend submits a consulting request",
		"security": [{"FrappeToken": []}],
		"description": "POST only. Native Frappe API Token from an enabled existing user with CRM Lead create permission. "
			"Cookie-only authentication is rejected. Maximum body: 65536 bytes. Source must already be Web Form. "
			"No Contact creation. message becomes an escaped Comment linked to the Lead. "
			"Idempotency key = wp:lead:SHA256(trimmed submission_id); Event.event_id and external_object_id retain submission_id. "
			"The normalized JSON payload is hashed. Same key and same payload returns the original Lead; "
			"different payload returns 409. Failed identical requests can be retried after fixing an external prerequisite. "
			"Client errors without a valid submission_id, and authentication failures, do not create Events.",
		"requestBody": {"required": True, "content": {"application/json": {"schema": ref("LeadSubmission"), "example": {
			"submission_id": "wp-form-example-001", "first_name": "Khach", "last_name": "Test",
			"phone": "0900000000", "email": "test@example.invalid", "message": "Yeu cau tu van", "consent": True,
		}}}},
		"responses": {k: v for k, v in responses.items() if k != "422"},
	}
	order_operation = {
		"operationId": "receiveOrder", "summary": "Receive a native signed WooCommerce order webhook",
		"security": [{"WooSignature": []}],
		"description": "POST only. HMAC-SHA256 of exact raw body, base64 encoded. Maximum body: 1048576 bytes. "
			"Unknown sources/invalid signatures have no business writes or Integration Events. "
			"Order key = woo:{source_store}:{id}. Event key = woo:event:{source_store}:SHA256(topic + newline + id + newline + delivery_id + newline + raw_body_sha256). "
			"order.updated requires a previously created Order. Old date_modified_gmt is acknowledged with ignored_stale=true. "
			"Equal timestamp with an identical raw hash is acknowledged unchanged; a different hash returns 409. "
			"SKU maps to existing CRM Product.product_code; missing SKU fails atomically with 422. "
			"Contact matches exact existing email_id/mobile_no; ambiguous or absent matches stay guests. "
			"date_paid_gmt on a non-Pending/non-Cancelled order creates at most one payment under {order_key}:payment. "
			"Paid amount and transaction identity cannot be silently changed. No loyalty, voucher or refund execution. "
			"An unsigned form-encoded positive webhook_id activation probe returns WEBHOOK_PROBE and writes nothing.",
		"parameters": [
			{"name": "X-WC-Webhook-Source", "in": "header", "required": True, "schema": string(),
				"description": "home_url('/'); must match a configured source URL after stripping trailing slash"},
			{"name": "X-WC-Webhook-Topic", "in": "header", "required": True,
				"schema": string(enum=["order.created", "order.updated"])},
			{"name": "X-WC-Webhook-Delivery-ID", "in": "header", "required": True,
				"schema": string(pattern="^[A-Za-z0-9_.-]{1,100}$")},
		],
		"requestBody": {"required": True, "content": {"application/json": {"schema": ref("WooOrder")},
			"application/x-www-form-urlencoded": {"schema": {"type": "object", "required": ["webhook_id"],
				"properties": {"webhook_id": string(pattern="^[1-9][0-9]*$")}}}}},
		"responses": responses,
	}
	contract = {
		"openapi": "3.0.3", "info": {"title": "Hasaki Integration A4.8", "version": "1.1.0",
			"description": "Implemented against TECHNICAL_CONTRACT.md v1.1. Secrets are server configuration, never repository contents."},
		"servers": [
			{"url": "http://127.0.0.1:8000", "description": "Verified Windows/XAMPP backend address; send X-Frappe-Site-Name: crm.localhost"},
			{"url": "http://crm.localhost:8000", "description": "Site hostname, when DNS resolves it to the local CRM server"},
		],
		"paths": {
			"/api/method/hasaki_integration.wordpress.receive_lead": {"post": lead_operation},
			"/api/method/hasaki_integration.woocommerce.receive_order": {"post": order_operation},
		},
		"components": {
			"securitySchemes": {
				"FrappeToken": {"type": "apiKey", "in": "header", "name": "Authorization", "description": "token <api_key>:<api_secret>"},
				"WooSignature": {"type": "apiKey", "in": "header", "name": "X-WC-Webhook-Signature", "description": "base64(HMAC-SHA256(secret, raw_body))"},
			},
			"schemas": {
				"LeadSubmission": {"type": "object", "additionalProperties": False,
					"required": ["submission_id", "first_name", "phone", "message", "consent"], "properties": leads},
				"Envelope": {"type": "object", "required": ["message"], "properties": {
					"message": {"type": "object", "required": ["ok", "code", "data"], "properties": {
						"ok": {"type": "boolean"}, "code": string(), "idempotent": {"type": "boolean"},
						"data": {"type": "object", "properties": {"lead": string(), "order": string(), "event": string(),
							"ignored_stale": {"type": "boolean"}, "unchanged": {"type": "boolean"}}},
						"error": {"type": "object", "properties": {"message": string()}},
					}},
				}},
				"WooOrder": {
					"type": "object", "additionalProperties": True,
					"required": ["id", "status", "currency", "date_created_gmt", "date_modified_gmt", "line_items", "total", "discount_total", "shipping_total"],
					"properties": {
						"id": {"type": "integer", "minimum": 1},
						"status": string(enum=["pending", "on-hold", "failed", "processing", "completed", "cancelled", "refunded"]),
						"currency": string(enum=["VND"]), "date_created_gmt": string(), "date_modified_gmt": string(),
						"date_paid_gmt": string(nullable=True, description="UTC date; null/empty means no payment confirmation"),
						"billing": {"type": "object", "properties": {key: string() for key in ("first_name", "last_name", "phone", "email")}},
						"total": string(), "discount_total": string(), "shipping_total": string(),
						"payment_method": string(description="Required when date_paid_gmt is present"), "transaction_id": string(),
						"line_items": {"type": "array", "minItems": 1, "maxItems": 500, "items": {
							"type": "object", "required": ["id", "sku", "quantity", "subtotal", "total"], "properties": {
								"id": {"type": "integer", "minimum": 1}, "sku": string(minLength=1, maxLength=140),
								"quantity": {"type": "number", "exclusiveMinimum": True, "minimum": 0, "maximum": 1000000},
								"subtotal": string(), "total": string(),
							}, "additionalProperties": True,
						}},
					},
				},
			},
		},
		"x-order-status-mapping": {"pending": "Pending", "on-hold": "Pending", "failed": "Pending",
			"processing": "Processing", "completed": "Completed", "cancelled": "Cancelled", "refunded": "Completed"},
		"x-config": {
			"frappe_site_config": {"hasaki_woocommerce_stores": {"<WordPress home_url without trailing slash>": {
				"source_store": "<stable store code: letters, digits, underscore or hyphen, max 60>",
				"secret": "<same private secret as WooCommerce>", "user": "<enabled existing CRM user>",
			}}},
			"wordpress_server_constants_or_environment": ["HASAKI_CRM_BASE_URL", "HASAKI_CRM_API_KEY", "HASAKI_CRM_API_SECRET", "HASAKI_CRM_SITE", "HASAKI_WC_WEBHOOK_SECRET"],
		},
		"x-local-deployment": {
			"wordpress_root": "D:\\baitap\\htdocs\\shopdongho", "wordpress_url": "http://localhost:8080/shopdongho/",
			"crm_site": "crm.localhost", "backend_crm_url": "http://127.0.0.1:8000",
			"site_header": "X-Frappe-Site-Name: crm.localhost", "source_store": "hasaki-local",
			"existing_crm_user": "tuvan@hasaki.example", "webhook_ids": {"order.created": 1, "order.updated": 2},
			"secrets": "Existing WordPress private config and CRM site_config; no secrets included in this contract",
		},
		"x-implementation-decisions": [
			"Native WooCommerce can reuse Delivery-ID within one second; event deduplication also includes topic, order ID and signed body hash.",
			"All _gmt dates are converted to the existing site timezone Asia/Ho_Chi_Minh before Frappe Datetime storage.",
			"Native WooCommerce has no Shipping status; unsupported custom statuses require an explicit mapping change.",
			"Refunded source status is treated as a completed historical sale; actual refund effects belong to the refund owner's workflow.",
			"No business master records are created or updated by either endpoint.",
			"Event, order and payment transactions use Redis locks plus DB unique indexes and atomic commits.",
		],
	}
	(ROOT / "docs" / "API_CONTRACT.openapi.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
	build()
