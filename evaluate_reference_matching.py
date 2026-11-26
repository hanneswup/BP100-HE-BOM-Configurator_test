"""Compare experimental matching against baseline on identical held-out cases."""
from pathlib import Path
import json
import math

import pandas as pd

from bom_proposal import build_examples, grouped_split, propose
from experimental_reference_matching import attach_historical_power, propose_matched


def evaluate(training, testing, descriptions):
    results = {'baseline': {'tp': 0, 'fp': 0, 'fn': 0, 'qty': 0, 'exact': 0},
               'matched': {'tp': 0, 'fp': 0, 'fn': 0, 'qty': 0, 'exact': 0}}
    comparable = 0
    for case in testing:
        new, refs = propose_matched(case['codes'], case['power_proxy'], training, descriptions)
        if not refs:
            continue
        old, old_refs = propose(case['codes'], training, descriptions)
        if not old_refs:
            continue
        comparable += 1
        for name, suggestion in [('baseline', old), ('matched', new)]:
            predicted = {item['Item code']: item['Suggested quantity'] for item in suggestion}
            actual = case['parts']
            common = set(predicted) & set(actual)
            r = results[name]
            r['tp'] += len(common)
            r['fp'] += len(set(predicted) - set(actual))
            r['fn'] += len(set(actual) - set(predicted))
            r['qty'] += sum(math.isclose(predicted[p], actual[p], rel_tol=1e-9, abs_tol=1e-9) for p in common)
            r['exact'] += set(predicted) == set(actual) and all(math.isclose(predicted[p], actual[p], rel_tol=1e-9, abs_tol=1e-9) for p in common)
    output = {'test_cases': len(testing), 'comparable_cases': comparable}
    for name, r in results.items():
        output[name] = {'precision': r['tp'] / (r['tp'] + r['fp']) if r['tp'] + r['fp'] else None,
                        'recall': r['tp'] / (r['tp'] + r['fn']) if r['tp'] + r['fn'] else None,
                        'quantity_accuracy': r['qty'] / r['tp'] if r['tp'] else None,
                        'exact_quantity': r['exact'] / comparable if comparable else None}
    return output


if __name__ == '__main__':
    p = Path(__file__).resolve().parent / 'Data' / 'Excel'
    associations = pd.read_excel(p / 'Technical-Commercial Code Assosiation in Prd Sheets.xlsx', sheet_name='BP 100 HE', dtype=object)
    links = pd.read_excel(p / 'Link Prd Sheet-Prd Order.xlsx', sheet_name='BP 100 HE', dtype=object)
    bom = pd.read_excel(p / 'Prod Ord BOMs.xlsx', sheet_name='BP 100 HE', dtype=object)
    headers = pd.read_excel(p / 'Prd Sheets Headers.xlsx', sheet_name='BP100 HE', dtype=object)
    records, descriptions = build_examples(associations, links, bom)
    records = attach_historical_power(records, headers)
    train_idx, test_idx = grouped_split(records)
    train = [records[i] for i in train_idx]
    test = [records[i] for i in test_idx]
    inner_train, inner_test = grouped_split(train)
    dev = evaluate([train[i] for i in inner_train], [train[i] for i in inner_test], descriptions)
    heldout = evaluate(train, test, descriptions)
    print(json.dumps({'development': dev, 'historical_holdout': heldout}, indent=2))
