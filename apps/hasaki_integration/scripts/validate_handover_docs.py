"""Validate generated Markdown structure and its coverage of source/test evidence."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
NAMES = (
	"IMPLEMENTATION_REPORT.md", "DATA_DICTIONARY.md", "API_CONTRACT.md",
	"TEST_REPORT.md", "DEMO_GUIDE.md", "HANDOVER.md",
)


def main():
	json_count, link_count = 0, 0
	for name in NAMES:
		path = DOCS / name
		text = path.read_text(encoding="utf-8")
		assert text.startswith("# ") and "\x00" not in text and "\\u005c" not in text, name
		assert len(re.findall(r"^```", text, re.M)) % 2 == 0, f"Unbalanced code fences: {name}"
		for block in re.findall(r"```json\n(.*?)\n```", text, re.S):
			value = json.loads(block)
			json_count += 1
			if name == "API_CONTRACT.md" and isinstance(value.get("message"), str):
				assert "\n" in value["message"], "Lead message sample must contain an actual JSON-escaped newline"
		for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
			if target.startswith(("http://", "https://", "#")):
				continue
			assert (path.parent / target.split("#")[0]).exists(), f"Broken relative link: {name}: {target}"
			link_count += 1
	methods = []
	for suite in ("lead", "woocommerce", "schema"):
		data = json.loads((DOCS / f"test_results_{suite}.json").read_text())
		assert data["passed"] and all(row["status"] == "Passed" for row in data["results"])
		methods.extend(row["test"].split(".")[-1] for row in data["results"])
	tests = (DOCS / "TEST_REPORT.md").read_text(encoding="utf-8")
	assert len(methods) == 37 and len(re.findall(r"^### TC\d{2} ", tests, re.M)) == 37
	assert all(tests.count("### TC" + f"{idx:02d}") == 1 for idx in range(1, 38))
	assert all(method in tests for method in methods)
	schemas = json.loads((DOCS / "DATA_DICTIONARY.json").read_text())["doctypes"]
	dictionary = (DOCS / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
	for schema in schemas:
		section = dictionary.split("### " + schema["name"] + "\n", 1)[1].split("\n### ", 1)[0]
		assert all("`" + f["fieldname"] + "`" in section for f in schema["fields"])
	report = {"markdown_files": len(NAMES), "json_examples": json_count,
		"valid_relative_links": link_count, "test_cases": len(methods), "schema_fields": sum(len(s["fields"]) for s in schemas),
		"status": "Passed"}
	(DOCS / "documentation_validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
	print(json.dumps(report))


if __name__ == "__main__":
	main()
