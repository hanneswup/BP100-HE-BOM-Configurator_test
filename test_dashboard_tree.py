import unittest

import pandas as pd

from bom_xml import engineering_tree_xml
from dashboard_tree import render_dashboard_tree, summarize_source_tree


class DashboardTreeTests(unittest.TestCase):
    def test_user_and_historical_values_are_html_escaped(self):
        html = render_dashboard_tree({'notes': '<script>alert(1)</script>', 'options': ['<img src=x>']},
            [{'code': '<CODE>', 'description': '<b>bad</b>', 'sheets': []}],
            candidate_rows=[{'Item code': '<bad>', 'Description': '<script>x</script>', 'Suggested quantity': 1}])
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=x>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('Flat historical component suggestions - assembly hierarchy is unknown', html)

    def test_source_hierarchy_and_parent_warning_are_preserved(self):
        frame = pd.DataFrame([{'Level': '0', 'Item Code': 'M'},
                              {'Level': '1', 'Father Code': 'M', 'Item Code': 'A', 'Quantity': 1},
                              {'Level': ' . 2', 'Father Code': 'other', 'Item Code': 'B', 'Quantity': -2}])
        xml = engineering_tree_xml(frame, ['M'])
        html = render_dashboard_tree({}, [], source_xml=xml)
        self.assertIn('Historical source BOM M', html)
        self.assertIn('A |', html)
        self.assertIn('B |', html)
        self.assertIn('source parent mismatch: review', html)
        self.assertIn('source qty: -2', html)
        self.assertIn('Father / parent code', html)
        self.assertIn('Child / item code', html)
        self.assertIn('Children / subcomponents (1)', html)
        self.assertEqual(summarize_source_tree(xml), {'components': 2, 'max_level': 2, 'parent_mismatches': 1})

    def test_repeated_child_occurrences_remain_separate(self):
        frame = pd.DataFrame([{'Level': '0', 'Item Code': 'M'},
                              {'Level': '1', 'Father Code': 'M', 'Item Code': 'A'},
                              {'Level': ' . 2', 'Father Code': 'A', 'Item Code': 'X'},
                              {'Level': '1', 'Father Code': 'M', 'Item Code': 'B'},
                              {'Level': ' . 2', 'Father Code': 'B', 'Item Code': 'X'}])
        xml = engineering_tree_xml(frame, ['M'])
        html = render_dashboard_tree({}, [], source_xml=xml)
        self.assertEqual(html.count('Level 2 | X |'), 2)
        self.assertEqual(summarize_source_tree(xml)['components'], 4)

    def test_unknown_inputs_are_not_claimed_as_absent_or_approved(self):
        html = render_dashboard_tree({}, [])
        self.assertIn('None entered - absence not verified', html)
        self.assertIn('Not calculated - complete the required fields first', html)
        self.assertIn('unverified draft', html)


if __name__ == '__main__':
    unittest.main()
