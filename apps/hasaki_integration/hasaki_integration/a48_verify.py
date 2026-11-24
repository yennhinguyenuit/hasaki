"""Export final, secret-free deployment evidence for the current local site."""

import json
from pathlib import Path

import frappe

from hasaki_integration.a48_preflight import inspect_site


def inspect_external_flow(submission_id=None, external_order_id=None, include_product_codes=False):
	"""Local operator read: verify real WordPress delivery results, without tokens."""
	result = {"master_counts": {dt: frappe.db.count(dt) for dt in (
		"Contact", "CRM Product", "HSK Product Category", "User", "Role", "CRM Lead Source",
	)}}
	if include_product_codes:
		result["product_codes"] = frappe.get_all("CRM Product", pluck="product_code", order_by="product_code")
	if submission_id:
		events = frappe.get_all("HSK Integration Event", filters={
			"source": "WordPress", "external_object_id": submission_id,
		}, fields=["name", "status", "reference_name", "payload_sha256"])
		result["lead_events"] = events
		if events and events[0].reference_name:
			name = events[0].reference_name
			result["lead"] = frappe.db.get_value("CRM Lead", name,
				["name", "first_name", "last_name", "mobile_no", "email", "source"], as_dict=True)
			result["comments"] = frappe.get_all("Comment", filters={
				"reference_doctype": "CRM Lead", "reference_name": name, "comment_type": "Comment",
			}, fields=["name", "content"])
	if external_order_id:
		result["order_events"] = frappe.get_all("HSK Integration Event", filters={
			"source": "WooCommerce", "external_object_id": str(external_order_id),
		}, fields=["name", "event_type", "status", "reference_name", "error_summary"], order_by="creation")
		key = f"woo:hasaki-local:{external_order_id}"
		names = frappe.get_all("HSK Order", filters={"integration_key": key}, pluck="name")
		result["order_count"] = len(names)
		if names:
			order = frappe.get_doc("HSK Order", names[0])
			result["order"] = {key: order.get(key) for key in (
				"name", "status", "payment_status", "customer", "guest_full_name", "guest_phone", "guest_email",
				"grand_total", "integration_key", "last_source_modified_at", "items", "status_history",
			)}
			result["payments"] = frappe.get_all("HSK Payment", filters={"order": names[0]},
				fields=["name", "amount", "status", "paid_at", "payment_integration_key", "transaction_id"])
	return result


