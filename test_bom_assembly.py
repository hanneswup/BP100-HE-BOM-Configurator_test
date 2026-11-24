import unittest
import pandas as pd
from bom_assembly import build_assembly_preview, direct_bom_lines


def example():
    return pd.DataFrame([
        (0, 'MACHINE', 'Machine', None, 'No'),
        (1, '001', 'Part A', 3, 'Yes'),
        (2, 'subpart', 'Nested part', 20, 'Yes'),
        (1, '002', 'Part B', 1, 'Yes'),
        (0, 'OPTION', 'Option', None, 'No'),
        (1, '001', 'Part A', -1, 'Yes'),
        (1, '003', 'Part C', 2, 'Yes'),
    ], columns=['Level', 'Item Code', 'Item Code Description', 'Quantity', 'Item in Production Bom?'])


class TechnicalAssemblyTests(unittest.TestCase):
    def test_signed_quantities_and_source_trace(self):
        summary, details = build_assembly_preview(example(), 'MACHINE', ['OPTION'])
        self.assertEqual(dict(zip(summary['Item code'], summary['Net quantity'])), {'001': '2', '002': '1', '003': '2'})
        self.assertNotIn('subpart', set(summary['Item code']))
        self.assertEqual(details.loc[details['Item code'].eq('001'), 'Source quantity'].tolist(), ['3', '-1'])
        self.assertEqual(set(details['Source BOM']), {'MACHINE', 'OPTION'})

    def test_unmatched_negative_is_visible(self):
        frame = example()
        frame.loc[5, 'Quantity'] = -5
        summary, _ = build_assembly_preview(frame, 'MACHINE', ['OPTION'])
        row = summary[summary['Item code'].eq('001')].iloc[0]
        self.assertEqual(row['Net quantity'], '-2')
        self.assertIn('Negative', row['Review'])

    def test_duplicate_root_and_missing_quantity_are_rejected(self):
        frame = pd.concat([example(), example().iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            direct_bom_lines(frame, 'MACHINE')
        frame = example()
        frame.loc[1, 'Quantity'] = None
        with self.assertRaisesRegex(ValueError, 'quantity'):
            build_assembly_preview(frame, 'MACHINE', ['OPTION'])

    def test_zero_total_is_not_silently_dropped(self):
        frame = example()
        frame.loc[5, 'Quantity'] = -3
        summary, _ = build_assembly_preview(frame, 'MACHINE', ['OPTION'])
        row = summary[summary['Item code'].eq('001')].iloc[0]
        self.assertEqual(row['Net quantity'], '0')
        self.assertIn('Zero', row['Review'])


if __name__ == '__main__':
    unittest.main()
