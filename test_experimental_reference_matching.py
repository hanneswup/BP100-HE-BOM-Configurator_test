import unittest

import pandas as pd

from experimental_reference_matching import attach_historical_power, connection_code, machine_tree_item_codes, propose_matched


class ExperimentalReferenceMatchingTests(unittest.TestCase):
    def test_requires_connection_and_power_and_does_not_fallback(self):
        records = [
            {'sheet': 'A', 'codes': frozenset({'FBCA0001', 'FBCA0207'}), 'power_proxy': '5.05 kW', 'parts': {'right': 1}},
            {'sheet': 'B', 'codes': frozenset({'FBCA0001', 'FBCA0207'}), 'power_proxy': '3.05 kW', 'parts': {'wrong': 1}},
            {'sheet': 'C', 'codes': frozenset({'FBCA0001', 'FBCA0202'}), 'power_proxy': '5.05 kW', 'parts': {'other': 1}},
        ]
        result, refs = propose_matched({'FBCA0001', 'FBCA0207'}, '5.05 kW', records, {})
        self.assertEqual([r['Item code'] for r in result], ['right'])
        self.assertEqual(refs[0][1]['sheet'], 'A')
        self.assertEqual(propose_matched({'FBCA0001', 'FBCA0207'}, 'unknown', records, {}), ([], []))
        self.assertEqual(propose_matched({'FBCA0001', 'FBCA0207'}, '3.05 kW', records[:1], {}), ([], []))

    def test_ambiguous_connection_and_power_are_not_inferred(self):
        self.assertIsNone(connection_code({'FBCA0001', 'FBCA0207', 'FBCA0208'}))
        rows = [{'sheet': 'A'}, {'sheet': 'B'}]
        headers = pd.DataFrame([{'Production Sheet': 'A', 'Machine Code Description': 'BP 3,05KW'},
                                {'Production Sheet': 'A', 'Machine Code Description': 'BP 5050W'},
                                {'Production Sheet': 'B', 'Machine Code Description': 'BP 3050W'}])
        result = attach_historical_power(rows, headers)
        self.assertIsNone(result[0]['power_proxy'])
        self.assertEqual(result[1]['power_proxy'], '3.05 kW')

    def test_source_tree_includes_deep_levels_but_rejects_ambiguous_roots(self):
        frame = pd.DataFrame([{'Level': '0', 'Item Code': 'M'}, {'Level': '1', 'Item Code': 'A'},
                              {'Level': ' . 2', 'Item Code': 'B'}, {'Level': '0', 'Item Code': 'N'},
                              {'Level': '1', 'Item Code': 'C'}])
        self.assertEqual(machine_tree_item_codes(frame, 'M'), {'A', 'B'})
        self.assertIsNone(machine_tree_item_codes(pd.concat([frame, frame], ignore_index=True), 'M'))
        self.assertIsNone(machine_tree_item_codes(frame, None))


if __name__ == '__main__':
    unittest.main()
