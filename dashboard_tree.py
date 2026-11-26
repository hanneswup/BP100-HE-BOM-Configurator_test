"""Safe, collapsible dashboard tree; distinguishes source hierarchy from suggestions."""
from html import escape
from xml.etree import ElementTree as ET


def _text(value):
    return escape(str(value if value is not None and str(value).strip() else 'Not provided'), quote=True)


def _branch(title, body, opened=False):
    return '<li><details' + (' open' if opened else '') + '><summary>' + _text(title) + '</summary><ul>' + body + '</ul></details></li>'


def _leaf(label, value=None):
    return '<li><span class="tree-label">' + _text(label) + '</span>' + (': <span class="tree-value">' + _text(value) + '</span>' if value is not None else '') + '</li>'


def _source_component(node):
    label = (node.findtext('ItemCode') or 'Unknown item') + ' | ' + (node.findtext('Description') or 'Description unavailable')
    quantity = node.findtext('Quantity') or 'Not available'
    label += ' | source qty: ' + quantity
    if node.get('parentCheck') != 'match':
        label += ' | source parent mismatch: review'
    children = node.findall('Component')
    return _branch(label, ''.join(_source_component(child) for child in children)) if children else _leaf(label)


def render_dashboard_tree(configuration, candidates, candidate_rows=None, references=None, evaluation=None, source_xml=None, source_error=None):
    """Return escaped HTML only; source XML hierarchy is never inferred from suggestions."""
    values = [
        ('Machine variant', configuration.get('variant')),
        ('Electrical connection', configuration.get('connection')),
        ('Power', configuration.get('power')),
        ('Control panel', configuration.get('panel')),
        ('Installation', configuration.get('installation')),
        ('Drain position', configuration.get('drain_position')),
        ('Drain diameter', configuration.get('drain_diameter')),
        ('Packaging', configuration.get('packaging')),
        ('Checklist notes', configuration.get('notes')),
    ]
    config_body = ''.join(_leaf(k, v if v is not None and str(v).strip() else 'Not entered - check source') for k, v in values)
    options = configuration.get('options') or []
    config_body += _branch('Commercial options entered', ''.join(_leaf(x) for x in options) if options else _leaf('None entered - absence not verified'))
    candidate_body = ''.join(_leaf(c.get('code'), str(c.get('description', '')) + ' | ' + str(len(c.get('sheets', []))) + ' historical sheets') for c in candidates)
    if not candidate_body:
        candidate_body = _leaf('No candidate found or required inputs are incomplete')
    candidate_body += _leaf('All technical-code candidates are historical and unverified')

    if source_xml:
        source_root = ET.fromstring(source_xml)
        source_boms = source_root.findall('./SourceBOMs/SourceBOM')
        source_body = ''
        for bom in source_boms:
            children = ''.join(_source_component(node) for node in bom.findall('Component'))
            source_body += _branch('Historical source BOM ' + (bom.get('code') or 'unknown'), children or _leaf('No source components found'))
        source_body += _leaf('Source levels, quantities and applicability are not approved or validated')
    elif source_error:
        source_body = _leaf('Source tree unavailable', source_error)
    else:
        source_body = _leaf('Select a technical-code candidate above to inspect its source BOM tree')

    if candidate_rows is None:
        proposal_body = _leaf('Not calculated - complete the required fields first')
    elif not candidate_rows:
        proposal_body = _leaf('No historical BOM candidate is available')
    else:
        proposal_body = _leaf('Flat historical component suggestions - assembly hierarchy is unknown')
        for item in candidate_rows:
            label = str(item.get('Item code', 'Unknown')) + ' | ' + str(item.get('Description', ''))
            qty = item.get('Suggested quantity', 'Not available')
            alert = item.get('Review alert', 'Unverified')
            proposal_body += _leaf(label, 'historical qty: ' + str(qty) + ' | ' + str(alert))
    refs_body = ''.join(_leaf(row.get('sheet'), f'{score:.1%} commercial-code similarity') for score, row in (references or []))
    if not refs_body:
        refs_body = _leaf('Not available or not yet calculated')

    if evaluation:
        def fmt(key):
            value = evaluation.get(key)
            return f'{value:.1%}' if value is not None else 'Not available'
        evaluation_body = ''.join(_leaf(k, fmt(v)) for k, v in [('Component precision', 'precision'), ('Component completeness', 'recall'), ('Quantity agreement among matched parts', 'quantity_accuracy'), ('Complete BOM and quantities', 'exact_quantity')])
        evaluation_body += _leaf('Scope', 'Historical aggregate results; not an accuracy score for this order')
    else:
        evaluation_body = _leaf('Historical test not yet available')

    body = (_branch('Order and configuration', config_body)
            + _branch(f'Technical machine-code candidates ({len(candidates)})', candidate_body)
            + _branch('Technical source BOM - recorded hierarchy', source_body)
            + _branch('BOM candidate - flat historical suggestions', proposal_body)
            + _branch('Historical references', refs_body)
            + _branch('Historical test and 90% target', evaluation_body))
    return '<div class="bom-tree"><ul>' + _branch('BOM configurator | unverified draft', body, opened=True) + '</ul></div>'
