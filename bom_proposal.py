"""Historical BOM suggestions and grouped backtesting; not production rules."""
from collections import Counter, defaultdict
import math
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


def clean(value):
    return '' if pd.isna(value) else str(value).strip()


def build_examples(associations, links, bom):
    ac = associations.copy()
    ac['Production Sheet'] = ac['Production Sheet'].map(clean)
    ac['Commercial Code'] = ac['Commercial Code'].map(clean)
    ac = ac[ac['Commercial Code'].str.startswith('FBCA')]
    code_sets = ac.groupby('Production Sheet')['Commercial Code'].agg(frozenset)
    lk = links.copy()
    for col in ['Production Sheet', 'Production Order']:
        lk[col] = lk[col].map(clean)
    lk = lk[(lk['Production Sheet'] != '') & (lk['Production Order'] != '')]
    order_sets = lk.groupby('Production Sheet')['Production Order'].agg(frozenset)
    lines = bom.copy()
    for col in ['Production Order', 'Item Code', 'Item Code Description']:
        lines[col] = lines[col].map(clean)
    lines['Quantity'] = pd.to_numeric(lines['Quantity'], errors='coerce')
    valid_lines = lines[(lines['Production Order'] != '') & (lines['Item Code'] != '')]
    quantities = valid_lines.groupby(['Production Order', 'Item Code'])['Quantity'].agg(lambda v: v.sum() if v.notna().all() else float('nan'))
    descriptions = valid_lines.groupby('Item Code')['Item Code Description'].agg(lambda v: next((x for x in v if x), ''))
    orders_present = set(valid_lines['Production Order'])
    records = []
    for sheet in code_sets.index.intersection(order_sets.index):
        orders = order_sets[sheet]
        if not orders.issubset(orders_present):
            continue
        per_order = quantities.loc[quantities.index.get_level_values(0).isin(orders)]
        if per_order.empty or per_order.isna().any() or (per_order < 0).any():
            continue
        # Totals across linked production orders, not normalized per machine.
        parts = per_order.groupby(level=1).sum().to_dict()
        records.append({'sheet': sheet, 'codes': code_sets[sheet], 'orders': orders, 'parts': parts})
    return records, descriptions.to_dict()


def neighbors(query, records, k=5):
    variants = set(query) & {'FBCA0000', 'FBCA0001', 'FBCA0002'}
    if len(variants) != 1:
        return []
    result = []
    for row in records:
        if not variants.issubset(row['codes']):
            continue
        union = set(query) | row['codes']
        score = len(set(query) & row['codes']) / len(union) if union else 0
        if score:
            result.append((score, row))
    return sorted(result, key=lambda item: (-item[0], item[1]['sheet']))[:k]


def propose(query, records, descriptions, k=5, threshold=0.5):
    near = neighbors(query, records, k)
    if not near:
        return [], []
    samples = defaultdict(list)
    for _, row in near:
        for part, quantity in row['parts'].items():
            samples[part].append(float(quantity))
    output = []
    for part, amounts in samples.items():
        if len(amounts) / len(near) < threshold:
            continue
        counts = Counter(amounts)
        mode = sorted(counts, key=lambda q: (-counts[q], q))[0]
        output.append({'Item code': part, 'Description': descriptions.get(part, ''),
                       'Suggested quantity': mode, 'Quantity agreement': counts[mode],
                       'Observed in': len(amounts), 'References': len(near),
                       'Quantity range': f'{min(amounts):g}–{max(amounts):g}'})
    return sorted(output, key=lambda row: (-row['Observed in'], row['Item code'])), near


def grouped_split(records):
    # Connected groups prevent the same code set or production order crossing the split.
    parent = list(range(len(records)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen_codes, seen_orders = {}, {}
    for i, row in enumerate(records):
        for key, seen in [(row['codes'], seen_codes), *((o, seen_orders) for o in row['orders'])]:
            if key in seen:
                parent[root(i)] = root(seen[key])
            else:
                seen[key] = i
    groups = [root(i) for i in range(len(records))]
    if len(set(groups)) < 5:
        raise ValueError('Not enough independent groups of historical orders for a test.')
    train, test = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=42).split(records, groups=groups))
    return train, test


def backtest(records, descriptions, k=5, threshold=.5):
    train_idx, test_idx = grouped_split(records)
    training = [records[i] for i in train_idx]
    tp = fp = fn = quantity_correct = 0
    exact_presence = exact_quantity = covered = 0
    for index in test_idx:
        actual = records[index]
        suggestion, near = propose(actual['codes'], training, descriptions, k, threshold)
        if not near:
            continue
        covered += 1
        predicted = {row['Item code']: row['Suggested quantity'] for row in suggestion}
        matched = set(predicted) & set(actual['parts'])
        tp += len(matched)
        fp += len(set(predicted) - set(actual['parts']))
        fn += len(set(actual['parts']) - set(predicted))
        quantity_correct += sum(math.isclose(predicted[p], actual['parts'][p], rel_tol=1e-9, abs_tol=1e-9) for p in matched)
        exact_presence += set(predicted) == set(actual['parts'])
        exact_quantity += (set(predicted) == set(actual['parts']) and all(math.isclose(predicted[p], actual['parts'][p], rel_tol=1e-9, abs_tol=1e-9) for p in matched))
    return {'precision': tp/(tp+fp) if tp+fp else None, 'recall': tp/(tp+fn) if tp+fn else None,
            'quantity_accuracy': quantity_correct/tp if tp else None,
            'exact_presence': exact_presence/covered if covered else None,
            'exact_quantity': exact_quantity/covered if covered else None,
            'covered': covered, 'test': len(test_idx), 'train': len(train_idx)}
