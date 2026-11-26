"""Experimental reference filter. No technical-code mapping is inferred."""
import re
from collections import defaultdict
import pandas as pd

from bom_proposal import clean, propose


def _power(description):
    value = clean(description).upper().replace(',', '.')
    matches = set()
    for watts, decimal in [('3050', '3.05'), ('5050', '5.05')]:
        if re.search(r'(?<!\d)(?:' + watts + r'\s*W|' + re.escape(decimal) + r'\s*KW)(?!\d)', value):
            matches.add(decimal + ' kW')
    return matches


def attach_historical_power(records, headers):
    """Attach only unambiguous sheet-level power inferred from historical descriptions.

    In evaluation this is a proxy for an OCL input, not a verified OCL value.
    """
    by_sheet = defaultdict(set)
    for _, row in headers.iterrows():
        by_sheet[clean(row.get('Production Sheet'))].update(_power(row.get('Machine Code Description')))
    result = []
    for record in records:
        values = by_sheet.get(record['sheet'], set())
        result.append({**record, 'power_proxy': next(iter(values)) if len(values) == 1 else None})
    return result


def connection_code(codes):
    choices = {code for code in codes if re.fullmatch(r'FBCA02(?:0[1-9]|1\d|2[0-4])', code)}
    return next(iter(choices)) if len(choices) == 1 else None


def propose_matched(query, power, training, descriptions, k=5, threshold=0.5):
    """Require variant, connection and power; abstain instead of widening the filter."""
    conn = connection_code(query)
    if not conn or power not in ('3.05 kW', '5.05 kW'):
        return [], []
    eligible = [row for row in training if connection_code(row['codes']) == conn and row.get('power_proxy') == power]
    return propose(query, eligible, descriptions, k=k, threshold=threshold)


def machine_tree_item_codes(technical_boms, machine_code):
    """Get source item codes at all recorded levels; never infer applicability."""
    if not machine_code:
        return None
    levels = pd.to_numeric(technical_boms['Level'], errors='coerce')
    codes = technical_boms['Item Code'].map(clean)
    starts = [i for i, (level, code) in enumerate(zip(levels, codes)) if level == 0 and code == machine_code]
    if len(starts) != 1:
        return None
    start = starts[0]
    end = next((i for i in range(start + 1, len(technical_boms)) if levels.iloc[i] == 0), len(technical_boms))
    return {code for code in codes.iloc[start + 1:end] if code}
