"""Transparent XML exports for exploratory BOM outputs, not an ERP schema."""
from xml.etree import ElementTree as ET
import re
import pandas as pd


def _clean(value):
    if value is None or pd.isna(value):
        return ''
    # XML 1.0 forbids most C0 control characters even when escaped.
    return ''.join(c for c in str(value).strip() if c in '\t\n\r' or '\x20' <= c <= '\ud7ff' or '\ue000' <= c <= '\ufffd' or '\U00010000' <= c <= '\U0010ffff')


def _element(parent, name, value):
    element = ET.SubElement(parent, name)
    cleaned = _clean(value)
    if cleaned:
        element.text = cleaned
    else:
        element.set('status', 'not_available')
    return element


def _document(kind, description):
    root = ET.Element('BOMExport', {'type': kind, 'status': 'unverified', 'schemaVersion': '1'})
    _element(root, 'Warning', 'DRAFT: Not approved for production. Engineering must review components, quantities and applicability.')
    _element(root, 'Scope', description)
    return root


def _configuration(root, config):
    node = ET.SubElement(root, 'OrderConfiguration')
    _element(node, 'MachineVariantCommercialCode', config.get('variant'))
    _element(node, 'ElectricalConnectionCommercialCode', config.get('electrical_connection'))
    options = ET.SubElement(node, 'CommercialOptions')
    for code in config.get('options', []):
        _element(options, 'CommercialOptionCode', code)
    details = config.get('additional_details_not_used_in_bom') or {}
    _element(node, 'PackagingNotAppliedToBOM', details.get('packaging'))
    _element(node, 'NotesRequiringReview', details.get('notes'))


def _xml(root):
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def historical_candidate_xml(config, candidates, references):
    root = _document('historical_candidate', 'Statistical candidate from historical orders; component hierarchy, units and quantities per machine are not established.')
    _configuration(root, config)
    refs = ET.SubElement(root, 'HistoricalReferences')
    for score, record in references:
        ref = ET.SubElement(refs, 'Reference')
        _element(ref, 'ProductionSheet', record.get('sheet'))
        _element(ref, 'CodeSimilarity', score)
        orders = ET.SubElement(ref, 'ProductionOrders')
        for order in sorted(record.get('orders', [])):
            _element(orders, 'ProductionOrder', order)
    lines = ET.SubElement(root, 'CandidateComponents', {'hierarchy': 'flat_unknown', 'quantityBasis': 'historical_order_total_unverified'})
    for _, row in candidates.iterrows():
        line = ET.SubElement(lines, 'Component', {'status': 'unverified'})
        for key, column in [('ItemCode', 'Item code'), ('Description', 'Description'), ('SuggestedQuantity', 'Suggested quantity'),
                            ('Unit', 'Unit of measure'), ('BOMLevel', 'BOM level'), ('RuleID', 'Rule ID'),
                            ('QuantityAgreement', 'Quantity agreement'), ('ObservedIn', 'Observed in'), ('References', 'References'),
                            ('QuantityRange', 'Quantity range'), ('ReviewAlert', 'Review alert')]:
            _element(line, key, row.get(column))
    return _xml(root)


def technical_preview_xml(config, summary, contributions):
    root = _document('technical_preview', 'Direct level-one positions grouped by explicitly selected source BOM; not a full multi-level explosion. Signed source quantities are not normalised to order quantity.')
    _configuration(root, config)
    sources = ET.SubElement(root, 'SourceBOMs')
    for (role, code), group in contributions.groupby(['Source role', 'Source BOM'], sort=False, dropna=False):
        source = ET.SubElement(sources, 'SourceBOM', {'role': _clean(role), 'code': _clean(code), 'level': '1_only'})
        for _, row in group.iterrows():
            line = ET.SubElement(source, 'Component', {'status': 'unverified'})
            for key, column in [('ItemCode', 'Item code'), ('Description', 'Description'), ('SignedQuantity', 'Source quantity'),
                                ('ParentCode', 'Parent code'), ('Sequence', 'Sequence'), ('ValidFrom', 'Source valid from'),
                                ('ValidTo', 'Source valid to'), ('ProductionBOMFlag', 'Production BOM flag')]:
                _element(line, key, row.get(column))
            _element(line, 'Unit', None)
    net = ET.SubElement(root, 'NetComponents', {'quantityBasis': 'unverified'})
    for _, row in summary.iterrows():
        component = ET.SubElement(net, 'Component', {'status': 'unverified'})
        _element(component, 'ItemCode', row.get('Item code'))
        _element(component, 'NetQuantity', row.get('Net quantity'))
        _element(component, 'Review', row.get('Review'))
    return _xml(root)


