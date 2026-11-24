"""Check actual WooCommerce deliveries against persisted CRM records."""

import json
from pathlib import Path

from test_existing_wordpress import inspect_crm

ROOT = Path(__file__).resolve().parents[1]


def main():
	update = json.loads((ROOT / "docs" / "test_results_woo_native_update.json").read_text(encoding="utf-8"))
	replay = json.loads((ROOT / "docs" / "test_results_woo_native_replay.json").read_text(encoding="utf-8"))
	order_id = update["order_id"]
	result = inspect_crm(external_order_id=str(order_id))
	assert result["order_count"] == 1
	order = result["order"]
	assert order["status"] == "Processing" and order["payment_status"] == "Paid"
	assert order["integration_key"] == f"woo:hasaki-local:{order_id}"
	assert not order["customer"] and order["guest_full_name"] == "A4.8 WP TEST Guest"
	assert len(order["items"]) == 1 and order["items"][0]["product"]
	assert [row["status"] for row in order["status_history"]] == ["Pending", "Processing"]
	assert len(result["payments"]) == 1 and result["payments"][0]["status"] == "Paid"
	assert float(result["payments"][0]["amount"]) == float(update["amount"])
	assert result["payments"][0]["payment_integration_key"] == f"woo:hasaki-local:{order_id}:payment"
	assert all(row["http_status"] == 200 and row["result"]["ok"] for row in replay["deliveries"])
	report = {"status": "Passed", "website": "http://localhost:8080/shopdongho/", "wordpress_order_id": order_id,
		"delivery_transport": "Native WC_Webhook / WordPress HTTP API; scoped Action Scheduler actions executed",
		"checks": ["Native signed webhook creates/reuses one CRM order", "Existing SKU resolves to CRM Product",
			"Unmatched guest does not create Contact", "Native update records Processing and status history",
			"Confirmed test date_paid_gmt creates one Payment", "Native replay creates no second Order or Payment"],
		"initial_out_of_order_case": "The initial update-before-create delivery returned 409; after the native create succeeded, both topics were redelivered successfully.",
		"payment_note": "Synthetic local test confirmation; no external gateway charge or real payment performed.",
		"cron_note": "Executed only scheduled actions for this test order. Unattended WP-Cron operation is not separately soak-tested.",
		"crm_evidence": result}
	(ROOT / "docs" / "test_results_woocommerce_e2e.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(json.dumps({"status": "Passed", "order": order["name"], "payment": result["payments"][0]["name"]}))


if __name__ == "__main__":
	main()