def export_evidence():
	root = Path(frappe.get_app_path("hasaki_integration")).parent
	docs = root / "docs"
	metadata = inspect_site()
	(docs / "a48_site_metadata.json").write_text(json.dumps(metadata, indent=2, default=str) + "\n")
	suites = {}
	for name in ("lead", "woocommerce", "schema"):
		report = json.loads((docs / f"test_results_{name}.json").read_text())
		suites[name] = {
			"status": "Passed" if report["passed"] else "Failed",
			"tests_run": report["tests_run"],
			"master_business_data_unchanged": report["master_business_data_unchanged"],
			"master_data_exactly_unchanged": report["master_data_exactly_unchanged"],
			"recorded_runtime_field_changes": report["changed_master_fields"],
		}
	lead_events = frappe.get_all("HSK Integration Event", filters={
		"source": "WordPress", "status": "Processed", "external_object_id": ["like", "a48-test-%"],
	}, fields=["name", "external_object_id", "reference_name"], order_by="creation desc", limit=3)
	lead_samples = []
	for event in lead_events:
		lead = frappe.db.get_value("CRM Lead", event.reference_name,
			["name", "first_name", "last_name", "mobile_no", "email", "source"], as_dict=True)
		lead_samples.append({"event": event, "lead": lead, "comments": frappe.get_all("Comment", filters={
			"reference_doctype": "CRM Lead", "reference_name": event.reference_name, "comment_type": "Comment",
		}, fields=["name", "content"])})
	orders = frappe.get_all("HSK Order", filters={"source_store": "a48-test"},
		fields=["name", "integration_key", "status", "payment_status", "grand_total"],
		order_by="creation desc", limit=3)
	status = {
		"technical_contract": "hasaki_integration/TECHNICAL_CONTRACT.md v1.1",
		"site": frappe.local.site, "checked_at": str(frappe.utils.now_datetime()),
		"backup_before_migration": {
			"status": "Passed", "kind": "Bench database and site-config backup; no restore performed",
			"database": "/home/frappe/frappe-bench/sites/crm.localhost/private/backups/20261124_112115-crm_localhost-database.sql.gz",
			"config": "/home/frappe/frappe-bench/sites/crm.localhost/private/backups/20261124_112115-crm_localhost-site_config_backup.json",
		},
		"migration": {"status": "Passed", "doctype_count": 5, "module": "Hasaki Integration"},
		"test_suites": suites,
		"python_compilation": "Passed", "php_syntax": "Passed", "php_adapter_doubles": "Passed",
		"wordpress_site_installation": {"status": "Not Tested", "reason": "No real website test evidence available"},
		"real_woocommerce_background_delivery": {"status": "Not Tested", "reason": "No native WooCommerce delivery evidence available"},
		"fresh_site_installation": {"status": "Not Tested", "reason": "User requested implementation on the existing local site; no site restore/reinstall performed"},
		"python_lint": {"status": "Not Tested", "reason": "Ruff is not installed in the existing Bench environment; compilation and git diff --check used"},
		"existing_user_api_token_configured": bool(frappe.db.get_value("User", "tuvan@hasaki.example", "api_key")),
		"persistent_woocommerce_store_configured": "http://localhost:8080/shopdongho" in (frappe.conf.get("hasaki_woocommerce_stores") or {}),
		"plugin_source": "wordpress-plugin/hasaki-crm-bridge/hasaki-crm-bridge.php",
		"master_counts": {dt: frappe.db.count(dt) for dt in (
			"Contact", "CRM Product", "HSK Product Category", "User", "Role", "CRM Lead Source",
		)},
		"transaction_counts": {dt: frappe.db.count(dt) for dt in (
			"CRM Lead", "CRM Deal", "HSK Order", "HSK Payment", "HSK Integration Event",
		)},
		"lead_evidence": lead_samples, "order_evidence": orders,
		"git": "No commit, push or merge performed; pre-existing .gitignore/.gitattributes edits preserved",
	}
	wp_report = docs / "test_results_wordpress_e2e.json"
	woo_report = docs / "test_results_woocommerce_e2e.json"
	preservation_report = docs / "wordpress_preservation.json"
	if wp_report.exists() and preservation_report.exists():
		wp = json.loads(wp_report.read_text())
		preservation = json.loads(preservation_report.read_text())
		status["wordpress_site_installation"] = {
			"status": wp["status"], "root": "D:\\baitap\\htdocs\\shopdongho", "url": wp["website"],
			"wordpress": "7.1.5", "woocommerce": "10.9.4", "php": "8.2.12",
			"lead": wp["crm_evidence"]["lead"]["name"], "checks": wp["checks"],
			"preservation": preservation,
		}
		status["wordpress_backup"] = {
			"database": "C:\\Users\\Yen Nhi\\frappe-crm-backups\\wordpress-a48-20261124\\wordpress-database.sql",
			"config": "C:\\Users\\Yen Nhi\\frappe-crm-backups\\wordpress-a48-20261124\\wp-config.php",
			"secrets_location": "C:\\Users\\Yen Nhi\\frappe-crm-backups\\hasaki-integration-private\\wordpress-secrets.php",
		}
		status["network"] = {
			"windows_crm_localhost_dns": "Unresolved at inspection",
			"wordpress_backend_crm_url": "http://127.0.0.1:8000",
			"site_header": "X-Frappe-Site-Name: crm.localhost", "ping": "Passed",
		}
	if woo_report.exists():
		woo = json.loads(woo_report.read_text())
		status["real_woocommerce_background_delivery"] = {
			"status": woo["status"], "wordpress_order_id": woo["wordpress_order_id"],
			"crm_order": woo["crm_evidence"]["order"]["name"],
			"payment": woo["crm_evidence"]["payments"][0]["name"],
			"transport": woo["delivery_transport"], "checks": woo["checks"],
			"payment_note": woo["payment_note"], "cron_note": woo["cron_note"],
		}
		status["unattended_cron_soak_test"] = {"status": "Not Tested", "reason": woo["cron_note"]}
	cron_report = docs / "test_results_wp_cron.json"
	if cron_report.exists():
		cron = json.loads(cron_report.read_text())
		status["automatic_wp_cron_functional_test"] = {
			"status": cron["status"], "wordpress_order_id": cron.get("wordpress_order_id"),
			"crm_order": cron.get("crm_order"), "crm_payment": cron.get("crm_payment"),
			"elapsed_seconds": cron.get("elapsed_seconds"), "manual_actions_executed": False,
			"direct_wp_cron_requests": False, "method": cron["method"], "limit": cron["limit"],
		}
		status["unattended_cron_soak_test"] = {
			"status": "Not Tested", "reason": "Short natural WP-Cron functional test passed; multi-hour/day and no-traffic operation were not tested",
		}
	(docs / "IMPLEMENTATION_STATUS.json").write_text(json.dumps(status, indent=2, default=str) + "\n")
	return {"evidence": str(docs / "IMPLEMENTATION_STATUS.json"), "test_suites": suites}
