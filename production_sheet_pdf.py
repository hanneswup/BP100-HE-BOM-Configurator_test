"""Production-sheet draft laid out after the supplied AS/400 examples."""
from io import BytesIO
import textwrap
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_production_sheet(data):
    writer = PdfWriter()
    pages = []

    def page():
        sheet = writer.add_blank_page(width=595, height=842)
        fonts = DictionaryObject()
        for name, base in [('F1', '/Helvetica'), ('F2', '/Helvetica-Bold')]:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject(base), NameObject('/Encoding'): NameObject('/WinAnsiEncoding')})
            fonts[NameObject('/' + name)] = writer._add_object(font)
        sheet[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): fonts})
        commands = []
        pages.append((sheet, commands))
        return commands

    def text(c, x, y, value, size=7, bold=False):
        value = str(value or '').replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)').replace('\n', ' ')
        c.append(f'BT /F{2 if bold else 1} {size} Tf {x:.1f} {y:.1f} Td ({value}) Tj ET')

    def box(c, x, y, w, h, fill=None):
        if fill:
            c.append(f'{fill} rg {x} {y} {w} {h} re f 0 g')
        c.append(f'0 G 0.5 w {x} {y} {w} {h} re S')

    def fit(value, max_chars):
        value = str(value).strip() if value is not None else ''
        if not value:
            return '-'
        return value if len(value) <= max_chars else value[:max_chars-3] + '...'

    def field(c, x, y, w, h, label, value):
        box(c, x, y, w, h)
        text(c, x+4, y+h-9, label, 6)
        text(c, x+4, y+5, fit(value, max(8, int(w/4.4))), 8, True)

    def bar(c, y, title):
        box(c, 20, y, 555, 14, '0.61 1 1')
        text(c, 25, y+4, title, 9, True)

    def row(c, y, code, description, qty='-', line='-'):
        text(c, 25, y, fit(code, 17), 6.5)
        text(c, 92, y, fit(description, 66), 6.5)
        text(c, 510, y, fit(qty, 8), 6.5)
        text(c, 546, y, fit(line, 5), 6.5)

    c=page()
    box(c, 20, 20, 555, 805)
    text(c, 25, 806, 'SteelcoBelimed', 11, True)
    text(c, 190, 807, 'SCHEDA TECNICA di PRODUZIONE', 13, True)
    text(c, 405, 791, 'DRAFT - NOT FOR PRODUCTION', 8, True)
    field(c,20,765,115,25,'N. Scheda',None); field(c,135,765,88,25,'Revisione',None); field(c,223,765,92,25,'Quantita',data.get('order_quantity')); field(c,315,765,260,25,'Linea di produzione',None)
    field(c,20,742,203,23,'Cliente',data.get('customer')); field(c,223,742,92,23,'Ordine cliente',data.get('order_number')); field(c,315,742,260,23,'Progetto',None)
    for x,w,label in [(20,148,'Data inizio produzione'),(168,147,'Data fat.'),(315,130,'Data fine produzione'),(445,130,'Data consegna')]: field(c,x,718,w,24,label,None)
    field(c,20,694,186,24,'Tipo macchina',data.get('variant')); field(c,206,694,109,24,'Codice articolo',data.get('technical_machine')); field(c,315,678,260,40,'Descrizione articolo',None)
    field(c,20,664,98,30,'Modello ICOS',None); field(c,118,664,98,30,'Modello configurato',None); field(c,216,664,99,30,'Requisiti',None)
    field(c,20,640,186,24,'Matricola',None); field(c,206,640,109,24,'Matricola cliente',None); field(c,315,640,260,38,'Codice a barre matricola',None)
    field(c,20,610,98,30,'Configurazione porte',None); field(c,118,610,98,30,'Disinfezione',None); field(c,216,610,99,30,'Alimentazione',None)
    field(c,315,610,260,30,'Electrical connection (commercial)',data.get('connection'))
    field(c,20,578,98,32,'Lingua software',data.get('panel_language')); field(c,118,578,98,32,'Lingua libretto',data.get('manual_language')); field(c,216,578,99,32,'Tipo libretto',None)
    field(c,315,578,130,32,'Potenza',data.get('power')); field(c,445,578,130,32,'2a Alimentazione',None)
    field(c,20,550,98,28,'Brand etichetta',None); field(c,118,550,98,28,'Personal. imballo',None); field(c,216,550,99,28,'Tipo imballo',data.get('packaging')); field(c,315,550,130,28,'Installation country',data.get('installation_country')); field(c,445,550,130,28,'Destination country',data.get('destination_country'))
    bar(c,536,'ANNOTAZIONI / COMMENTI')
    note = fit(data.get('notes'), 110)
    text(c,25,524,note,7)
    bar(c,508,'OPTIONAL - COMMERCIAL CODES')
    text(c,25,498,'Codice',7,True); text(c,92,498,'Descrizione',7,True); text(c,510,498,'Q.ta',7,True); text(c,546,498,'L.p.',7,True)
    options=data.get('options') or []
    for i, option in enumerate(options[:17]):
        code, _, desc = option.partition(' | ')
        row(c, 489-i*9, code, desc)
    if not options: text(c,25,487,'No commercial options selected',7)
    accessory_y = 475 - max(0, len(options) - 1) * 9
    bar(c,accessory_y,'CESTI / ACCESSORI')
    text(c,25,accessory_y-11,'Articolo',7,True); text(c,92,accessory_y-11,'Descrizione',7,True); text(c,510,accessory_y-11,'Q.ta',7,True); text(c,546,accessory_y-11,'L.p.',7,True)
    text(c,25,accessory_y-22,'Not available - technical accessories are not determined',7)
    config_y = accessory_y - 39
    bar(c,config_y,'CONFIGURAZIONE')
    for i,(label,key) in enumerate([('Tipo pulsantiera','panel'),('Installation type','installation'),('Drain position','drain_position'),('Drain diameter','drain_diameter'),('Closing panelling','panelling')]):
        text(c,25,config_y-11-i*12,fit(label + ': ' + str(data.get(key) or '-'),65),7)
    text(c,25,37,'DRAFT - verify technical codes, options, quantities and notes',7,True)
    text(c,520,27,'1 / 2',7,True)
    c=page()
    box(c,20,20,555,805)
    field(c,20,775,190,30,'N. SCHEDA',None); field(c,210,775,100,30,'MATRICOLA',None)
    box(c,310,775,265,30); text(c,315,785,'COMPONENTI SOGGETTI A RINTRACCIABILITA',8,True)
    text(c,25,762,'Articolo',7,True); text(c,105,762,'Descrizione',7,True); text(c,320,762,'Posizione',7,True); text(c,430,762,'Riferimento',7,True)
    c.append('20 756 m 575 756 l S')
    text(c,25,741,'Traceability data not available in this prototype.',8)
    text(c,25,728,'Do not use this draft as an approved production document.',8,True)
    text(c,520,27,'2 / 2',7,True)
    for sheet,commands in pages:
        stream=DecodedStreamObject(); stream.set_data('\n'.join(commands).encode('cp1252',errors='replace')); sheet[NameObject('/Contents')]=writer._add_object(stream)
    out=BytesIO(); writer.write(out); return out.getvalue()
