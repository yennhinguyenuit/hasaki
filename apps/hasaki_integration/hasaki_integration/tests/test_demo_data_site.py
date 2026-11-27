"""Live ORM tests for an ALREADY provisioned isolated site with shared masters.

Never run on crm.localhost. This suite does not create or restore master data.
"""
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from hasaki_integration import seed_demo_data as seeder


class IsolatedSiteTests(unittest.TestCase):
    def setUp(self):
        frappe.db.savepoint('demo_site_test')

    def tearDown(self):
        frappe.db.rollback(save_point='demo_site_test')

    def test_full_import_reconcile_repeat_and_preserve_edit(self):
        before = {dt: frappe.db.count(dt) for dt in ('Contact', 'CRM Product', 'HSK Order', 'HSK Payment', 'HSK Integration Event')}
        self.assertEqual(seeder.seed()['state'], 'imported')
        self.assertTrue(seeder.reconcile()['matches_frozen_dataset'])
        self.assertEqual(frappe.db.count('HSK Order'), before['HSK Order'] + 1200)
        self.assertEqual(frappe.db.count('HSK Payment'), before['HSK Payment'] + 1200)
        self.assertEqual(seeder.seed()['state'], 'already_imported')
        key = seeder.load()['orders'][0]['integration_key']
        doc = frappe.get_doc('HSK Order', frappe.db.get_value('HSK Order', {'integration_key': key}, 'name'))
        doc.status = 'Cancelled'
        doc.save()
        seeder.seed()
        doc.reload()
        self.assertEqual(doc.status, 'Cancelled')
        for dt in ('Contact', 'CRM Product', 'HSK Integration Event'):
            self.assertEqual(frappe.db.count(dt), before[dt])

    def test_insert_failure_rolls_back(self):
        before = {dt: frappe.db.count(dt) for dt in seeder.TARGETS}
        original = frappe.get_doc
        def fail_on_payment(*args, **kwargs):
            if args and isinstance(args[0], dict) and args[0].get('doctype') == 'HSK Payment':
                raise RuntimeError('isolated test failure')
            return original(*args, **kwargs)
        with patch.object(frappe, 'get_doc', side_effect=fail_on_payment):
            with self.assertRaisesRegex(RuntimeError, 'isolated test failure'):
                seeder.seed()
        for dt, count in before.items():
            self.assertEqual(frappe.db.count(dt), count)
        self.assertIsNone(frappe.db.get_global(seeder.MARKER))


def run():
    if frappe.local.site == 'crm.localhost' or frappe.conf.get('hasaki_demo_test_site') != 1:
        raise ValueError('Use an isolated test site explicitly marked hasaki_demo_test_site=1')
    if frappe.conf.get('hasaki_enable_demo_data') != 1:
        raise ValueError('Enable demo data only on the isolated test site')
    if frappe.db.get_global(seeder.MARKER):
        raise ValueError('Requires a test site with no existing demo dataset marker')
    frappe.set_user('Administrator')
    seeder.dry_run()
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IsolatedSiteTests))
    report = {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'site': frappe.local.site, 'output': output.getvalue()}
    path = Path(frappe.get_app_path('hasaki_integration')).parent / 'docs' / 'demo_isolated_site_results.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if not result.wasSuccessful():
        raise AssertionError(report)
    return report
