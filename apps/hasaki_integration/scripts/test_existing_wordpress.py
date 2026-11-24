"""End-to-end public WordPress form -> PHP backend -> CRM HTTP -> MariaDB."""

import http.cookiejar
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = "http://localhost:8080/shopdongho/"


class FormParser(HTMLParser):
	def __init__(self):
		super().__init__()
		self.in_form = False
		self.values = {}
		self.action = None

	def handle_starttag(self, tag, attrs):
		attrs = dict(attrs)
		if tag == "form" and attrs.get("id") == "hasaki-crm-lead-form":
			self.in_form = True
			self.action = attrs["action"]
		elif self.in_form and tag == "input" and attrs.get("type") == "hidden":
			self.values[attrs["name"]] = attrs.get("value", "")

	def handle_endtag(self, tag):
		if tag == "form":
			self.in_form = False


class NoRedirect(urllib.request.HTTPRedirectHandler):
	def redirect_request(self, req, fp, code, msg, headers, newurl):
		return None


def inspect_crm(**kwargs):
	command = [
		"docker", "exec", "-w", "/home/frappe/frappe-bench", "crm-frappe-1", "bench", "--site", "crm.localhost",
		"execute", "hasaki_integration.a48_verify.inspect_external_flow", "--kwargs", repr(kwargs),
	]
	completed = subprocess.run(command, capture_output=True, text=True, check=True, encoding="utf-8")
	return json.loads(completed.stdout.strip().splitlines()[-1])


def main():
	before = inspect_crm()
	opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())
	with opener.open(HOME, timeout=20) as response:
		html = response.read().decode("utf-8")
	parser = FormParser()
	parser.feed(html)
	assert parser.action and parser.values.get("hasaki_nonce"), "The real website must render the bridge form and nonce"
	assert "HASAKI_CRM_API_SECRET" not in html and "Authorization: token" not in html
	submission = str(uuid.uuid4())
	payload = {
		**parser.values, "submission_id": submission,
		"first_name": "A4.8 WORDPRESS TEST", "last_name": "Khách thử",
		"phone": "0900000000", "email": "a48-wordpress-e2e@example.invalid",
		"message": "Kiểm thử từ WordPress Hasaki thực tế\nNội dung tư vấn dòng thứ hai.", "consent": "1",
		"contact_website": "",
	}
	def submit(fields):
		request = urllib.request.Request(parser.action,
			data=urllib.parse.urlencode(fields).encode(), headers={"Referer": HOME}, method="POST")
		try:
			response = opener.open(request, timeout=35)
		except urllib.error.HTTPError as exc:
			response = exc
		location = response.headers.get("Location", "")
		status = response.code
		response.close()
		return {"http_status": status, "redirect": location}
	first, duplicate = submit(payload), submit(payload)
	for result in (first, duplicate):
		assert result["http_status"] == 303 and "hsk_state=sent" in result["redirect"], result
	after = inspect_crm(submission_id=submission)
	assert len(after["lead_events"]) == 1 and after["lead_events"][0]["status"] == "Processed", after
	assert after["lead"]["mobile_no"] == payload["phone"]
	assert after["lead"]["first_name"] == payload["first_name"]
	assert after["lead"]["last_name"] == payload["last_name"]
	assert after["lead"]["source"] == "Web Form"
	assert after["lead"]["email"] == payload["email"]
	assert len(after["comments"]) == 1 and "dòng thứ hai" in after["comments"][0]["content"]
	no_consent_id = str(uuid.uuid4())
	no_consent = submit({**payload, "submission_id": no_consent_id, "consent": "0"})
	assert no_consent["http_status"] == 303 and "hsk_state=error" in no_consent["redirect"], no_consent
	assert not inspect_crm(submission_id=no_consent_id)["lead_events"]
	assert before["master_counts"] == after["master_counts"]
	report = {
		"status": "Passed", "website": HOME, "runtime": "real WordPress 7.1.5 / XAMPP PHP 8.2.12",
		"checks": ["Public form and nonce rendered", "Form POST reaches WordPress PHP backend",
			"Lead stored in CRM with Unicode names and message", "Duplicate form creates only one Lead and one Comment",
			"Consent false rejected before CRM delivery", "No master records created"],
		"submission_id": submission, "first_request": first, "duplicate_request": duplicate,
		"no_consent_request": no_consent, "crm_evidence": after,
	}
	(ROOT / "docs" / "test_results_wordpress_e2e.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(json.dumps({"status": "Passed", "lead": after["lead"]["name"], "checks": len(report["checks"])}))


if __name__ == "__main__":
	main()
