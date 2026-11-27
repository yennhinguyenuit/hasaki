"""Read-only site audit; exports business IDs, never contact personal details."""
import json
from pathlib import Path

import frappe

from hasaki_integration.a48_preflight import _describe_doctype

DOCTYPES = ('Contact', 'Address', 'User', 'CRM Lead', 'CRM Deal', 'CRM Product',
            'CRM Lead Source', 'HSK Product Category', 'HSK Order', 'HSK Order Item',
            'HSK Order Status History', 'HSK Payment', 'HSK Integration Event')


def inspect_site():
    result = {
        'site': frappe.local.site,
        'apps': frappe.get_installed_apps(),
        'metadata': [_describe_doctype(dt) for dt in DOCTYPES],
        'counts': {dt: frappe.db.count(dt) for dt in DOCTYPES if frappe.db.exists('DocType', dt)},
        'doc_events': frappe.get_hooks('doc_events'),
        'override_doctype_class': frappe.get_hooks('override_doctype_class'),
        'notifications': frappe.get_all('Notification', filters={'enabled': 1},
                                        fields=['name', 'document_type', 'channel', 'event']),
        'webhooks': frappe.get_all('Webhook', filters={'enabled': 1},
                                  fields=['name', 'webhook_doctype', 'webhook_docevent']),
    }
    root = Path(frappe.get_app_path('hasaki_integration')).parent
    (root / 'docs' / 'demo_site_audit.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return result


def export_master():
    """Call only after metadata inspection confirms these fields."""
    result = {
        'contacts': frappe.get_all('Contact', fields=['custom_customer_id'], order_by='custom_customer_id'),
        'products': frappe.get_all('CRM Product', fields=[
            'product_code', 'product_name', 'standard_rate', 'custom_cost_price', 'custom_category',
            'custom_brand', 'custom_product_category', 'disabled'],
            order_by='product_code'),
        'categories': frappe.get_all('HSK Product Category', fields=['category_id', 'category_name'], order_by='category_id'),
    }
    root = Path(frappe.get_app_path('hasaki_integration')) / 'demo_data' / 'v1'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'master_snapshot.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return {'contacts': len(result['contacts']), 'products': len(result['products'])}


def export_dry_run():
    from hasaki_integration.seed_demo_data import dry_run
    result = dry_run()
    root = Path(frappe.get_app_path('hasaki_integration')).parent
    (root / 'docs' / 'demo_dry_run.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def final_state():
    from hasaki_integration.seed_demo_data import status
    result = {'site': frappe.local.site, 'dataset': status(),
              'counts': {dt: frappe.db.count(dt) for dt in DOCTYPES}}
    root = Path(frappe.get_app_path('hasaki_integration')).parent
    (root / 'docs' / 'demo_final_site_state.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result
