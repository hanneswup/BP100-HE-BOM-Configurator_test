from pathlib import Path
from io import BytesIO
import base64
import hashlib
import json
import re
import os
import pandas as pd
import streamlit as st
from pypdf import PdfReader
from checklist_codes import extract_codes, extract_visual_codes, extract_rev08_form_values, extract_rev08_connection
from bom_xml import engineering_tree_xml, historical_candidate_xml, technical_preview_xml, historical_reference_xml

DATA = Path(__file__).resolve().parent / 'Data' / 'Excel'
st.set_page_config(page_title='BP100 HE BOM Configurator', layout='wide')
st.markdown("""
<style>
.brand-logo { width: 440px; max-width: 100%; height: 76px; background-repeat: no-repeat; background-position: center 42%; background-size: 100% auto; flex: 0 1 440px; }
.stApp { background: #f3f6f7; color: #233b48; }
[data-testid="stMainBlockContainer"] { padding-top: 2rem; padding-bottom: 5rem; max-width: 1320px; }
h1, h2, h3 { color: #102f40 !important; letter-spacing: -.025em; }
[data-testid="stHeader"] { background: rgba(243,246,247,.96); }
.hero { background: #fff; border-top: 7px solid #284a98; border-image: linear-gradient(90deg, #284a98 35%, #2f886b) 1; padding: 32px 36px; margin-bottom: 6px; display: flex; align-items: center; justify-content: space-between; gap: 30px; }
.hero-copy { flex: 1 1 420px; }
.hero .eyebrow { color: #2d886b; font-size: 12px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.hero h1 { color: #254992 !important; font-size: 2.25rem; margin: 8px 0; }
.hero p { color: #536578; font-size: 1rem; max-width: 750px; margin: 0; }
.workflow { display: flex; gap: 12px; flex-wrap: wrap; margin: 8px 0 4px; }
.workflow span { background: #fff; color: #47616b; border: 1px solid #dfe9e9; border-radius: 8px; padding: 9px 13px; font-size: .83rem; font-weight: 600; }
.workflow b { color: #2f886b; margin-right: 7px; }
[data-testid="stExpander"] { background: #fff; border: 1px solid #dce7e8; border-radius: 12px; }
[data-testid="stMetric"] { background: #fff; border: 1px solid #dce7e8; border-radius: 12px; padding: 19px; box-shadow: 0 2px 10px rgba(22,62,72,.04); }
[data-testid="stMetricLabel"] { color: #526d78; }
[data-testid="stMetricValue"] { color: #284a98; }
.dashboard-title { background: white; border-left: 5px solid #2f886b; padding: 18px 22px; margin: 12px 0 14px; box-shadow: 0 2px 8px rgba(22,62,72,.06); }
.dashboard-title .dash-eyebrow { color: #2f886b; font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.dashboard-title .dash-name { color: #173c52; font-size: 23px; font-weight: 700; line-height: 1.25; margin-top: 4px; }
.dashboard-title .dash-subtitle { color: #647b88; font-size: 13px; margin-top: 4px; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #d5e1e3; }
.stTabs [data-baseweb="tab"] { color: #536d78; padding: 10px 16px; }
.stTabs [aria-selected="true"] { color: #007c79 !important; border-bottom-color: #00958e !important; }
.stDownloadButton button { background: #2f886b; color: white; border: 1px solid #2f886b; border-radius: 8px; font-weight: 600; }
.stDownloadButton button:hover { background: #246e57; color: white; border-color: #246e57; }
[data-testid="stFileUploader"] section { background: #f2faf8; border: 1px dashed #85bcb5; border-radius: 10px; }
[data-testid="stAlert"] { border-radius: 10px; }
@media (max-width: 800px) { .hero { padding: 24px; flex-wrap: wrap; } .hero-copy { flex-basis: 100%; } .brand-logo { flex-basis: 340px; height: 65px; } .hero h1 { font-size: 1.7rem; } }
</style>
""", unsafe_allow_html=True)
logo_file = Path(__file__).resolve().parent / 'steelco-logo.jpg'
logo_html = ''
if logo_file.is_file():
    logo_data = base64.b64encode(logo_file.read_bytes()).decode('ascii')
    logo_html = f'<div class="brand-logo" role="img" aria-label="SteelcoBelimed, Miele Group Member" style="background-image:url(data:image/jpeg;base64,{logo_data})"></div>'
st.markdown('''<div class="hero"><div class="hero-copy"><div class="eyebrow">BP 100 HE · Configuration workspace</div>
<h1>From checklist to reference BOM</h1>
<p>Upload an order checklist, review its configuration and explore comparable production records.</p></div>''' + logo_html + '''</div>
<div class="workflow"><span>Order information</span><span>Configuration</span><span>Reference BOM</span></div>''', unsafe_allow_html=True)

@st.cache_data(show_spinner='Loading source files...')
def load():
    files={'headers':('Prd Sheets Headers.xlsx','BP100 HE'), 'links':('Link Prd Sheet-Prd Order.xlsx','BP 100 HE'), 'bom':('Prod Ord BOMs.xlsx','BP 100 HE'), 'routing':('BP100 Time routings.xlsx','BP100 HE'), 'assoc':('Technical-Commercial Code Assosiation in Prd Sheets.xlsx','BP 100 HE'), 'config':('List of Technical Configurations.xlsx','BP100 HE'), 'notes':('Prd Sheets Notes.xlsx','BP 100 HE'), 'technical':('Technical BOMs.xlsx','BP 100 HE')}
    result={}
    for name,(filename,sheet) in files.items():
        df=pd.read_excel(DATA/filename,sheet_name=sheet,dtype=object)
        df=df.loc[:,[not str(c).startswith('Unnamed:') for c in df.columns]]
        df.columns=[str(c).strip() for c in df.columns]
        for c in df.columns: df[c]=df[c].map(lambda v:v.strip() if isinstance(v,str) else v)
        result[name]=df
    return result

def text(v): return '' if pd.isna(v) else str(v).strip()
def rows(df,col,values): return df[df[col].map(text).isin(values)].copy()

@st.cache_data(show_spinner='Preparing historical examples...')
def prepare_examples(associations, links_data, bom_data):
    ac = associations.copy()
    ac['Production Sheet'] = ac['Production Sheet'].map(text)
    ac['Commercial Code'] = ac['Commercial Code'].map(text)
    ac = ac[ac['Commercial Code'].str.startswith('FBCA')]
    code_sets = ac.groupby('Production Sheet')['Commercial Code'].agg(lambda x: frozenset(x))
    l = links_data.copy()
    l['Production Sheet'] = l['Production Sheet'].map(text)
    l['Production Order'] = l['Production Order'].map(text)
    b = bom_data.copy()
    b['Production Order'] = b['Production Order'].map(text)
    b['Item Code'] = b['Item Code'].map(text)
    joined = l[['Production Sheet','Production Order']].drop_duplicates().merge(b[['Production Order','Item Code','Item Code Description']],on='Production Order',how='inner')
    joined = joined[joined['Item Code'] != '']
    parts = joined.groupby('Production Sheet')['Item Code'].agg(lambda x: frozenset(x))
    descriptions = dict(zip(joined['Item Code'],joined['Item Code Description'].map(text)))
    return [(str(k),code_sets[k],parts[k]) for k in code_sets.index.intersection(parts.index) if code_sets[k] and parts[k]], descriptions

pdf_ready = False
detected_codes = set()
visual_codes = None
st.caption('Proof of concept · Uses historical production records; results are not an approved BOM.')
with st.expander('Pilot scope and data sources'):
    st.markdown('**Current pilot:** BP 100 HE. The six families named in the first survey response are BP 100, BP 100 H, BP 100 HE, BP 100 HSER, BP 100 HLA and BP 100 HXL. The full subfamily mapping is still to be confirmed.')
    st.markdown('**Current data:** local Excel exports of historical engineering BOMs, production BOMs and routings. This app does not currently connect to AS/400 or SAP. AS/400 is the existing ERP; its replacement by SAP is planned for 1 August 2027, with the scope of that date and the future interface still to be confirmed.')
    st.markdown('**Review before release:** check that the confirmed OCL configuration matches the applicable approved rules, and that the BOM and routing match those rules. Approved rules, quantities per machine and the release process are not yet established in this prototype.')
    st.caption('Project scope and review requirements include one survey response and require confirmation with the responsible teams.')
