"""In-memory production-sheet draft with a traceable historical BOM appendix."""
from io import BytesIO
import textwrap

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from production_sheet_pdf import make_production_sheet


def make_detailed_production_pdf(sheet_data, configuration, machine_candidates, components, references):
    """Return a PDF draft; all input results are unverified and never sent externally."""
    lines = []

    def add(value='', indent=''):
        text = '' if value is None else str(value)
        text = ''.join(c if c in '\t\n\r' or ord(c) >= 32 else ' ' for c in text)
        for line in textwrap.wrap(text, width=95 - len(indent), break_long_words=True,
                                  break_on_hyphens=False, replace_whitespace=True) or ['']:
            lines.append(indent + line)

    add('ORDER AND CHECKLIST INFORMATION - VALUES ENTERED OR READ BY THE APP')
    for label, key in [('Customer', 'customer'), ('Order number', 'order_number'), ('Order quantity', 'order_quantity'),
                       ('Machine variant', 'variant'), ('Electrical connection', 'connection'), ('Power', 'power'),
                       ('Control panel', 'panel'), ('Installation type', 'installation'), ('Drain position', 'drain_position'),
                       ('Drain diameter', 'drain_diameter'), ('Closing panelling', 'panelling'),
                       ('Installation country', 'installation_country'), ('Destination country', 'destination_country'),
                       ('User manual language', 'manual_language'), ('Packaging', 'packaging')]:
        value = sheet_data.get(key)
        add(f'{label}: {value if value is not None and str(value).strip() else "Not available"}')
    details = configuration.get('additional_details_not_used_in_bom') or {}
    add('Control panel language entered: ' + (str(details.get('control_panel_language') or 'Not available')))
    add('Commercial machine code: ' + str(configuration.get('variant') or 'Not available'))
    add('Commercial connection code: ' + str(configuration.get('electrical_connection') or 'Not available'))
    options = configuration.get('options') or []
    add('Commercial options entered: ' + (', '.join(map(str, options)) if options else 'None entered; absence is not verified'))
    add('Full checklist notes: ' + str(details.get('notes') or 'None entered; check the original document'))
    add('Notes and packaging are not automatically applied to the BOM. Review them with engineering.')
    add('')
    add('HISTORICAL TECHNICAL MACHINE-CODE CANDIDATES - NOT CONFIRMED')
    if not machine_candidates:
        add('No candidate found or inputs incomplete. Obtain the applicable code from engineering.')
    for candidate in machine_candidates:
        add(f"{candidate.get('code', '-')} | {candidate.get('description', '-')} | {len(candidate.get('sheets', []))} historical sheets")
    if len(machine_candidates) == 1:
        add('The single historical candidate is not an approved technical code.')
    elif len(machine_candidates) > 1:
        add('Several candidates exist; no technical code was selected automatically.')
    add('')
    add('METHOD AND LIMITATIONS')
    add('Candidate based on up to five historical sheets with the same machine variant, ranked by shared commercial codes.')
    add('A part is included when it appears in at least half of the reference sheets. With five references, at least three are required.')
    add('Suggested quantities are the most frequent historical totals across linked production orders, not verified per machine or scaled to this order.')
    add('Special notes, packaging, technical option applicability, units and revisions are not automatically applied or validated.')
    add('No 90 percent accuracy is established for this order. Compare against an approved BOM before use.')
    add('Characters not supported by the PDF font may appear as question marks; verify the original source and item master.')
    add('')
    add('HISTORICAL REFERENCES - NOT THE CURRENT ORDER')
    if not references:
        add('No usable historical references are available; no candidate BOM is included.')
    for score, record in references:
        orders = ', '.join(sorted(str(value) for value in record.get('orders', [])))
        add(f"Sheet {record.get('sheet', '-')} | commercial-code similarity {float(score) * 100:.1f}% | production orders {orders or '-'}")
    add('Similarity concerns commercial-code sets only; it is not BOM accuracy or approval.')
    add('')
    add('PROPOSED BOM COMPONENTS - ALL POSITIONS REQUIRE ENGINEERING REVIEW')
    add('Format: item code | historical suggested quantity | observed / reference sheets')
    add('An asterisk identifies historical presence or quantity disagreement. All other rows also remain unverified.')
    for item in components:
        marker = '*' if str(item.get('Review alert', '')).startswith('CHECK') else '-'
        add(f"{marker} {item.get('Item code', '-')} | qty {item.get('Suggested quantity', '-')} | {item.get('Observed in', '-')}/{item.get('References', '-')}")
        add(item.get('Description') or 'Description unavailable', indent='   ')
    if not components:
        add('No component suggestions are available.')
    add('')
    add('END OF DRAFT. Review all positions, missing items, quantities, units and special notes against the approved order BOM.')

    per_page = 48
    chunks = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]
    writer = PdfWriter()
    writer.append(BytesIO(make_production_sheet(sheet_data)))
    regular = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                                NameObject('/BaseFont'): NameObject('/Helvetica'), NameObject('/Encoding'): NameObject('/WinAnsiEncoding')})
    font = writer._add_object(regular)
    for index, chunk in enumerate(chunks, 1):
        page = writer.add_blank_page(width=595, height=842)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        commands = []

        def text(x, y, value, size=8):
            escaped = str(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)').replace('\r', ' ').replace('\n', ' ')
            commands.append(f'BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET')

        text(30, 815, 'BOM REVIEW APPENDIX - UNVERIFIED DRAFT - NOT FOR PRODUCTION', 10)
        text(30, 800, 'Historical suggestions only. Check the approved BOM and original OCL.', 8)
        for offset, line in enumerate(chunk):
            text(30, 780 - offset * 15, line, 8)
        text(30, 35, f'BOM review appendix {index} / {len(chunks)}', 8)
        stream = DecodedStreamObject()
        stream.set_data('\n'.join(commands).encode('cp1252', errors='replace'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    result = output.getvalue()
    if len(PdfReader(BytesIO(result)).pages) != 2 + len(chunks):
        raise ValueError('The detailed PDF page count could not be verified.')
    return result
