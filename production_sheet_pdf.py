"""Draft production-sheet PDF based on the supplied AS/400 examples."""
from io import BytesIO
import textwrap
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_production_sheet(data):
    writer = PdfWriter()
    page = None
    commands = []
    y = 0

    def flush():
        if page is None:
            return
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode('cp1252', errors='replace'))
        page[NameObject('/Contents')] = writer._add_object(stream)

    def new_page():
        nonlocal page, commands, y
        flush()
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica'), NameObject('/Encoding'): NameObject('/WinAnsiEncoding')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        commands = []
        y = 810
        line('PRODUCTION SHEET - DRAFT', 16)
        line('PROTOTYPE - NOT APPROVED FOR PRODUCTION', 10)
        line('No live AS/400 or SAP connection. Review all values and missing data.', 9)
        y -= 8

    def line(value, size=10):
        nonlocal y
        if y < 42:
            new_page()
        value = str(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        commands.append(f'BT /F1 {size} Tf 36 {y:.0f} Td ({value}) Tj ET')
        y -= size + 5

    def section(title):
        nonlocal y
        y -= 6
        if y < 75:
            new_page()
        line(title.upper(), 11)
        commands.append(f'0.7 w 36 {y+8:.0f} m 559 {y+8:.0f} l S')

    def entry(label, value):
        value = str(value).strip() if value is not None else ''
        for part in textwrap.wrap(f'{label}: {value or "Not available"}', width=90, break_long_words=True, break_on_hyphens=False) or [label + ': Not available']:
            line(part, 9)

    new_page()
    section('Order and production')
    for label, key in [('Customer','customer'),('Order number','order_number'),('Order quantity','order_quantity'),('Production sheet number','production_sheet'),('Production dates','production_dates'),('Serial number','serial')]:
        entry(label, data.get(key))
    section('Machine and electrical connection')
    for label, key in [('Machine variant','variant'),('Commercial machine code','variant_code'),('Technical machine code','technical_machine'),('Electrical connection','connection'),('Power','power')]:
        entry(label, data.get(key))
    section('Configuration')
    for label, key in [('Control panel','panel'),('Control panel language','panel_language'),('Installation','installation'),('Drain position','drain_position'),('Drain diameter','drain_diameter'),('Closing panelling','panelling'),('Installation country','installation_country'),('Destination country','destination_country'),('Manual language','manual_language'),('Packaging','packaging')]:
        entry(label, data.get(key))
    section('Selected commercial options')
    options = data.get('options') or []
    if options:
        for option in options:
            entry('Option', option)
    else:
        line('No commercial options selected; non-commercial options are not determined.', 9)
    section('Technical options and accessories')
    line('Not determined automatically. Verify technical option codes and accessories.', 9)
    section('Notes')
    entry('Order notes', data.get('notes'))
    new_page()
    section('Traceable components')
    line('Not available: traceability data and serial numbers are not provided by this prototype.', 9)
    line('No component list on this page is implied or generated.', 9)
    section('Source and limitations')
    entry('Input source', data.get('source'))
    entry('Input file', data.get('filename'))
    line('This document is a draft based on entered data and supported PDF extraction.', 9)
    line('It is not an AS/400 production sheet or an approved complete BOM.', 9)
    line('Machine/option BOMs, quantities, special requests and applicability require review.', 9)
    flush()
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