with st.expander('Pilot testing: record feedback', expanded=False):
    st.caption('Test with actual historical customer checklists across machine variants and compare with the confirmed production sheet and BOM. Use approved data only. The app does not send this feedback automatically.')
    feedback_template = pd.DataFrame(columns=['Test case ID', 'OCL revision', 'Machine variant', 'Expected machine code', 'Suggested machine code', 'OCL field or BOM item', 'Expected value', 'Actual value', 'Issue or feedback', 'Source / reference', 'Reviewer', 'Status'])
    st.download_button('Download pilot feedback template (CSV)', feedback_template.to_csv(index=False).encode('utf-8-sig'), file_name='BP100_HE_pilot_feedback_template.csv', mime='text/csv')
st.subheader('01 · Choose the order information')
input_mode = st.radio('Order input', ['Upload checklist PDF', 'Purchase order without checklist', 'Enter configuration manually'], horizontal=True, label_visibility='collapsed')
f = None
form_values = {}
purchase_order = None
if input_mode == 'Purchase order without checklist':
    purchase_order = st.file_uploader('Purchase order PDF (optional reference)', type='pdf', key='purchase_order_upload', help='The PDF is a reference only; the app does not extract its contents.')
    st.info('Enter the machine configuration manually using the purchase order. The app does not read or interpret the purchase order PDF.')
    if purchase_order:
        st.caption('Reference attached: ' + purchase_order.name + '. It remains in this session and is not included in the download.')
    pdf_ready = True
elif input_mode == 'Enter configuration manually':
    pdf_ready = True
else:
    f = st.file_uploader('Drag and drop a checklist PDF',type='pdf', key='ocl_upload')
    if f:
        try:
            reader=PdfReader(BytesIO(f.getvalue()))
            if reader.is_encrypted and not reader.decrypt(''): raise ValueError('Password-protected PDF')
            content='\n'.join(p.extract_text() or '' for p in reader.pages)
            header_text = ' '.join((reader.pages[0].extract_text() or '').split()) if reader.pages else ''
            family_match = re.search(r'BP\s*100\s*(HXL|HSER|HLA|HE|H)\s*Rev\.', header_text, re.IGNORECASE)
            if family_match and family_match.group(1).upper() != 'HE':
                st.error('This checklist is for BP 100 ' + family_match.group(1).upper() + '. The available BOM data and models currently support BP 100 HE only.')
                st.stop()
            fields=reader.get_fields() or {}
            form_values = extract_rev08_form_values(fields, header_text)
            detected_codes=extract_codes(fields)
            if form_values.get('variant'):
                detected_codes.add(form_values['variant'])
            try:
                interactive_connection = extract_rev08_connection(reader, fields, f.getvalue(), header_text)
            except Exception:
                interactive_connection = None
            if interactive_connection:
                detected_codes.add(interactive_connection)
            note_field = fields.get('Notes') or {}
            if str(note_field.get('/FT')) == '/Tx' and note_field.get('/V'):
                form_values['notes'] = str(note_field['/V']).strip()
            try:
                visual_codes = extract_visual_codes(f.getvalue())
            except Exception:
                visual_codes = None
            if visual_codes is not None:
                detected_codes = visual_codes
            values=[(k,text(v.get('/V'))) for k,v in fields.items() if v.get('/V') is not None and text(v.get('/V')) not in ('','/Off')]
            if len(reader.pages) == 0: raise ValueError('PDF has no pages')
            pdf_ready = True
            st.success(f'{f.name}: {len(reader.pages)} pages read')
            if values:
                with st.expander('View PDF form fields'):
                    st.dataframe(pd.DataFrame(values,columns=['PDF field','Value']),hide_index=True,use_container_width=True)
            with st.expander('View extracted PDF text'): st.text_area('PDF text',content,height=200,disabled=True)
        except Exception as exc: st.error(f'Cannot read PDF: {exc}')
if not pdf_ready:
    st.info('Upload a readable order checklist PDF to continue.')
    st.stop()
if f and os.environ.get('BOM_LOCAL_LLM_TEST') == '1':
    with st.expander('Experimental local LLM: analyse PDF text', expanded=False):
        st.warning('Test only: use approved or anonymised documents. The extracted PDF text is sent to an Ollama server on this app server (127.0.0.1). Confirm the model runs locally under your IT policy. This does not read checkboxes or automatically change any selection.')
        llm_model = st.text_input('Approved local Ollama model name', key='local_llm_model', placeholder='Enter an installed local model name')
        if st.button('Analyse extracted PDF text', key='run_local_llm'):
            try:
                from local_llm_test import analyse_text
                with st.spinner('Analysing PDF text locally...'):
                    suggestions, truncated = analyse_text(content, llm_model)
                if truncated:
                    st.warning('Only the first 25,000 characters were analysed.')
                st.warning('Unverified suggestions only. An exact quote does not prove an option was selected; compare every result with the document. Nothing was applied to the configuration or BOM.')
                if suggestions:
                    st.dataframe(pd.DataFrame(suggestions), hide_index=True, use_container_width=True)
                else:
                    st.info('No suggestions with exact text evidence were returned. Text-only analysis cannot establish checkbox states.')
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
if input_mode == 'Enter configuration manually':
    st.info('Enter the variant, electrical connection and selected options from the available order information below.')
elif input_mode == 'Purchase order without checklist':
    st.caption('If the purchase order does not specify a required selection, obtain clarification before proceeding. No unspecified option is inferred.')
elif visual_codes is not None:
    st.success('Supported configuration codes read from the checklist: ' + ', '.join(sorted(visual_codes)))
    st.caption('Supported BP 100 HE revision 07/08 code selections were read. Other details and notes may still need to be entered.')
    if not fields:
        st.warning('This PDF has no readable interactive form fields. Handwritten or flattened order details and notes may be invisible to text extraction. Inspect the original PDF and enter all relevant notes and details manually; they may change the BOM.')
else:
    st.warning('Automatic checkbox recognition was not reliable for this PDF. Select the configuration below.')
    if f and interactive_connection:
        st.warning('The interactive machine and connection fields may be prefilled, but option selections have not been read completely. Check every option and any notes against the original PDF.')
try: data=load()
except Exception as exc: st.error(f'Unable to load input data: {exc}'); st.stop()
headers=data['headers']
all_codes = sorted({text(v) for v in data['assoc']['Commercial Code'] if text(v).startswith('FBCA')})
if visual_codes is not None and visual_codes.difference(all_codes):
    st.error('Detected codes are missing from the available historical data: ' + ', '.join(sorted(visual_codes.difference(all_codes))) + '. The configuration cannot be processed automatically.')
    st.stop()
variant_codes = [v for v in ['FBCA0000','FBCA0001','FBCA0002'] if v in all_codes]
variant_names = {'FBCA0000':'BP 100 HE · manual','FBCA0001':'BP 100 HSE · semi-automatic','FBCA0002':'BP 100 HAE · automatic'}
connections = [c for c in all_codes if c.startswith('FBCA02')]
connection_labels = ['200V 1-phase 50Hz','220V 1-phase 50Hz','230V 1-phase 50Hz','240V 1-phase 50Hz','200V 3-phase 50Hz','220V 3-phase 50Hz','230V 3-phase 50Hz','240V 3-phase 50Hz','380V 3-phase +N 50Hz','400V 3-phase +N 50Hz','415V 3-phase +N 50Hz','110V 1-phase 60Hz','200V 1-phase 60Hz','220V 1-phase 60Hz','230V 1-phase 60Hz','240V 1-phase 60Hz','200V 3-phase 60Hz','208V 3-phase 60Hz UL','220V 3-phase 60Hz','230V 3-phase 60Hz','240V 3-phase 60Hz','380V 3-phase +N 60Hz','400V 3-phase +N 60Hz','415V 3-phase +N 60Hz']
connection_names = {f'FBCA{201+i:04d}':name for i,name in enumerate(connection_labels)}
option_labels = ['Wall installation for toilet bowl connection','LCD display control panel','High pressure washing technology','AISI 316L chamber','Device main switch','HEPA H14 air filtering','Electrical heated drying and cooling','Chemical dosing pump','Infra-red switch (LED)','Infra-red switch (LCD)','Emergency stop button','ST1 external printer','RS232 port','Independent monitoring system','Manual emptier conversion kit','Flushing kit','USB predisposition']
option_names = {f'FBCA{1000+i:04d}':name for i,name in enumerate(option_labels)}
options = [c for c in all_codes if c.startswith('FBCA1')]
pdf_key = hashlib.sha256(f.getvalue()).hexdigest() if f else ('po_' + hashlib.sha256(purchase_order.getvalue()).hexdigest() if purchase_order else ('po_manual' if input_mode == 'Purchase order without checklist' else 'manual'))
detected_variants = sorted(detected_codes.intersection(variant_codes))
detected_connections = sorted(detected_codes.intersection(connections))
detected_options = sorted(detected_codes.intersection(options))
auto_recognized = visual_codes is not None and len(detected_variants) == 1 and len(detected_connections) == 1 and set(detected_codes).issubset(set(variant_codes) | set(connections) | set(options))
if not f:
    st.subheader('02 · Review configuration')
