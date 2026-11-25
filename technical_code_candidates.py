"""Find historical machine-code candidates without asserting engineering approval."""
import re
import pandas as pd


def _text(value):
    return '' if pd.isna(value) else str(value).strip()


def machine_candidates(headers, associations, variant, connection, power):
    if not variant or not connection or power not in ('3.05 kW', '5.05 kW'):
        return []
    watts = '3050' if power == '3.05 kW' else '5050'
    decimal = '3' if watts == '3050' else '5'
    pattern = re.compile(r'(?<!\d)(?:' + watts + r'\s*W|' + decimal + r'[.,]05\s*KW)(?!\d)', re.I)
    grouped = {}
    for _, row in associations.iterrows():
        sheet, tech, code = (_text(row.get(k)) for k in ('Production Sheet', 'Technical Code', 'Commercial Code'))
        if sheet and tech and code:
            grouped.setdefault((sheet, tech), set()).add(code)
    matches = {}
    for _, row in headers.iterrows():
        sheet, code, description = (_text(row.get(k)) for k in ('Production Sheet', 'Machine Code', 'Machine Code Description'))
        if not sheet or not code or not pattern.search(description):
            continue
        if {variant, connection}.issubset(grouped.get((sheet, code), set())):
            item = matches.setdefault(code, {'code': code, 'descriptions': set(), 'sheets': set()})
            item['descriptions'].add(description)
            item['sheets'].add(sheet)
    return [{'code': x['code'], 'description': ' | '.join(sorted(x['descriptions'])), 'sheets': sorted(x['sheets'])} for x in sorted(matches.values(), key=lambda x: (-len(x['sheets']), x['code']))]
