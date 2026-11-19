import unittest
import pandas as pd
from bom_proposal import build_examples, grouped_split, propose


class BomProposalTests(unittest.TestCase):
    def test_excludes_incomplete_orders_and_preserves_quantity_disagreement(self):
        assoc = pd.DataFrame([('A', 'FBCA0001'), ('B', 'FBCA0001'), ('C', 'FBCA0001')], columns=['Production Sheet', 'Commercial Code'])
        links = pd.DataFrame([('A', '1'), ('B', '2'), ('C', '3'), ('C', 'missing')], columns=['Production Sheet', 'Production Order'])
        bom = pd.DataFrame([('1', 'p', 'Part', 2), ('1', 'p', 'Part', 1), ('2', 'p', 'Part', 5), ('3', 'p', 'Part', 99)], columns=['Production Order', 'Item Code', 'Item Code Description', 'Quantity'])
        rows, descriptions = build_examples(assoc, links, bom)
        self.assertEqual({r['sheet'] for r in rows}, {'A', 'B'})
        proposal, refs = propose({'FBCA0001'}, rows, descriptions)
        self.assertEqual(len(refs), 2)
        self.assertEqual(proposal[0]['Suggested quantity'], 3)
        self.assertEqual(proposal[0]['Quantity range'], '3–5')
        self.assertEqual(proposal[0]['Quantity agreement'], 1)

    def test_shared_orders_and_identical_codes_never_cross_split(self):
        rows = [dict(sheet=str(i), codes=frozenset({'FBCA0001', f'FBCA{i+200:04d}'}), orders=frozenset({str(i)}), parts={'p': 1}) for i in range(12)]
        rows[1]['orders'] = rows[0]['orders']
        rows[3]['codes'] = rows[2]['codes']
        train, test = grouped_split(rows)
        train_rows, test_rows = [rows[i] for i in train], [rows[i] for i in test]
        for a in train_rows:
            for b in test_rows:
                self.assertNotEqual(a['codes'], b['codes'])
                self.assertFalse(a['orders'] & b['orders'])


if __name__ == '__main__':
    unittest.main()