if detected_codes:
    st.caption('Codes detected from the uploaded checklist: ' + ', '.join(sorted(detected_codes)))
if len(detected_variants) > 1 or len(detected_connections) > 1:
    st.warning('Multiple variants or electrical connections were found. Choose the correct values manually.')
if not detected_codes and input_mode == 'Upload checklist PDF':
    st.warning('No explicit commercial codes could be mapped from the interactive PDF fields. Select the configuration manually; printed option lists are not treated as selections.')
selection_label = ('Change or add checklist selections' if auto_recognized else
                   'Complete missing checklist selections' if f else 'Enter or change checklist selections')
detail_keys = ['panel_', 'installation_', 'drain_', 'diameter_', 'power_']
missing_saved_details = any(not st.session_state.get(key + pdf_key) for key in detail_keys)
if st.session_state.get('panel_' + pdf_key) == 'LCD':
    missing_saved_details = missing_saved_details or not st.session_state.get('panel_language_' + pdf_key, '').strip()
with st.expander(selection_label, expanded=not auto_recognized or missing_saved_details):
    st.caption('Enter or change selections from the available order information. The PDF itself is not modified; the selections below determine the results shown by this app.')
    col_variant,col_power = st.columns(2)
    with col_variant:
        selected_variant = st.selectbox('Machine variant from checklist',variant_codes,index=variant_codes.index(detected_variants[0]) if len(detected_variants)==1 else None,format_func=lambda c: variant_names.get(c,c)+' ('+c+')',placeholder='Select the variant',key='variant_'+pdf_key)
    with col_power:
        selected_connection = st.selectbox('Electrical connection code',connections,index=connections.index(detected_connections[0]) if len(detected_connections)==1 else None,placeholder='Select the electrical connection',format_func=lambda c: connection_names.get(c,'Unknown connection')+' ('+c+')',key='connection_'+pdf_key)
    selected_options = st.multiselect('Selected option codes',options,default=detected_options,format_func=lambda c: option_names.get(c,'Other option')+' ('+c+')',help='Only select options marked on the uploaded checklist.',key='options_'+pdf_key)
    st.markdown('**Required BP 100 HE details**')
    st.caption('Clearly identified form values are prefilled. Other details must be entered. These fields do not yet change the BOM or routing; workshop requirements need engineering confirmation.')
    detail_left, detail_right = st.columns(2)
    with detail_left:
        control_panel = st.selectbox('Control panel *', ['LED', 'LCD'], index=['LED', 'LCD'].index(form_values['control_panel']) if form_values.get('control_panel') in ['LED', 'LCD'] else None, placeholder='Not specified', key='panel_'+pdf_key)
        panelling = st.selectbox('Closing panelling', ['No', 'Yes'], index=['No', 'Yes'].index(form_values['panelling']) if form_values.get('panelling') in ['No', 'Yes'] else None, placeholder='Not specified', key='panelling_'+pdf_key)
        installation = st.selectbox('Installation type *', ['Stand Alone', 'Recessed wall'], index=['Stand Alone', 'Recessed wall'].index(form_values['installation']) if form_values.get('installation') in ['Stand Alone', 'Recessed wall'] else None, placeholder='Not specified', key='installation_'+pdf_key)
        drain_position = st.selectbox('Drain position *', ['To the wall', 'To the floor'], index=['To the wall', 'To the floor'].index(form_values['drain_position']) if form_values.get('drain_position') in ['To the wall', 'To the floor'] else None, placeholder='Not specified', key='drain_'+pdf_key)
        drain_diameter = st.selectbox('Drain diameter *', ['90 mm', '110 mm'], index=['90 mm', '110 mm'].index(form_values['drain_diameter']) if form_values.get('drain_diameter') in ['90 mm', '110 mm'] else None, placeholder='Not specified', key='diameter_'+pdf_key)
        power = st.selectbox('Power *', ['3.05 kW', '5.05 kW'], index=['3.05 kW', '5.05 kW'].index(form_values['power']) if form_values.get('power') in ['3.05 kW', '5.05 kW'] else None, placeholder='Not specified', key='power_'+pdf_key)
    with detail_right:
        customer = st.text_input('Customer', key='customer_'+pdf_key)
        order_number = st.text_input('Order number', key='order_number_'+pdf_key)
        order_quantity = st.number_input('Order quantity', min_value=1, value=None, step=1, placeholder='Not specified', key='order_quantity_'+pdf_key)
        installation_country = st.text_input('Installation country', key='installation_country_'+pdf_key)
        destination_country = st.text_input('Destination country', key='destination_country_'+pdf_key)
        packaging = st.text_input('Packaging', key='packaging_'+pdf_key, help='Packaging may require additional production BOM materials. The prototype does not add these automatically.')
        manual_language = st.text_input('User manual language', key='manual_language_'+pdf_key)
        panel_language = st.text_input('Control panel language (required for LCD)', key='panel_language_'+pdf_key, help='Production may need this information for software setup; its relation to software language must be confirmed.')
        checklist_notes = st.text_area('Checklist notes', value=form_values.get('notes', ''), key='notes_'+pdf_key, help='Notes may affect the BOM and require technical review.')
required_inputs = {'machine variant': selected_variant, 'electrical connection': selected_connection,
    'control panel': control_panel, 'installation type': installation, 'drain position': drain_position,
    'drain diameter': drain_diameter, 'power': power}
if control_panel == 'LCD':
    required_inputs['LCD control panel language'] = panel_language.strip()
missing_inputs = [name for name, value in required_inputs.items() if not value]
from technical_code_candidates import machine_candidates
candidates = machine_candidates(data['headers'], data['assoc'], selected_variant, selected_connection, power)
unique_machine_candidate = candidates[0]['code'] if len(candidates) == 1 else None
dashboard_slot = st.container()
with dashboard_slot:
    st.markdown('''<div class="dashboard-title"><div class="dash-eyebrow">BP 100 HE &nbsp; | &nbsp; Pilot dashboard</div><div class="dash-name">Order and BOM quality overview</div><div class="dash-subtitle">Current order status and historical test results</div></div>''', unsafe_allow_html=True)
    st.markdown('**Current order · review status**')
    d1, d2, d3, d4 = st.columns(4)
    d1.metric('Required fields entered', f'{len(required_inputs) - len(missing_inputs)}/{len(required_inputs)}', help='Only the current prototype checks are counted; this is not proof that the complete OCL was read.')
    d2.metric('Historical machine-code candidates', len(candidates), help='Candidates are unverified; even one match is not an approved technical code.')
    d3.metric('Checklist notes', 'Entered' if checklist_notes.strip() else 'Not entered', help='Not entered does not prove that the original OCL has no notes.')
    d4.metric('Release status', 'Not approved', help='Engineering review remains required for every proposal.')
    if missing_inputs:
        st.warning('Missing required fields: ' + ', '.join(missing_inputs) + '.')
    st.caption('Per-order BOM accuracy: not measured. Options, packaging, notes and the technical code still require review; a complete field count does not establish correctness.')
st.markdown('**Historical technical machine-code candidates**')
if candidates:
    st.dataframe(pd.DataFrame([{'Technical code': item['code'], 'Description': item['description'], 'Historical production sheets': ', '.join(item['sheets'])} for item in candidates]), hide_index=True, use_container_width=True)
    st.caption('Matches use the same historical sheet and machine code for variant, electrical connection and power. Other details, revisions and applicability are not validated. These are historical candidates, not approved mappings.')
    if unique_machine_candidate:
        st.info('One historical candidate was found and is included as an unverified candidate in the draft PDF: ' + unique_machine_candidate)
    else:
        st.warning('Several technical codes match. No code is automatically selected; clarify the correct code with engineering.')
else:
    st.info('No unique candidate can be determined from the available historical data. Select variant, connection and power, or clarify the technical code with engineering.')