def historical_reference_xml(sheet, reference_bom, missing_orders):
    root = _document('historical_reference', 'Recorded production-order BOM from a historical sheet, not the BOM generated from the current order. Assembly hierarchy and quantity basis are not established.')
    _element(root, 'ProductionSheet', sheet)
    missing = ET.SubElement(root, 'MissingProductionBOMOrders')
    for order in missing_orders:
        _element(missing, 'ProductionOrder', order)
    orders = ET.SubElement(root, 'ProductionOrders', {'componentHierarchy': 'flat_unknown'})
    for order, group in reference_bom.groupby('Production Order', sort=False, dropna=False):
        order_node = ET.SubElement(orders, 'ProductionOrder', {'number': _clean(order)})
        for _, row in group.iterrows():
            line = ET.SubElement(order_node, 'Component', {'status': 'historical_unverified'})
            for key, column in [('MachineCode', 'Machine Code'), ('MachineDescription', 'Machine Code Description'),
                                ('ItemCode', 'Item Code'), ('Description', 'Item Code Description'), ('Quantity', 'Quantity')]:
                _element(line, key, row.get(column))
            _element(line, 'Unit', None)
    return _xml(root)


def engineering_tree_xml(frame, root_codes):
    """Export source ordering/levels as a tree without exploding or summing BOMs."""
    root = _document('engineering_source_tree', 'Historical engineering BOM source tree; source row levels and order are preserved. Not a current or approved production BOM; no validity, unit, quantity or option applicability is validated.')
    trees = ET.SubElement(root, 'SourceBOMs')
    levels = []
    for value in frame['Level']:
        match = re.search(r'(\d+)\s*$', _clean(value))
        levels.append(int(match.group(1)) if match else None)
    codes = [_clean(value) for value in frame['Item Code']]
    starts = {}
    for code in root_codes:
        found = [i for i, level in enumerate(levels) if level == 0 and codes[i] == code]
        if len(found) != 1:
            raise ValueError(f'Source BOM {code} has {len(found)} matching root rows; exactly one is needed to export a tree.')
        starts[code] = found[0]
    for code in root_codes:
        start = starts[code]
        end = next((i for i in range(start + 1, len(frame)) if levels[i] == 0), len(frame))
        source = ET.SubElement(trees, 'SourceBOM', {'code': code, 'status': 'unverified'})
        stack = {0: (source, code)}
        root_row = frame.iloc[start]
        _element(source, 'Description', root_row.get('Item Code Description'))
        for position in range(start + 1, end):
            row = frame.iloc[position]
            level = levels[position]
            if level is None or level < 1 or level - 1 not in stack:
                raise ValueError(f'Source BOM {code} contains an invalid or missing level at row {position + 1}; no tree was exported.')
            parent, parent_code = stack[level - 1]
            item_code = _clean(row.get('Item Code'))
            source_parent = _clean(row.get('Father Code'))
            if not item_code:
                raise ValueError(f'Source BOM {code} contains a component without an item code at row {position + 1}.')
            node = ET.SubElement(parent, 'Component', {'level': str(level), 'status': 'unverified',
                                 'parentCheck': 'match' if source_parent == parent_code else 'mismatch_or_missing'})
            for name, column in [('ItemCode', 'Item Code'), ('Description', 'Item Code Description'),
                                 ('Quantity', 'Quantity'), ('SourceParentCode', 'Father Code'),
                                 ('Sequence', 'Sequence'), ('ProductionBOMFlag', 'Item in Production Bom?')]:
                _element(node, name, row.get(column))
            for name, prefix in [('ValidFrom', 'Data inizio'), ('ValidTo', 'Data fine')]:
                column = next((c for c in frame.columns if str(c).startswith(prefix)), None)
                _element(node, name, row.get(column) if column else None)
            _element(node, 'Unit', None)
            stack = {depth: item for depth, item in stack.items() if depth < level}
            stack[level] = (node, item_code)
    return _xml(root)
