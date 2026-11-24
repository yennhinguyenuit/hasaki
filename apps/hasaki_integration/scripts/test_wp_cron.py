"""Observe natural WP-Cron delivery using normal page visits, without running actions."""

import json
import re
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from test_existing_wordpress import inspect_crm

ROOT = Path(__file__).resolve().parents[1]
PHP = "D:/baitap/php/php.exe"
WP = "D:/baitap/htdocs/shopdongho"
HOME = "http://localhost:8080/shopdongho/"
ACCESS_LOG = Path("D:/baitap/apache/logs/access.log")
REPORT = ROOT / "docs" / "test_results_wp_cron.json"


def run_php(name, *args):
	completed = subprocess.run([PHP, str(ROOT / "scripts" / name), WP, *map(str, args)],
		capture_output=True, text=True, encoding="utf-8", check=True)
	return json.loads(completed.stdout)


def main():
	started = time.monotonic()
	log_offset = ACCESS_LOG.stat().st_size
	report = {
		"status": "Running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
		"method": "Only normal homepage HTTP GET visits; WooCommerce schedules webhooks at shutdown and native WP-Cron runs the queue",
		"manual_actions_executed": False, "direct_wp_cron_requests": False,
		"cron_before": run_php("inspect_wp_cron.php"), "phases": [],
		"master_counts_before": inspect_crm()["master_counts"],
	}
	def save():
		REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
	def observe(order_id, expected_status):
		phase = {"expected_order_status": expected_status, "observations": []}
		deadline = time.monotonic() + 180
		while time.monotonic() < deadline:
			try:
				with urllib.request.urlopen(HOME, timeout=25) as response:
					page_status = response.status
			except Exception as exc:
				page_status = type(exc).__name__
			time.sleep(3)
			crm = inspect_crm(external_order_id=str(order_id))
			cron = run_php("inspect_wp_cron.php", order_id)
			phase["observations"].append({
				"elapsed_seconds": round(time.monotonic() - started, 2), "homepage_http_status": page_status,
				"order_count": crm.get("order_count"),
				"order_status": crm.get("order", {}).get("status"),
				"payment_status": crm.get("order", {}).get("payment_status"), "actions": cron.get("actions", []),
			})
			phase["last_crm_evidence"], phase["last_cron_evidence"] = crm, cron
			actions = cron.get("actions", [])
			if crm.get("order", {}).get("status") == expected_status and actions and all(a["status"] == "complete" for a in actions):
				if expected_status != "Processing" or (crm["order"]["payment_status"] == "Paid" and len(crm.get("payments", [])) == 1):
					phase["status"] = "Passed"
					return phase
			save()
			time.sleep(5)
		phase["status"] = "Failed"
		return phase
	try:
		created = run_php("test_existing_woocommerce.php", "cron-create")
		report["wordpress_order_id"] = order_id = created["order_id"]
		report["create_command_result"] = created
		save()
		create_phase = observe(order_id, "Pending")
		report["phases"].append(create_phase)
		if create_phase["status"] != "Passed":
			raise RuntimeError("Natural background create delivery did not complete within 180 seconds")
		report["update_command_result"] = run_php("test_existing_woocommerce.php", "cron-update", order_id)
		update_phase = observe(order_id, "Processing")
		report["phases"].append(update_phase)
		if update_phase["status"] != "Passed":
			raise RuntimeError("Natural background update delivery did not complete within 180 seconds")
		latest = update_phase["last_crm_evidence"]
		assert latest["order_count"] == 1 and len(latest["payments"]) == 1
		assert all(event["status"] == "Processed" for event in latest["order_events"]), latest["order_events"]
		assert report["master_counts_before"] == latest["master_counts"]
		report["status"] = "Passed"
		report["crm_order"] = latest["order"]["name"]
		report["crm_payment"] = latest["payments"][0]["name"]
	except Exception as exc:
		report["status"] = "Failed"
		report["failure"] = f"{type(exc).__name__}: {exc}"
	finally:
		report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
		report["elapsed_seconds"] = round(time.monotonic() - started, 2)
		with ACCESS_LOG.open("rb") as handle:
			handle.seek(log_offset)
			lines = handle.read().decode("utf-8", errors="replace").splitlines()
		report["automatic_loopback_requests"] = []
		for line in lines:
			match = re.search(r'\[([^\]]+)\] "(GET|POST) (/shopdongho/(?:wp-cron\.php|wp-admin/admin-ajax\.php))[^ ]* HTTP/[^\"]+" (\d+)', line)
			if match:
				report["automatic_loopback_requests"].append({"time": match[1], "method": match[2], "path": match[3], "http_status": int(match[4])})
		report["limit"] = "Short functional observation; not a long-running soak test or proof of operation without page traffic/system cron"
		save()
	print(json.dumps({key: report.get(key) for key in ("status", "wordpress_order_id", "crm_order", "crm_payment", "elapsed_seconds", "failure")}))
	if report["status"] != "Passed":
		raise SystemExit(1)


if __name__ == "__main__":
	main()
