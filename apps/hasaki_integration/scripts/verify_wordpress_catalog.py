"""Read-only SKU compatibility check; never create or update product masters."""

import json
from pathlib import Path

from test_existing_wordpress import inspect_crm

ROOT = Path(__file__).resolve().parents[1]


def main():
	wp = json.loads((ROOT / "docs" / "wordpress_site_inventory.json").read_text(encoding="utf-8"))
	crm = inspect_crm(include_product_codes=True)
	wp_codes = wp["product_skus"]
	crm_codes = crm["product_codes"]
	missing = sorted(set(wp_codes) - set(crm_codes))
	report = {
		"status": "Passed" if not missing and len(wp_codes) == len(set(wp_codes)) else "Failed",
		"wordpress_published_products": int(wp["products"]["publish"]),
		"wordpress_sku_count": len(wp_codes), "crm_product_count": len(crm_codes),
		"wordpress_skus_missing_in_crm": missing,
		"duplicate_wordpress_skus": len(wp_codes) - len(set(wp_codes)),
		"products_created_or_modified": False,
	}
	(ROOT / "docs" / "wordpress_catalog_compatibility.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
	print(json.dumps(report))
	assert report["status"] == "Passed", "Catalog mismatches require review; no masters were changed"


if __name__ == "__main__":
	main()
