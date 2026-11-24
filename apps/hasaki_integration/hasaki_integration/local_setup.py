"""Local operator setup, deliberately not exposed as an HTTP method.

The credential-returning function must only be called by the local setup
script which consumes stdout in memory; never print its return value to chat.
"""

import secrets

import frappe
from frappe.installer import update_site_config
from frappe.utils.password import get_decrypted_password, set_encrypted_password


def configure_existing_wordpress():
	user = "tuvan@hasaki.example"
	url, store = "http://localhost:8080/shopdongho", "hasaki-local"
	if not frappe.db.exists("User", {"name": user, "enabled": 1}):
		raise RuntimeError("Existing enabled integration user is required")
	if "Sales User" not in frappe.get_roles(user):
		raise RuntimeError("Existing integration user must already have the Sales User role")
	key = frappe.db.get_value("User", user, "api_key")
	api_secret = get_decrypted_password("User", user, "api_secret", raise_exception=False)
	if not key or not api_secret:
		key = key or secrets.token_hex(16)
		api_secret = api_secret or secrets.token_hex(24)
		frappe.db.set_value("User", user, "api_key", key, update_modified=False)
		set_encrypted_password("User", user, api_secret, fieldname="api_secret")
	stores = dict(frappe.conf.get("hasaki_woocommerce_stores") or {})
	config = stores.get(url)
	if config and (config.get("source_store") != store or config.get("user") != user):
		raise RuntimeError("Existing WooCommerce source configuration conflicts with the intended local store")
	webhook_secret = (config or {}).get("secret") or secrets.token_hex(32)
	stores[url] = {"source_store": store, "user": user, "secret": webhook_secret}
	frappe.db.commit()
	update_site_config("hasaki_woocommerce_stores", stores)
	return {"api_key": key, "api_secret": api_secret, "webhook_secret": webhook_secret, "user": user}
