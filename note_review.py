"""Find candidate item mentions in untrusted order notes for human review."""
import re


def item_mentions(notes):
    """Return literal quantity x item mentions; never assert they belong in a BOM."""
    if not notes:
        return []
    pattern = re.compile(r'(?<![A-Z0-9])(?P<quantity>\d+(?:[.,]\d+)?)\s*[xX\u00d7]\s*(?P<item>[A-Z0-9][A-Z0-9_-]{5,29})(?![A-Z0-9])', re.I)
    return [{'item': m.group('item'), 'quantity_text': m.group('quantity'), 'source': m.group(0)} for m in pattern.finditer(str(notes))]
