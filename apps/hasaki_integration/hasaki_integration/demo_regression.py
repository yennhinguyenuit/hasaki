"""Run unchanged A4.8 cases; clean only records created by this run via ORM."""
import io
import json
import secrets
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe
import requests
from frappe.utils.password import get_decrypted_password

from hasaki_integration.demo_deployment import ROOT, _snapshot, _write
from hasaki_integration.validate_demo_data import require

OWNED_TYPES = ('HSK Integration Event', 'HSK Payment', 'HSK Order', 'CRM Lead')


def run():
    from hasaki_integration.tests import test_integration_http as http
    from hasaki_integration.tests.test_schema import SchemaTests
    from frappe.model.delete_doc import delete_dynamic_links

    require(frappe.local.site == 'crm.localhost', 'Existing suite HTTP targets crm.localhost')
    user = http.LeadHTTPTests.user
    require(frappe.db.get_value('User', user, 'api_key') and
            get_decrypted_password('User', user, 'api_secret', raise_exception=False), 'Existing credentials required')
    before = _snapshot()
    _write('regression_before', before)
    # Names stay in memory, not in distributable evidence.
    original_names = {dt: set(frappe.get_all(dt, pluck='name')) for dt in OWNED_TYPES}
    ancillary_types = ('Comment', 'Version', 'Deleted Document')
    ancillary = {dt: set(frappe.get_all(dt, pluck='name')) for dt in ancillary_types}
    submissions, order_ids, deliveries = set(), set(), set()
    original_post = requests.post
    results = {}
    config_path = Path(frappe.get_site_path('site_config.json'))
    original_config = config_path.read_bytes()
    original_secret = http.WooHTTPTests.secret
    cleanup = {}
    test_error = None

    def tracked_post(url, *args, **kwargs):
        if url.endswith(http.LEAD_PATH):
            payload = kwargs.get('json') or {}
            if payload.get('submission_id'):
                submissions.add(str(payload['submission_id']))
        elif url.endswith(http.ORDER_PATH):
            headers = kwargs.get('headers') or {}
            if headers.get('X-WC-Webhook-Delivery-ID'):
                deliveries.add(headers['X-WC-Webhook-Delivery-ID'])
            raw = kwargs.get('data')
            if isinstance(raw, bytes):
                payload = json.loads(raw)
                order_ids.add(str(payload['id']))
        return original_post(url, *args, **kwargs)

    try:
        with patch.object(requests, 'post', side_effect=tracked_post):
            results['lead'] = http._run(http.LeadHTTPTests, 'demo_regression_lead.json')
            config = json.loads(original_config)
            stores = config.setdefault('hasaki_woocommerce_stores', {})
            require(http.WooHTTPTests.source_url not in stores, 'Temporary regression source already configured')
            http.WooHTTPTests.secret = secrets.token_hex(32)
            stores[http.WooHTTPTests.source_url] = {'source_store': http.WooHTTPTests.source_store,
                'secret': http.WooHTTPTests.secret, 'user': http.WooHTTPTests.user}
            config_path.write_text(json.dumps(config, indent=2) + '\n')
            try:
                results['woocommerce'] = http._run(http.WooHTTPTests, 'demo_regression_woocommerce.json')
            finally:
                config_path.write_bytes(original_config)
                http.WooHTTPTests.secret = original_secret
            results['schema'] = http._run(SchemaTests, 'demo_regression_schema.json')
    except Exception as exc:
        test_error = type(exc).__name__
    finally:
        config_path.write_bytes(original_config)
        http.WooHTTPTests.secret = original_secret
        frappe.db.rollback()
        frappe.set_user('Administrator')
        owned = {dt: set(frappe.get_all(dt, pluck='name')) - original_names[dt] for dt in OWNED_TYPES}
        # Prove ownership before deleting anything. Never select by broad a48-test prefix.
        for name in owned['HSK Order']:
            doc = frappe.get_doc('HSK Order', name)
            require(doc.source_store == http.WooHTTPTests.source_store and str(doc.external_order_id) in order_ids,
                    'Unowned new Order encountered; do not delete')
        for name in owned['HSK Payment']:
            require(frappe.db.get_value('HSK Payment', name, 'order') in owned['HSK Order'], 'Unowned Payment')
        for name in owned['HSK Integration Event']:
            doc = frappe.get_doc('HSK Integration Event', name)
            require((doc.source == 'WordPress' and doc.external_object_id in submissions) or
                    (doc.source == 'WooCommerce' and doc.external_object_id in order_ids and doc.event_id in deliveries),
                    'Unowned Integration Event')
        referenced_leads = set(frappe.get_all('HSK Integration Event',
            filters={'name': ['in', list(owned['HSK Integration Event'])], 'reference_doctype': 'CRM Lead'}, pluck='reference_name'))
        require(owned['CRM Lead'] <= referenced_leads, 'Unowned CRM Lead')
        # Record actual verdicts and counts BEFORE cleanup. Cleanup never changes a verdict.
        _write('regression_verdict_before_cleanup', {'results': results, 'error': test_error,
                'new_test_records': {dt: len(names) for dt, names in owned.items()}})
        real_get_doc = frappe.get_doc
        owned_pairs = {(dt, name) for dt, names in owned.items() for name in names}
        def cleanup_get_doc(*args, **kwargs):
            doc = real_get_doc(*args, **kwargs)
            if (doc.doctype, doc.name) in owned_pairs:
                # Core-supported attribute suppresses deletion feed for temporary docs;
                # on_trash, on_change, after_delete, permissions and links still run.
                doc.no_feed_on_delete = True
            return doc
        frappe.db.savepoint('demo_regression_cleanup')
        try:
            with patch.object(frappe, 'get_doc', side_effect=cleanup_get_doc):
                for dt in OWNED_TYPES:
                    for name in sorted(owned[dt], reverse=True):
                        frappe.delete_doc(dt, name, delete_permanently=True)
                        delete_dynamic_links(dt, name)
                    cleanup[dt] = len(owned[dt])
            # Core dynamic-link cleanup removes new Comment/Version and child rows.
            for dt in OWNED_TYPES:
                require(set(frappe.get_all(dt, pluck='name')) == original_names[dt], f'Test leftovers: {dt}')
            for dt in ancillary_types:
                require(set(frappe.get_all(dt, pluck='name')) == ancillary[dt], f'Ancillary leftovers: {dt}')
            frappe.db.commit()
        except Exception:
            frappe.db.rollback(save_point='demo_regression_cleanup')
            raise
    report = {'results': results, 'tests_run': sum(r['tests_run'] for r in results.values()),
              'passed': test_error is None and len(results) == 3,
              'cleanup_counts': cleanup, 'test_records_remaining': 0,
              'config_restored_exact_bytes': config_path.read_bytes() == original_config,
              'cleanup_scope': 'Only new run-owned records; ORM hooks/links enforced; no old/demo document selected',
              'error': test_error}
    _write('regression', report)
    require(report['passed'], 'Regression failed; verdict evidence preserved, test-owned records cleaned')
    return report
