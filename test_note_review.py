import unittest

from note_review import item_mentions


class NoteReviewTests(unittest.TestCase):
    def test_finds_literal_mention_without_asserting_action(self):
        mentions = item_mentions('AGGIUNGERE:\n1 X 99M11233190')
        self.assertEqual(len(mentions), 1)
        self.assertEqual(mentions[0]['item'], '99M11233190')
        self.assertEqual(mentions[0]['quantity_text'], '1')
        self.assertEqual(mentions[0]['source'], '1 X 99M11233190')

    def test_no_mention_does_not_mean_note_is_safe(self):
        self.assertEqual(item_mentions('No pump for limescale dosing'), [])
        self.assertEqual(item_mentions(''), [])


if __name__ == '__main__':
    unittest.main()
