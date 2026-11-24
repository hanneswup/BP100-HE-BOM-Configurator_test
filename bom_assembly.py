"""Exploratory, traceable combination of explicitly selected technical BOMs."""
from decimal import Decimal, InvalidOperation
import pandas as pd


def clean(value):
    if pd.isna(value):
        return ''
    return str(value).strip()


def technical_roots(frame):
    levels = pd.to_numeric(frame['Level'], errors='coerce')
    result = frame.loc[levels.eq(0), ['Item Code', 'Item Code Description']].copy()
    result['Item Code'] = result['Item Code'].map(clean)
    result['Item Code Description'] = result['Item Code Description'].map(clean)
    return result[result['Item Code'] != '']


def direct_bom_lines(frame, root_code):
    levels = pd.to_numeric(frame['Level'], errors='coerce')
    roots = frame.index[levels.eq(0) & frame['Item Code'].map(clean).eq(root_code)].tolist()
    if len(roots) != 1:
        raise ValueError(f'Technical code {root_code} has {len(roots)} BOM roots; exactly one is required.')
    start = frame.index.get_loc(roots[0])
    after = levels.iloc[start + 1:]
    next_root = next((i for i, value in enumerate(after, start + 1) if value == 0), len(frame))
    block = frame.iloc[start + 1:next_root]
    direct = block.loc[pd.to_numeric(block['Level'], errors='coerce').eq(1)].copy()
    if direct.empty:
        raise ValueError(f'Technical code {root_code} has no direct BOM lines.')
    return direct


def build_assembly_preview(frame, machine_code, option_codes):
    """Sum signed level-1 quantities once per chosen root, without ERP assumptions."""
    roots = [machine_code] + list(option_codes)
    if not machine_code or len(set(roots)) != len(roots):
        raise ValueError('Select one machine BOM and distinct option BOMs.')
    details, totals = [], {}
    valid_from = next((c for c in frame.columns if str(c).startswith('Data inizio')), None)
    valid_to = next((c for c in frame.columns if str(c).startswith('Data fine')), None)
    for index, root in enumerate(roots):
        role = 'Machine' if index == 0 else 'Option'
        for _, row in direct_bom_lines(frame, root).iterrows():
            item = clean(row['Item Code'])
            if not item:
                raise ValueError(f'{root} has a line without an item code.')
            try:
                value = Decimal(clean(row['Quantity']))
            except (InvalidOperation, ValueError):
                raise ValueError(f'{root}, item {item}: quantity is missing or invalid.')
            if not value.is_finite():
                raise ValueError(f'{root}, item {item}: quantity is not finite.')
            previous = totals.get(item, Decimal('0'))
            totals[item] = previous + value
            details.append({'Source BOM': root, 'Source role': role, 'Item code': item,
                'Description': clean(row['Item Code Description']), 'Source quantity': format(value.normalize(), 'f'),
                'Sequence': clean(row.get('Sequence')), 'Parent code': clean(row.get('Father Code')),
                'Source valid from': clean(row[valid_from]) if valid_from else '',
                'Source valid to': clean(row[valid_to]) if valid_to else '',
                'Production BOM flag': clean(row.get('Item in Production Bom?'))})
    summary = [{'Item code': code, 'Net quantity': format(value.normalize(), 'f'),
                'Review': 'Negative result — check source and applicability' if value < 0 else
                          'Zero — fully offset; verify before omission' if value == 0 else 'Not validated'}
               for code, value in totals.items()]
    return pd.DataFrame(summary), pd.DataFrame(details)
