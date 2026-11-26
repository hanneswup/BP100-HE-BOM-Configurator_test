import json
import unittest
from unittest.mock import patch

from local_note_llm import analyse_note


class Response:
    def __init__(self, items):
        self.body = json.dumps({'message': {'content': json.dumps({'items': items})}}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit):
        return self.body[:limit]


class LocalNoteLLMTests(unittest.TestCase):
    @patch('local_note_llm.build_opener')
    def test_requires_exact_evidence_for_quantity_and_item(self, opener):
        opener.return_value.open.return_value = Response([
            {'item_code': '99M11233190', 'quantity': '1', 'exact_excerpt': '1 X 99M11233190'},
            {'item_code': 'BAD', 'quantity': '2', 'exact_excerpt': '2 X BAD'},
        ])
        result = analyse_note('AGGIUNGERE: 1 X 99M11233190', 'llama3.2:1b')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['Possible item'], '99M11233190')
        self.assertEqual(opener.return_value.open.call_args.args[0].full_url, 'http://127.0.0.1:11434/api/chat')

    @patch('local_note_llm.build_opener')
    def test_does_not_send_unapproved_model_or_oversized_note(self, opener):
        with self.assertRaises(ValueError):
            analyse_note('test', 'model:cloud')
        with self.assertRaises(ValueError):
            analyse_note('a' * 6001, 'local-model')
        opener.assert_not_called()


if __name__ == '__main__':
    unittest.main()
