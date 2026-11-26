import unittest
from xml.etree import ElementTree as ET

import pandas as pd

from bom_xml import engineering_tree_xml, historical_candidate_xml, historical_reference_xml, technical_preview_xml


class BOMXMLTest(unittest.TestCase):
    def test_technical_sources_preserve_signed_quantities_and_parent(self):
        summary = pd.DataFrame([{'Item code': 'A', 'Net quantity': '0', 'Review': 'verify'}])
        contributions = pd.DataFrame([
            {'Source role': 'Machine', 'Source BOM': 'M1', 'Item code': 'A', 'Description': 'A & B', 'Source quantity': '1', 'Parent code': 'M1'},
            {'Source role': 'Option', 'Source BOM': 'O1', 'Item code': 'A', 'Description': 'A & B', 'Source quantity': '-1', 'Parent code': 'O1'},
        ])
        root = ET.fromstring(technical_preview_xml({'variant': 'FBCA0001', 'options': []}, summary, contributions))
        self.assertEqual(root.attrib['status'], 'unverified')
        self.assertEqual([x.text for x in root.findall('./SourceBOMs/SourceBOM/Component/SignedQuantity')], ['1', '-1'])
        self.assertEqual(root.find('./SourceBOMs/SourceBOM/Component/Description').text, 'A & B')
        self.assertEqual(root.find('./NetComponents/Component/NetQuantity').text, '0')

    def test_candidate_states_flat_unknown_and_lists_references(self):
        rows = pd.DataFrame([{'Item code': '123', 'Suggested quantity': 2, 'Review alert': 'CHECK', 'Machine BOM source evidence': 'Found in historical machine BOM'}])
        refs = [(0.75, {'sheet': '4/26', 'orders': {'P1', 'P2'}})]
        root = ET.fromstring(historical_candidate_xml({'variant': 'FBCA0000', 'technical_machine_candidate_unverified': 'M1'}, rows, refs))
        self.assertEqual(root.find('CandidateComponents').attrib['hierarchy'], 'flat_unknown')
        self.assertEqual(root.find('./CandidateComponents/Component/ReviewAlert').text, 'CHECK')
        self.assertEqual(root.find('./CandidateComponents/Component/MachineBOMSourceEvidence').text, 'Found in historical machine BOM')
        self.assertEqual(root.find('./OrderConfiguration/TechnicalMachineCandidateUnverified').text, 'M1')
        self.assertEqual(root.find('./HistoricalReferences/Reference/ProductionSheet').text, '4/26')

    def test_reference_keeps_duplicate_lines_and_missing_orders(self):
        rows = pd.DataFrame([{'Production Order': 'P1', 'Item Code': 'A', 'Quantity': 1},
                             {'Production Order': 'P1', 'Item Code': 'A', 'Quantity': -1}])
        root = ET.fromstring(historical_reference_xml('1/26', rows, ['P2']))
        self.assertEqual(root.find('./MissingProductionBOMOrders/ProductionOrder').text, 'P2')
        self.assertEqual([x.text for x in root.findall('./ProductionOrders/ProductionOrder/Component/Quantity')], ['1', '-1'])

    def test_engineering_tree_preserves_nested_levels_and_flags_bad_parent(self):
        rows = pd.DataFrame([
            {'Level': '0', 'Item Code': 'M'},
            {'Level': '1', 'Father Code': 'M', 'Item Code': 'A', 'Quantity': '1'},
            {'Level': ' . 2', 'Father Code': 'A', 'Item Code': 'B', 'Quantity': '-2'},
            {'Level': ' . . 3', 'Father Code': 'wrong', 'Item Code': 'C', 'Quantity': '0.5'},
            {'Level': '1', 'Father Code': 'M', 'Item Code': 'D', 'Quantity': '3'},
        ])
        root = ET.fromstring(engineering_tree_xml(rows, ['M']))
        node = root.find('./SourceBOMs/SourceBOM/Component/Component')
        self.assertEqual(node.find('ItemCode').text, 'B')
        self.assertEqual(node.find('Quantity').text, '-2')
        self.assertEqual(node.find('Component').attrib['parentCheck'], 'mismatch_or_missing')
        self.assertEqual(len(root.findall('./SourceBOMs/SourceBOM/Component')), 2)

    def test_invalid_level_jump_is_rejected(self):
        rows = pd.DataFrame([{'Level': '0', 'Item Code': 'M'}, {'Level': ' . 2', 'Item Code': 'X'}])
        with self.assertRaisesRegex(ValueError, 'invalid or missing level'):
            engineering_tree_xml(rows, ['M'])


if __name__ == '__main__':
    unittest.main()
