import types
import unittest
from unittest.mock import patch

from checklist_codes import extract_rev08_connection, extract_rev08_form_values


class Ref:
    def __init__(self, number, state, on_state, rect=(440, 74, 452, 86)):
        self.idnum = number
        self.widget = {'/AS': state, '/AP': {'/N': {'/Off': {}, on_state: {}}}, '/Rect': rect}

    def get_object(self):
        return self.widget


class Page(dict):
    pass


class Search:
    def __init__(self, code):
        self.code = code
        self.calls = 0

    def get_next(self):
        self.calls += 1
        return (1, 1) if self.calls == 1 and self.code == 'FBCA0213' else None


class TextPage:
    def search(self, code, match_case=True):
        return Search(code)

    def count_rects(self, *args):
        return 1

    def get_rect(self, index):
        return (38, 77, 75, 83)


class ChecklistRev08Tests(unittest.TestCase):
    def test_drain_fields_are_mapped_only_when_selected_consistently(self):
        kids = [Ref(1, '/Off', '/Scelta1'), Ref(2, '/Scelta2', '/Scelta2')]
        fields = {'Drain position': {'/FT': '/Btn', '/V': '/Scelta2', '/Kids': kids}}
        self.assertEqual(extract_rev08_form_values(fields, 'BP 100 HE Rev. 08')['drain_position'], 'To the floor')
        fields['Drain position']['/V'] = '/Scelta1'
        self.assertNotIn('drain_position', extract_rev08_form_values(fields, 'BP 100 HE Rev. 08'))

    def test_connection_uses_location_not_radio_index(self):
        kids = [Ref(i, '/Off', f'/{i}') for i in range(24)]
        kids[23].widget['/AS'] = '/23'
        fields = {'Electrical Connection': {'/FT': '/Btn', '/V': '/23', '/Kids': kids}}
        reader = types.SimpleNamespace(pages=[Page({'/Annots': [kids[23]]})])
        fake_doc = [types.SimpleNamespace(get_textpage=lambda: TextPage())]
        fake_pdfium = types.SimpleNamespace(PdfDocument=lambda data: fake_doc)
        with patch.dict('sys.modules', {'pypdfium2': fake_pdfium}):
            self.assertEqual(extract_rev08_connection(reader, fields, b'pdf', 'BP 100 HE Rev. 08'), 'FBCA0213')
            fields['Electrical Connection']['/V'] = '/33'
            self.assertIsNone(extract_rev08_connection(reader, fields, b'pdf', 'BP 100 HE Rev. 08'))


if __name__ == '__main__':
    unittest.main()