from production_sheet_pdf import make_production_sheet
production_sheet_data = {
    'customer': customer, 'order_number': order_number, 'order_quantity': order_quantity,
    'variant': variant_names.get(selected_variant, selected_variant), 'variant_code': selected_variant, 'technical_machine': unique_machine_candidate,
    'connection': (connection_names.get(selected_connection, selected_connection) + ' (' + selected_connection + ')') if selected_connection else None,
    'power': power, 'panel': control_panel, 'panel_language': panel_language if control_panel == 'LCD' else 'Not applicable',
    'installation': installation, 'drain_position': drain_position, 'drain_diameter': drain_diameter,
    'panelling': panelling, 'installation_country': installation_country, 'destination_country': destination_country,
    'manual_language': manual_language, 'packaging': packaging, 'notes': checklist_notes,
    'options': [code + ' | ' + option_names.get(code, 'Description not available') for code in selected_options],
    'source': 'checklist_pdf' if f else ('purchase_order' if input_mode == 'Purchase order without checklist' else 'manual'), 'filename': f.name if f else (purchase_order.name if purchase_order else None),
}
st.warning('PACKAGING REVIEW: Packaging can require additional production BOM material (for example a wooden cage). This prototype records the selection but does not automatically determine or add packaging components. Confirm the requirement and item codes with the responsible team.')
st.subheader('Production sheet PDF')
st.caption('Draft based on the AS/400 examples. Unavailable ERP fields and traceable components are marked; the document is not an approved production sheet or complete BOM.')
st.download_button('Download draft production sheet (PDF)', make_production_sheet(production_sheet_data), file_name='BP100_HE_production_sheet_DRAFT.pdf', mime='application/pdf')

if missing_inputs:
    st.warning('Required information still missing: ' + ', '.join(missing_inputs) + '. Complete the fields above to continue.')
    st.stop()
st.success('The listed workshop fields have been entered. Review the selections; this does not validate the configuration or BOM.')
if input_mode == 'Purchase order without checklist':
    selection_hash = hashlib.sha256(json.dumps([selected_variant, selected_connection, sorted(selected_options)]).encode('utf-8')).hexdigest()
    po_confirmed = st.checkbox('I have checked the purchase order and confirmed the variant, electrical connection and complete option selection, including any absence of options.', key='po_confirmed_'+pdf_key+'_'+selection_hash)
    if not po_confirmed:
        st.warning('Confirm the complete configuration from the purchase order before calculating. If information is missing, clarify it first.')
        st.stop()
if not selected_variant or not selected_connection:
    st.info('Select the machine variant and electrical connection to see similar historical orders.')
    st.stop()
selected_codes = [selected_variant, selected_connection, *selected_options]
st.markdown('**Configuration used for this analysis**')
st.write(', '.join(selected_codes))
comparison_status = 'not_provided'
if f:
    with st.expander('Compare checklist with purchase order (optional)', expanded=False):
        po_compare = st.file_uploader('Purchase order PDF', type='pdf', key='po_compare_'+pdf_key, help='The document is a reference only. Enter its codes manually; it is not read automatically.')
        if po_compare:
            st.caption('The PDF is not parsed. Enter the complete commercial-code selection from the purchase order; missing or unclear information must be clarified.')
            po_variant = st.selectbox('Purchase order: machine variant', variant_codes, index=None, key='compare_variant_'+pdf_key)
            po_connection = st.selectbox('Purchase order: electrical connection', connections, index=None, key='compare_connection_'+pdf_key)
            po_options = st.multiselect('Purchase order: selected options', options, key='compare_options_'+pdf_key)
            po_hash = hashlib.sha256(json.dumps([po_variant, po_connection, sorted(po_options), hashlib.sha256(po_compare.getvalue()).hexdigest()]).encode()).hexdigest()
            po_complete = st.checkbox('I have checked all listed commercial codes and confirmed the option selection, including any absence of options.', key='compare_confirm_'+po_hash)
            if not po_complete or not po_variant or not po_connection:
                comparison_status = 'incomplete'
                st.warning('Complete and confirm the purchase order selection before comparing it with the checklist.')
            else:
                po_codes = {po_variant, po_connection, *po_options}
                ocl_codes = set(selected_codes)
                missing_on_po = sorted(ocl_codes - po_codes)
                missing_on_ocl = sorted(po_codes - ocl_codes)
                comparison_status = 'mismatch' if missing_on_po or missing_on_ocl else 'match'
                if comparison_status == 'match':
                    st.success('The manually confirmed purchase order codes match the current checklist selection. Other fields and non-commercial items were not compared.')
                else:
                    st.warning('The commercial-code selections differ. Clarify the differences before using the technical BOM preview.')
                    st.write('Only in current checklist selection:', ', '.join(missing_on_po) or 'None')
                    st.write('Only in purchase order:', ', '.join(missing_on_ocl) or 'None')
                st.caption('This comparison covers only manually entered commercial codes, not quantities, customer details, non-price-relevant items or free text.')
if selected_variant != 'FBCA0002' and {'FBCA1008', 'FBCA1009'}.intersection(selected_options):
    st.warning('The BP 100 HE checklist describes infrared door-opening options as available only for the fully automatic variant. Please review this selection; the prototype does not enforce CPQ rules.')
configuration_export = {'input_source': 'checklist_pdf' if f else ('purchase_order' if input_mode == 'Purchase order without checklist' else 'manual'), 'pdf_filename': f.name if f else None,
    'purchase_order_filename': purchase_order.name if purchase_order else None,
    'purchase_order_sha256': hashlib.sha256(purchase_order.getvalue()).hexdigest() if purchase_order else None,
    'detected_pdf_codes': sorted(detected_codes) if f else [],
    'variant': selected_variant, 'electrical_connection': selected_connection, 'options': selected_options,
    'technical_machine_candidate_unverified': unique_machine_candidate,
    'additional_details_not_used_in_bom': {'control_panel': control_panel, 'closing_panelling': panelling,
        'installation_type': installation, 'drain_position': drain_position, 'drain_diameter': drain_diameter,
        'power': power, 'installation_country': installation_country, 'destination_country': destination_country,
        'packaging': packaging, 'user_manual_language': manual_language, 'control_panel_language': panel_language,
        'customer': customer, 'order_number': order_number, 'order_quantity': order_quantity, 'notes': checklist_notes}}
st.download_button('Download checklist selections', json.dumps(configuration_export, ensure_ascii=False, indent=2).encode('utf-8'), file_name='BP100_HE_checklist_selections.json', mime='application/json', help='The optional details are recorded for review; they do not currently affect the BOM or routing.')
if f and detected_codes:
    recognized = set(detected_codes) & (set(variant_codes) | set(connections) | set(options))
    if set(selected_codes) != recognized:
        st.info('Your current selections differ from the detected PDF values. The analysis uses your current selections, not the original PDF values.')
