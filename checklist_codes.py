"""Extract explicitly selected commercial codes from interactive PDF fields."""
import re

CODE = re.compile(r'(?<![A-Z0-9])FBCA\d{4}(?!\d)', re.IGNORECASE)


def extract_codes(fields):
    found = set()
    for name, field in fields.items():
        value = field.get('/V')
        if value is None or str(value).strip().lower() in ('', '/off', 'off'):
            continue
        # Printed option lists and unselected checkbox names are not evidence.
        sources = [str(value)]
        if str(field.get('/FT')) == '/Btn':
            sources.append(str(name))
        for source in sources:
            found.update(match.upper() for match in CODE.findall(source))
    return found
