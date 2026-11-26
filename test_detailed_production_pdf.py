import unittest
from io import BytesIO

from pypdf import PdfReader

from detailed_production_pdf import make_detailed_production_pdf


class DetailedProductionPDFTests(unittest.TestCase):
    def test_proposal_includes_all_items_notes_and_references_across_pages(self):
        components = [{'Item code': f'P{i:04d}', 'Description': f'Example component {i}',
                       'Suggested quantity': i + 1, 'Observed in': 3, 'References': 5,
                       'Review alert': 'CHECK', 'Machine BOM source evidence': 'Found in historical machine BOM'} for i in range(100)]
        sheet = {'customer': 'Test Customer', 'notes': 'Special request ADD item 123', 'variant': 'BP 100 HSE'}
        config = {'variant': 'FBCA0001', 'options': ['FBCA1007'],
                  'additional_details_not_used_in_bom': {'notes': sheet['notes'], 'control_panel_language': 'Italian'}}
        refs = [(0.75, {'sheet': '12/26', 'orders': {'ORDER1'}})]
        candidates = [{'code': 'TECH1', 'description': 'Example machine', 'sheets': ['12/26']}]
        pdf = make_detailed_production_pdf(sheet, config, candidates, components, refs)
        pages = PdfReader(BytesIO(pdf)).pages
        extracted = ' '.join(page.extract_text() or '' for page in pages)
        self.assertGreater(len(pages), 3)
        for value in ('NOT FOR PRODUCTION', 'Test Customer', 'Special request ADD item 123',
                      'TECH1', '12/26', 'ORDER1', 'P0000', 'P0099', 'FBCA1007', 'Found in historical machine BOM'):
            self.assertIn(value, extracted)
        self.assertIn('not an approved technical code', extracted)

    def test_no_candidate_is_explicit(self):
        pdf = make_detailed_production_pdf({}, {}, [], [], [])
        extracted = ' '.join(page.extract_text() or '' for page in PdfReader(BytesIO(pdf)).pages)
        self.assertIn('No usable historical references', extracted)
        self.assertIn('No component suggestions are available', extracted)
        self.assertIn('No candidate found or inputs incomplete', extracted)


if __name__ == '__main__':
    unittest.main()