with st.expander('Review required BP 100 HE details and technical BOM combination', expanded=False):
    st.caption('Workshop-based draft checks for BP 100 HE only. Some form values can be read; remaining details must be entered. Confirm applicability with engineering.')
    required_details = {'control panel': control_panel, 'installation type': installation, 'drain position': drain_position,
        'drain diameter': drain_diameter, 'power': power}
    if control_panel == 'LCD':
        required_details['LCD control panel language'] = panel_language.strip()
    missing_details = [name for name, value in required_details.items() if not value]
    if missing_details:
        st.warning('Additional details to confirm: ' + ', '.join(missing_details) + '. Open the checklist selections above to enter them.')
    else:
        st.success('The workshop-listed technical detail fields have been entered. This does not validate the configuration or its BOM.')
    configuration_conflicts = []
    if power == '5.05 kW' and selected_connection == 'FBCA0212':
        configuration_conflicts.append('power / connection')
        st.warning('The checklist describes FBCA0212 (110 V, 60 Hz) as limited to 3.05 kW. Review the selection.')
    if power == '3.05 kW' and selected_connection == 'FBCA0218':
        configuration_conflicts.append('power / UL connection')
        st.warning('The checklist describes FBCA0218 (208 V, UL) as limited to 5.05 kW. Review the selection.')
    if selected_variant == 'FBCA0000' and 'FBCA1002' in selected_options:
        configuration_conflicts.append('manual door / high pressure')
        st.warning('The checklist describes high-pressure washing as unavailable for the manual door variant. Review the selection.')
    if checklist_notes.strip():
        configuration_conflicts.append('unreviewed checklist notes')
        st.warning('Checklist notes contain text. A person must assess whether it affects the technical configuration or is a special request.')
    from bom_assembly import technical_roots, build_assembly_preview
    root_frame = technical_roots(data['technical'])
    root_labels = dict(zip(root_frame['Item Code'], root_frame['Item Code Description']))
    root_codes = sorted(root_labels)
    st.markdown('**Exploratory combination of technical BOMs**')
    st.warning('Select the technical codes manually against AS/400. No commercial-to-technical mapping, validity dates, unit conversions, multi-level explosion, production flags or per-machine normalization are validated by this calculation.')
    historical_mapping = data['assoc'][['Production Sheet', 'Commercial Code', 'Technical Code']].copy()
    historical_mapping['Commercial Code'] = historical_mapping['Commercial Code'].map(text)
    historical_mapping['Technical Code'] = historical_mapping['Technical Code'].map(text)
    historical_mapping = historical_mapping[historical_mapping['Commercial Code'].isin(selected_codes) & historical_mapping['Technical Code'].ne('')]
    if not historical_mapping.empty:
        mapping_summary = historical_mapping.groupby(['Commercial Code', 'Technical Code'], as_index=False)['Production Sheet'].nunique()
        mapping_summary.columns = ['Commercial code', 'Observed technical code', 'Historical sheets']
        mapping_summary['Description in technical BOM export'] = mapping_summary['Observed technical code'].map(root_labels).fillna('Not found as BOM root')
        st.caption('Historical associations below are leads for source verification, not an approved mapping or proof that a code fits this configuration.')
        st.dataframe(mapping_summary, hide_index=True, use_container_width=True)
    machine_root = st.selectbox('Technical machine BOM', root_codes, index=None, placeholder='Select a verified machine code', format_func=lambda c: c + ' | ' + root_labels[c], key='machine_root_'+pdf_key)
    option_roots = st.multiselect('Technical option BOMs', [c for c in root_codes if c != machine_root], format_func=lambda c: c + ' | ' + root_labels[c], key='option_roots_'+pdf_key)
    root_fingerprint = hashlib.sha256(json.dumps([machine_root, sorted(option_roots), sorted(selected_codes)]).encode()).hexdigest()
    roots_verified = st.checkbox('I have checked the machine and all applicable option BOM codes against the source, including options without commercial codes.', key='roots_verified_'+root_fingerprint)
    if machine_root and roots_verified:
        if missing_details or configuration_conflicts or comparison_status in ('incomplete', 'mismatch'):
            st.warning('Complete the BP 100 HE detail review, resolve highlighted conflicts and review notes or purchase order differences before the technical BOM preview.')
        else:
            try:
                summary, contributions = build_assembly_preview(data['technical'], machine_root, option_roots)
                st.error('BOM ALERT ? TECHNICAL PREVIEW ONLY. Source BOM selection, scope and quantities are not validated. Engineering review is required before use.')
                st.caption('Level-1 positions only; signed source quantities are summed once per selected BOM. Zero and negative totals are shown for review. Quantities are not multiplied by order quantity; no units or production approval are inferred.')
                st.dataframe(summary, hide_index=True, use_container_width=True)
                with st.expander('Source positions and signed quantities'):
                    st.dataframe(contributions, hide_index=True, use_container_width=True)
                if any(summary['Net quantity'].map(lambda x: float(x) < 0)):
                    st.error('Negative totals were found. Review missing base parts, quantities, validity and applicability; this output must not be used for production.')
                st.download_button('Download technical BOM preview', summary.to_csv(index=False).encode('utf-8-sig'), file_name='technical_bom_preview.csv', mime='text/csv')
                st.download_button('Download source positions', contributions.to_csv(index=False).encode('utf-8-sig'), file_name='technical_bom_sources.csv', mime='text/csv')
                st.download_button('Download technical BOM preview (XML)', technical_preview_xml(configuration_export, summary, contributions), file_name='BP100_HE_technical_BOM_DRAFT.xml', mime='application/xml', help='Source BOMs and their direct level-1 components plus unverified net quantities. Not a validated SAP import.')
                try:
                    tree_xml = engineering_tree_xml(data['technical'], [machine_root, *option_roots])
                    st.download_button('Download engineering BOM source tree (XML)', tree_xml, file_name='BP100_HE_engineering_BOM_tree_DRAFT.xml', mime='application/xml', help='Source BOMs including nested levels. Source quantities, parent links and validity are not validated or consolidated.')
                except ValueError as exc:
                    st.warning('Engineering BOM source tree could not be exported: ' + str(exc))
            except ValueError as exc:
                st.error(f'The selected technical BOMs cannot be combined: {exc}')
st.error('BOM ALERT ? NOT APPROVED FOR PRODUCTION. All BOM results are exploratory. Missing, extra or incorrect components and quantities cannot be ruled out; engineering must review them against the approved configuration and source BOMs.')
st.subheader('BOM candidate from historical orders')
st.caption('Components and quantities observed in similar orders. Review every line before use.')
if checklist_notes.strip():
    from note_review import item_mentions
    mentions = item_mentions(checklist_notes)
    st.warning('ORDER NOTE REQUIRES REVIEW: checklist notes are not automatically applied to the BOM. A person must decide whether parts or quantities need to be added, removed or changed.')
    if mentions:
        st.caption('Possible item and quantity mentions copied literally from the notes. These are not validated item codes or instructions and were not added to the BOM.')
        st.dataframe(pd.DataFrame(mentions).rename(columns={'item': 'Possible item', 'quantity_text': 'Quantity mentioned', 'source': 'Exact note excerpt'}), hide_index=True, use_container_width=True)
    if os.environ.get('BOM_LOCAL_LLM_TEST') == '1':
        with st.expander('Optional local LLM note review', expanded=False):
            st.warning('This sends the entered note to Ollama on the app server only after you click the button. Use approved or anonymised data. Results require human review and do not change the BOM.')
            note_model = st.text_input('Approved local model for note review', value='llama3.2:1b', key='local_note_model')
            if st.button('Analyse note with local LLM', key='run_local_note_llm'):
                try:
                    from local_note_llm import analyse_note
                    with st.spinner('Analysing the note locally...'):
                        llm_mentions = analyse_note(checklist_notes, note_model)
                    if llm_mentions:
                        st.dataframe(pd.DataFrame(llm_mentions), hide_index=True, use_container_width=True)
                        st.warning('Literal matches do not establish whether an item must be added, removed or replaced. Nothing was applied to the BOM.')
                    else:
                        st.info('No item mentions with exact note evidence were returned. Review the full note manually.')
                except (ValueError, RuntimeError) as exc:
                    st.error(str(exc))
