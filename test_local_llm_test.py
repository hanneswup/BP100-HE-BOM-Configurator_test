import json
import unittest
from unittest.mock import patch

from local_llm_test import ENDPOINT, analyse_text


class Response:
    def __init__(self, result):
        self.body = json.dumps({'message': {'content': json.dumps(result)}}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, limit):
        return self.body[:limit]


class LocalLLMTest(unittest.TestCase):
    @patch('local_llm_test.build_opener')
    def test_only_exact_document_quotes_are_returned(self, build_opener):
        build_opener.return_value.open.return_value = Response({
            'power': {'value': '3.05 kW', 'evidence': 'Selected power: 3.05 kW'},
            'control_panel': {'value': 'LCD', 'evidence': 'LCD selected'},
        })
        suggestions, truncated = analyse_text('Selected power: 3.05 kW', 'approved-model')
        self.assertFalse(truncated)
        self.assertEqual([row['Field'] for row in suggestions], ['power'])
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, ENDPOINT)

    @patch('local_llm_test.build_opener')
    def test_rejects_cloud_and_invalid_model_names_before_request(self, build_opener):
        for name in ('model:cloud', 'http://example.com/model', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                analyse_text('example', name)
        build_opener.assert_not_called()

    @patch('local_llm_test.build_opener')
    def test_blank_text_is_not_sent(self, build_opener):
        with self.assertRaises(ValueError):
            analyse_text(' ', 'approved-model')
        build_opener.assert_not_called()


if __name__ == '__main__':
    unittest.main()