try:
    from bom_proposal import build_examples, propose, backtest
    @st.cache_data(show_spinner='Preparing and testing historical BOM candidates...')
    def prepare_bom_candidate_data(associations, links_data, bom_data):
        records, descriptions = build_examples(associations, links_data, bom_data)
        return records, descriptions, backtest(records, descriptions)
    bom_records, bom_descriptions, evaluation = prepare_bom_candidate_data(data['assoc'], data['links'], data['bom'])
    candidate, candidate_references = propose(set(selected_codes), bom_records, bom_descriptions)
    if candidate_references and candidate:
        candidate_df = pd.DataFrame(candidate)
        candidate_df['Unit of measure'] = 'Not available'
        candidate_df['BOM level'] = 'Not available'
        candidate_df['Rule ID'] = 'Not available'
        from experimental_reference_matching import machine_tree_item_codes
        source_items = machine_tree_item_codes(data['technical'], unique_machine_candidate)
        if source_items is None:
            candidate_df['Machine BOM source evidence'] = 'Not checked'
        else:
            candidate_df['Machine BOM source evidence'] = candidate_df['Item code'].map(lambda code: 'Found in historical machine BOM' if code in source_items else 'Not found in machine BOM; may come from an option')
            st.caption('Source evidence uses the single unverified historical machine-code candidate across all recorded BOM levels. It does not validate revision, quantity, production applicability or option BOMs; items not found may still be required.')
        candidate_df['Review alert'] = candidate_df.apply(lambda r: 'CHECK: component absent from some references; quantity differs' if r['Observed in'] < r['References'] and r['Quantity agreement'] < r['Observed in'] else ('CHECK: component absent from some references' if r['Observed in'] < r['References'] else ('CHECK: historical quantities differ' if r['Quantity agreement'] < r['Observed in'] else 'UNVERIFIED: engineering review required')), axis=1)
        component_risks = (candidate_df['Observed in'] < candidate_df['References']).sum()
        quantity_risks = (candidate_df['Quantity agreement'] < candidate_df['Observed in']).sum()
        if component_risks or quantity_risks:
            st.error(f'BOM ALERT ? {component_risks} component(s) are absent from at least one reference; {quantity_risks} have differing historical quantities. These are risk indicators, not proof of an error.')
        candidate_df = candidate_df[['Item code', 'Description', 'Suggested quantity', 'Unit of measure', 'BOM level', 'Rule ID', 'Quantity agreement', 'Observed in', 'References', 'Quantity range', 'Machine BOM source evidence', 'Review alert']]
        st.warning('Exploratory candidate, not an approved or complete production BOM. Quantities are totals across the linked orders of each reference; order and machine quantities may differ. Verify each component and quantity against engineering data.')
        st.caption('A component is included when it appears in at least half of up to five same-variant historical references. The suggested quantity is the most common observed total; quantity agreement and range show disagreements.')
        st.caption('Unit of measure, BOM level and rule ID are not available for this historical candidate. No approved rule has been applied; do not treat an unavailable value as verified.')
        st.dataframe(candidate_df, hide_index=True, use_container_width=True)
        st.download_button('Download BOM candidate as CSV', candidate_df.to_csv(index=False).encode('utf-8-sig'), file_name='BP100_HE_BOM_candidate.csv', mime='text/csv')
        st.download_button('Download BOM candidate (XML)', historical_candidate_xml(configuration_export, candidate_df, candidate_references), file_name='BP100_HE_BOM_candidate_DRAFT.xml', mime='application/xml', help='Historical candidate and reference orders; component hierarchy and quantities are unverified.')
        from detailed_production_pdf import make_detailed_production_pdf
        detailed_pdf = make_detailed_production_pdf(production_sheet_data, configuration_export, candidates, candidate_df.to_dict('records'), candidate_references)
        st.download_button('Download detailed production sheet and BOM (PDF)', detailed_pdf, file_name='BP100_HE_production_sheet_and_BOM_DRAFT.pdf', mime='application/pdf', help='Draft production sheet with entered details, unverified technical-code candidates, historical references and BOM candidate positions.')
        with st.expander('Experimental: compare references with matching connection and power', expanded=False):
            st.warning('Exploratory comparison only. A stricter historical match did not improve both component metrics in the available held-out test and covered only some cases. Do not use it as an approved BOM or assume it is more accurate.')
            st.caption('The test requires the same commercial electrical-connection code and power inferred from the historical machine description. Missing or ambiguous values are excluded. Technical codes, BOM validity, quantities and options still need engineering review.')
            match_key = 'experimental_match_' + hashlib.sha256(json.dumps([sorted(selected_codes), power]).encode()).hexdigest()
            if st.button('Compare stricter historical match', key='run_match_'+pdf_key):
                from experimental_reference_matching import attach_historical_power, propose_matched
                historical_with_power = attach_historical_power(bom_records, headers)
                st.session_state[match_key] = propose_matched(set(selected_codes), power, historical_with_power, bom_descriptions)
            comparison = st.session_state.get(match_key)
            if comparison is not None:
                matched_items, matched_refs = comparison
                if not matched_refs:
                    st.warning('No references meet the stricter criteria. The test does not silently fall back or assume a match.')
                else:
                    baseline_codes = set(candidate_df['Item code'])
                    matched_codes = {item['Item code'] for item in matched_items}
                    st.write(f'{len(matched_refs)} matching historical references; {len(matched_codes - baseline_codes)} additional and {len(baseline_codes - matched_codes)} omitted component types relative to the current candidate.')
                    st.dataframe(pd.DataFrame(matched_items), hide_index=True, use_container_width=True)
                    st.caption('The comparison may include the current or related historical order. Different items or amounts are not proof of an error or improvement.')
        with st.expander('Show historical references used for this candidate'):
            st.dataframe(pd.DataFrame([{'Production sheet': row['sheet'], 'Code similarity': round(score*100, 1), 'Missing requested codes': ', '.join(sorted(set(selected_codes)-row['codes'])), 'Additional codes': ', '.join(sorted(row['codes']-set(selected_codes))), 'Production orders': ', '.join(sorted(row['orders']))} for score, row in candidate_references]), hide_index=True, use_container_width=True)
    else:
        st.info('No usable historical BOMs for the selected machine variant were found.')
        from detailed_production_pdf import make_detailed_production_pdf
        detailed_pdf = make_detailed_production_pdf(production_sheet_data, configuration_export, candidates, [], candidate_references)
        st.download_button('Download detailed production sheet (PDF)', detailed_pdf, file_name='BP100_HE_production_sheet_DRAFT.pdf', mime='application/pdf', help='No usable BOM candidate was found; the PDF states that BOM positions are unavailable.')
    def show_percent(value):
        return f'{value:.0%}' if value is not None else '—'
    with dashboard_slot:
        st.markdown('**Historical test of the current BOM candidate method**')
        m1, m2, m3, m4 = st.columns(4)
        m1.metric('Component precision', show_percent(evaluation['precision']), help='Share of suggested component types present in the held-out historical BOMs.')
        m2.metric('Component completeness', show_percent(evaluation['recall']), help='Share of component types in the held-out historical BOMs that were suggested.')
        m3.metric('Quantity agreement', show_percent(evaluation['quantity_accuracy']), help='Only among correctly suggested components: share with an exactly matching historical summed quantity.')
        m4.metric('Complete BOM with quantities', show_percent(evaluation['exact_quantity']), help='Share of covered historical test sheets where all components and summed quantities matched exactly.')
        chart_col, coverage_col = st.columns([2.2, 1])
        with chart_col:
            st.markdown('**Component results vs. proposed target**')
            from pilot_dashboard import historical_performance_chart
            performance_chart = historical_performance_chart(evaluation)
            if performance_chart is not None:
                st.altair_chart(performance_chart, use_container_width=True)
                st.caption('Blue: historical test result · Gold dashed line: proposed 90% target.')
            else:
                st.info('Component metrics are unavailable for this historical test.')
        with coverage_col:
            st.markdown('**Historical test coverage**')
            st.metric('Comparable held-out sheets', f"{evaluation['covered']} / {evaluation['test']}", help='Cases with at least one comparable training reference; excluded source records are not included.')
            st.caption(f"Training sheets: {evaluation['train']}. Quantity agreement only covers correctly suggested components.")
        st.caption(f"Historical coverage: {evaluation['covered']} of {evaluation['test']} held-out sheets had comparable training references ({evaluation['train']} training sheets). Sheets with missing linked BOMs, missing quantities or negative quantities are excluded. Shared production orders and identical code sets are grouped; other relationships may remain. These are aggregate historical results, not accuracy or probability for the current order.")
        st.markdown('**Proposed pilot target: 90% for both component precision and completeness**')
        st.caption('Quantities and complete BOMs are measured separately. The target and acceptance criteria still require agreement and independent, approved OCL/BOM test cases.')
        p, r = evaluation['precision'], evaluation['recall']
        if p is None or r is None:
            st.warning('The proposed 90% pilot target cannot be assessed because the required historical metrics are unavailable.')
        elif p >= 0.9 and r >= 0.9:
            st.info('Both proposed thresholds were reached in this historical test only. This does not approve any BOM or replace independent technical validation.')
        else:
            st.error('The proposed pilot target is not reached in this historical test: component precision ' + show_percent(p) + ', component completeness ' + show_percent(r) + '. Do not use these results as a production BOM.')
except Exception as exc:
    st.warning(f'BOM candidate or its historical test could not be prepared: {exc}')
st.subheader('Historical model performance')
try:
    from ml_models import train_models
    examples, descriptions = prepare_examples(data['assoc'], data['links'], data['bom'])
    historical_model = train_models(examples)
    historical_metrics = historical_model['metrics']['XGBoost']
    precision_card, recall_card, match_card = st.columns(3)
    precision_card.metric('Predicted parts found', f"{historical_metrics['Precision']:.0%}", help='Of model-predicted components, the share also found in historical test orders.')
    recall_card.metric('Historical parts found', f"{historical_metrics['Recall']:.0%}", help='Of the evaluated components actually present in historical test orders, the share predicted by the model.')
    match_card.metric('Exact match of evaluated parts', f"{historical_metrics['Exact match']:.0%}", help='Share of historical test orders where all evaluated component-presence decisions matched.')
    st.caption(f"Historical XGBoost test on {historical_model['test_count']} held-out sheets, covering {len(historical_model['targets'])} modeled component types at a 50% threshold. Related orders may still appear in training and test sets.")
    st.warning('These are aggregate historical component-presence results, not a probability that this OCL produces a correct or complete BOM. They exclude quantities and unmodeled components. The historical reference BOM below is not a generated BOM.')
except Exception as exc:
    st.info(f'Historical model metrics are currently unavailable: {exc}')
query = set(selected_codes)
association_data = data['assoc'].copy()
association_data['Production Sheet'] = association_data['Production Sheet'].map(text)
association_data['Commercial Code'] = association_data['Commercial Code'].map(text)
sets = association_data.groupby('Production Sheet')['Commercial Code'].agg(lambda vals: set(vals))
reference_candidates = []
for reference, codeset in sets.items():
    if selected_variant not in codeset: continue
    score = len(query & codeset) / len(query | codeset) if query | codeset else 0
    reference_candidates.append((score, reference, sorted(query - codeset), sorted(codeset - query)))
reference_candidates.sort(key=lambda item: (-item[0], item[1]))
if not reference_candidates:
    st.warning('No historical reference with this machine variant was found.')
    st.stop()
reference_candidates = reference_candidates[:10]
reference_frame = pd.DataFrame([{'Reference sheet': r, 'Code similarity': score, 'Requested codes absent': ', '.join(missing) or 'None', 'Additional historical codes': ', '.join(extra) or 'None'} for score,r,missing,extra in reference_candidates])
st.subheader('03 · Choose a reference')
st.caption('Ranked by shared commercial codes. Similarity is not a technical validation; additional and missing codes must be reviewed.')
st.dataframe(reference_frame, hide_index=True, use_container_width=True, column_config={'Code similarity':st.column_config.ProgressColumn('Code similarity',min_value=0,max_value=1,format='%.2f')})
reference_options = [item[1] for item in reference_candidates]
sheet = st.selectbox('Inspect a suggested historical reference',reference_options,format_func=lambda r: r+' | '+text(headers.loc[headers['Production Sheet'].map(text)==r,'Machine Code Description'].iloc[0]) if (headers['Production Sheet'].map(text)==r).any() else r)
selected_reference = next(item for item in reference_candidates if item[1] == sheet)
missing_reference, extra_reference = selected_reference[2], selected_reference[3]
st.error('BOM ALERT ? HISTORICAL REFERENCE ONLY. This BOM belongs to another order and may have missing, extra or incorrect components and quantities for the current order. It is not an approved generated BOM.')
if missing_reference or extra_reference:
    st.error('CONFIGURATION DIFFERENCE ? Missing requested codes: ' + (', '.join(missing_reference) or 'none') + '; additional historical codes: ' + (', '.join(extra_reference) or 'none') + '. Review the differences before using this reference.')
h=rows(headers,'Production Sheet',{sheet}).iloc[0]
links=rows(data['links'],'Production Sheet',{sheet}); association=rows(data['assoc'],'Production Sheet',{sheet})
ids={text(x) for x in links['Production Order']}; codes={text(x) for x in links['Machine/Optional Item Code']}
bom=rows(data['bom'],'Production Order',ids); routing=rows(data['routing'],'Item Code',codes)
config=rows(data['config'],'Production sheet',{sheet}); notes=rows(data['notes'],'Production Sheet',{sheet})
missing_orders=sorted(ids-{text(x) for x in bom['Production Order']}); missing_routing=sorted(codes-{text(x) for x in routing['Item Code']})
tech=data['technical']; machine=text(h['Machine Code']); roots=list(tech.index[(tech['Item Code'].map(text)==machine)&(tech['Level'].map(text)=='0')]); blocks=[]
for idx in roots:
    subsequent=tech.index[(tech.index>idx)&(tech['Level'].map(text)=='0')]; end=subsequent[0] if len(subsequent) else len(tech); blocks.append(tech.iloc[idx:end])
technical=pd.concat(blocks,ignore_index=True) if blocks else tech.iloc[0:0]
issues=[{'Category':'Missing production BOM','Reference':x,'Next step':'Check order status and ERP export'} for x in missing_orders]+[{'Category':'Missing routing','Reference':x,'Next step':'Check ERP routing assignment'} for x in missing_routing]
if not roots: issues.append({'Category':'Missing engineering BOM','Reference':machine,'Next step':'Check technical BOM export'})
diagnostics=pd.DataFrame(issues,columns=['Category','Reference','Next step'])
if missing_orders or not ids or bom.empty:
    st.error('BOM ALERT ? Production BOM data is missing or incomplete for the selected historical reference. The displayed lines may not be complete.')
if not roots:
    st.error('BOM ALERT ? No engineering BOM root was found for the historical machine code.')
a,b,c,d=st.columns(4); a.metric('Machine',machine); b.metric('Production orders',len(ids)); c.metric('BOM lines',len(bom)); d.metric('Routing lines',len(routing))
st.caption(f"Revision {text(h['Revision'])} · {text(h['Machine Code Description'])}. Quantities remain per production order.")
st.subheader('Reference details')
tabs=st.tabs(['Production BOM','Routing','Configuration & notes','Engineering BOM','Diagnostics','Scope'])
with tabs[0]:
    if bom.empty: st.warning('No production BOM found for the linked orders.')
    st.dataframe(bom,hide_index=True,use_container_width=True); st.caption('Source: Prod Ord BOMs linked through production orders.')
with tabs[1]:
    st.dataframe(routing,hide_index=True,use_container_width=True)
    if missing_routing: st.warning('No routing found for linked codes: '+', '.join(missing_routing))
    st.caption('Source: BP100 Time routings. Times retain their original units.')
with tabs[2]:
    for title,df in [('Production orders',links),('Commercial codes on this sheet',association),('Technical configurations',config),('Production notes',notes)]:
        st.markdown('**'+title+'**'); st.dataframe(df,hide_index=True,use_container_width=True)
with tabs[3]:
    if technical.empty: st.warning('No engineering BOM root found for this machine.')
    st.dataframe(technical,hide_index=True,use_container_width=True); st.caption('Includes source validity dates and the production BOM flag; dates are not filtered.')
    if roots:
        try:
            reference_tree_xml = engineering_tree_xml(tech, [machine])
            st.download_button('Download historical engineering BOM tree (XML)', reference_tree_xml, file_name='BP100_HE_historical_engineering_tree_DRAFT.xml', mime='application/xml')
        except ValueError as exc:
            st.warning('Engineering BOM source tree could not be exported: ' + str(exc))
with tabs[4]:
    st.markdown('**Current sheet**'); st.dataframe(diagnostics,hide_index=True,use_container_width=True)
    negative=tech[pd.to_numeric(tech['Quantity'],errors='coerce')<0]
    st.markdown(f'**Negative quantities in HE engineering BOM: {len(negative)}**'); st.dataframe(negative,hide_index=True,use_container_width=True)
    st.caption('Negative quantities need engineering review. SAP-compatible corrections cannot be inferred safely from quantity alone.')
with tabs[5]:
    st.write('This prototype uses sheet-specific commercial associations and recorded production BOMs. It does not yet generate BOMs for unseen configurations, provide an editable rule engine or connect to SAP. Historical notes may be order-specific.')
    st.write('Accuracy against blind cases and a complete AS400 correction list have not been established.')

output=BytesIO()
with pd.ExcelWriter(output,engine='openpyxl') as writer:
    pd.DataFrame([{'Status': 'NOT APPROVED - HISTORICAL REFERENCE ONLY', 'Warning': 'May contain missing, extra or incorrect components and quantities for the current order. Engineering review required.', 'Requested codes absent': ', '.join(missing_reference), 'Additional historical codes': ', '.join(extra_reference), 'Missing production BOM orders': ', '.join(missing_orders)}]).to_excel(writer, sheet_name='READ FIRST - BOM ALERT', index=False)
    for name,df in {'BOM':bom,'Routing':routing,'Orders':links,'Commercial codes':association,'Configuration':config,'Notes':notes,'Engineering BOM':technical,'Diagnostics':diagnostics}.items(): df.to_excel(writer,sheet_name=name,index=False)
st.download_button('Download reference workbook',output.getvalue(),file_name='BP100_HE_'+sheet.replace('/','-')+'.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
st.download_button('Download historical reference BOM (XML)', historical_reference_xml(sheet, bom, missing_orders), file_name='BP100_HE_reference_BOM_DRAFT.xml', mime='application/xml', help='Recorded components grouped by historical production order; not the current order BOM.')

st.divider()
st.subheader('Explore similar configurations')
st.caption('Local k-nearest-neighbours model: it learns historical examples and compares sets of commercial codes. The selected sheet is excluded from its own neighbours.')
examples, descriptions = prepare_examples(data['assoc'], data['links'], data['bom'])
available_codes=sorted({text(x) for x in data['assoc']['Commercial Code'] if text(x).startswith('FBCA')})
default_codes=sorted({text(x) for x in association['Commercial Code'] if text(x) in available_codes})
st.caption('Machine learning uses the checklist codes confirmed above: ' + ', '.join(selected_codes))
k=st.slider('Number of similar historical sheets',3,15,5)
query=set(selected_codes)
if not query:
    st.info('Select at least one commercial code to find similar configurations.')
else:
    variants={code for code in query if code in {'FBCA0000','FBCA0001','FBCA0002'}}
    if len(variants) != 1:
        st.warning('Select exactly one machine variant (FBCA0000, FBCA0001 or FBCA0002).')
    else:
        neighbours=[]
        for example_sheet,example_codes,example_parts in examples:
            if example_sheet==sheet or not variants.issubset(example_codes): continue
            score=len(query & example_codes)/len(query | example_codes)
            if score>0: neighbours.append((score,example_sheet,example_codes,example_parts))
        neighbours.sort(key=lambda x:(-x[0],x[1]))
        neighbours=neighbours[:k]
        if not neighbours: st.warning('No comparable historical sheets with BOM data were found.')
        else:
            st.warning('Exploratory suggestions only: similarity is not an engineering rule or probability of correctness. Quantities and routing are not predicted. Review before use.')
            st.dataframe(pd.DataFrame([{'Production sheet':n[1], 'Similarity':round(n[0]*100,1), 'Matching codes':', '.join(sorted(query & n[2])), 'Missing requested codes':', '.join(sorted(query-n[2])), 'Additional codes':', '.join(sorted(n[2]-query))} for n in neighbours]),hide_index=True,use_container_width=True)
            part_counts={}
            for _,_,_,parts in neighbours:
                for part in parts: part_counts[part]=part_counts.get(part,0)+1
            suggestions=pd.DataFrame([{'Item code':part,'Description':descriptions.get(part,''),'Found in neighbours':count,'Neighbour count':len(neighbours)} for part,count in part_counts.items()]).sort_values(['Found in neighbours','Item code'],ascending=[False,True])
            st.markdown('**Observed components in similar production sheets**')
            st.dataframe(suggestions,hide_index=True,use_container_width=True)
            st.caption('Each part is counted once per neighbouring sheet. All linked production orders are included; machine and option quantities are not distinguished. Results are not a generated BOM.')
            st.download_button('Download component observations',suggestions.to_csv(index=False).encode('utf-8-sig'),file_name='similar_sheet_components.csv',mime='text/csv')
st.subheader('Model comparison and explanations')
st.caption('Models train locally on first use and stay cached for this app session. Adjust the model and threshold to update the dashboard.')
if True:
    try:
        import altair as alt
        import math
        from ml_models import train_models, predict, explain
        result = train_models(examples)
        import numpy as np
        st.markdown('#### Performance dashboard')
        dashboard_model, dashboard_threshold = st.columns([1, 2])
        with dashboard_model:
            active_model = st.selectbox('Model', ['XGBoost', 'kNN'], key='dashboard_model')
        with dashboard_threshold:
            threshold = st.slider('Decision threshold', min_value=0.05, max_value=0.95, value=0.50, step=0.05, help='Applied to model scores on the held-out test set. kNN uses the fraction of five neighbours.')
        truth = result['test_truth']
        score_arrays = {'XGBoost': result['test_xgb_scores'], 'kNN': result['test_knn_scores']}
        metric_rows = {}
        confusion_rows = []
        for model_name, scores in score_arrays.items():
            pred = scores >= threshold
            tp = int(np.sum(pred & (truth == 1)))
            fp = int(np.sum(pred & (truth == 0)))
            tn = int(np.sum(~pred & (truth == 0)))
            fn = int(np.sum(~pred & (truth == 1)))
            precision = tp / (tp + fp) if tp + fp else 0
            recall = tp / (tp + fn) if tp + fn else 0
            metric_rows[model_name] = {'Precision': precision, 'Recall': recall, 'Accuracy': (tp + tn) / (tp + tn + fp + fn), 'F1': 2 * precision * recall / (precision + recall) if precision + recall else 0, 'Exact match': float(np.all(pred == truth, axis=1).mean())}
            confusion_rows.extend([{'Model': model_name, 'Outcome': label, 'Count': count} for label, count in [('True positive', tp), ('False positive', fp), ('True negative', tn), ('False negative', fn)]])
        metric_table = pd.DataFrame(metric_rows).T
        active_metrics = metric_rows[active_model]
        cards = st.columns(5)
        for card, name in zip(cards, ['Precision', 'Recall', 'Accuracy', 'F1', 'Exact match']):
            card.metric(name, f'{active_metrics[name]:.1%}')
        st.caption('Metrics use the grouped held-out test set and cover only the modeled components. Accuracy includes true negatives and can look high when components are uncommon.')
        compare_tab, prediction_tab, explanation_tab = st.tabs(['Model comparison', 'Component scores', 'Explain a component'])
        with compare_tab:
            st.markdown('#### How do the models compare?')
            m1, m2, m3 = st.columns(3)
            m1.metric('Training sheets', result['train_count'])
            m2.metric('Held-out sheets', result['test_count'])
            m3.metric('Components evaluated', len(result['targets']))
            metrics_long = metric_table.rename_axis('Model').reset_index().melt(id_vars='Model', var_name='Measure', value_name='Value')
            chart = alt.Chart(metrics_long).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X('Measure:N', title=None), y=alt.Y('Value:Q', title='Score', scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format='%')),
                xOffset='Model:N', color=alt.Color('Model:N', scale=alt.Scale(domain=['XGBoost','kNN'], range=['#008c86','#0c4c80'])),
                tooltip=['Model:N','Measure:N',alt.Tooltip('Value:Q',format='.1%')]).properties(height=290)
            st.altair_chart(chart, use_container_width=True)
            st.caption('Precision = share of predicted components that were present. Recall = share of actual components found. Exact match = all evaluated components correct on one sheet.')
            st.info('This is a grouped hold-out on historical data, not a blind acceptance test. Exact match covers only the modeled components, not the full BOM. Related orders can still appear across groups.')
            st.markdown('#### Prediction outcomes for ' + active_model)
            conf = pd.DataFrame(confusion_rows)
            conf = conf[conf['Model'] == active_model]
            confusion_chart = alt.Chart(conf).mark_bar(cornerRadius=3).encode(
                x=alt.X('Count:Q', title='Component decisions'),
                y=alt.Y('Outcome:N', sort=['True positive', 'False positive', 'False negative', 'True negative'], title=None),
                color=alt.Color('Outcome:N', scale=alt.Scale(domain=['True positive', 'False positive', 'False negative', 'True negative'], range=['#008c86','#d99552','#c75b4d','#517a9a']), legend=None),
                tooltip=['Outcome:N', 'Count:Q']).properties(height=160)
            st.altair_chart(confusion_chart, use_container_width=True)
        x, prob = predict(result, set(selected_codes))
        table = pd.DataFrame({'Item code':result['targets'], 'Description':[descriptions.get(t,'') for t in result['targets']], 'XGBoost score':prob}).sort_values('XGBoost score', ascending=False)
        with prediction_tab:
            st.markdown('#### Which components does the model indicate?')
            st.caption('Based on the selected commercial codes. The 50% line is an illustrative threshold, not an approval rule.')
            st.dataframe(table, hide_index=True, use_container_width=True, column_config={
                'XGBoost score': st.column_config.ProgressColumn('Model score', format='%.2f', min_value=0, max_value=1, help='Uncalibrated model score between 0 and 1.')})
            st.warning('The selected historical sheet may have been used for training. Its score is an illustration, not an independent accuracy test. Scores are not calibrated; quantities, routing and rare components are not predicted.')
        with explanation_tab:
            st.markdown('#### Why did the score move?')
            target = st.selectbox('Component to inspect', table['Item code'].tolist(), format_func=lambda c: c + ' | ' + descriptions.get(c,''))
            contrib, bias = explain(result, x, target)
            component_score = float(table.loc[table['Item code'] == target, 'XGBoost score'].iloc[0])
            baseline = 1 / (1 + math.exp(-bias))
            a, b, c = st.columns(3)
            a.metric('Baseline score', f'{baseline:.0%}', help='Model baseline before applying feature contributions.')
            b.metric('Current model score', f'{component_score:.0%}', help='Uncalibrated score for the current selection.')
            c.metric('Commercial codes selected', len(selected_codes))
            st.caption('The baseline and final score are percentages. The individual bars below are additive contributions in log-odds; they are not percentage-point changes.')
            top = contrib.head(12).copy()
            top['Code and selection'] = top.apply(lambda r: r['Commercial code'] + (' · selected' if r['Selected'] else ' · not selected'), axis=1)
            top['Effect'] = top['Contribution (log-odds)'].map(lambda v: 'Raises score' if v >= 0 else 'Lowers score')
            influence = alt.Chart(top).mark_bar(cornerRadius=3).encode(
                y=alt.Y('Code and selection:N', sort=top['Code and selection'].tolist(), title=None),
                x=alt.X('Contribution (log-odds):Q', title='Contribution to model score (log-odds)'),
                color=alt.Color('Effect:N', scale=alt.Scale(domain=['Raises score','Lowers score'], range=['#008c86','#cc6f42']), title=None),
                tooltip=['Commercial code:N','Selected:N','Effect:N',alt.Tooltip('Contribution (log-odds):Q',format='.3f')]
            ).properties(height=max(180, len(top)*30))
            st.altair_chart(influence, use_container_width=True)
            with st.expander('View all code contributions'):
                st.dataframe(contrib, hide_index=True, use_container_width=True)
            st.caption('Tree SHAP explains this model output relative to its baseline. An unselected code can also influence the score. Contributions describe learned associations, not engineering causation or validated BOM rules.')
    except ImportError:
        st.error('XGBoost and scikit-learn are required. Install the packages listed in requirements.txt and restart the app.')
    except Exception as exc:
        st.error(f'Model training or explanation failed: {exc}')

