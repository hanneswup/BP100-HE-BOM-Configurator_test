from pathlib import Path
from io import BytesIO
import base64
import hashlib
import pandas as pd
import streamlit as st
from pypdf import PdfReader
from checklist_codes import extract_codes, extract_visual_codes

DATA = Path(__file__).resolve().parent / 'Data' / 'Excel'
st.set_page_config(page_title='BP100 HE BOM Configurator', layout='wide')
st.markdown("""
<style>
.brand-logo { width: 100%; height: 100px; background-repeat: no-repeat; background-position: center 49%; background-size: 100% auto; mix-blend-mode: multiply; }
.stApp { background: #f5f8fa; color: #18334b; }
[data-testid="stMainBlockContainer"] { padding-top: 2rem; max-width: 1500px; }
h1, h2, h3 { color: #123d68 !important; }
[data-testid="stHeader"] { background: rgba(245,248,250,.96); }
[data-testid="stExpander"] { background: #fff; border: 1px solid #d8e4eb; border-radius: 9px; }
[data-testid="stMetric"] { background: #fff; border: 1px solid #d8e4eb; border-top: 3px solid #118d89; border-radius: 7px; padding: 14px 16px; }
[data-testid="stMetricLabel"] { color: #526d7f; }
[data-testid="stMetricValue"] { color: #074f82; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid #cddde5; }
.stTabs [data-baseweb="tab"] { color: #3b6179; padding: 10px 16px; }
.stTabs [aria-selected="true"] { color: #007c79 !important; border-bottom-color: #00958e !important; }
.stDownloadButton button { background: #007f82; color: white; border: 1px solid #007f82; border-radius: 6px; font-weight: 600; }
.stDownloadButton button:hover { background: #00686b; color: white; border-color: #00686b; }
[data-testid="stFileUploader"] section { background: #eef7f8; border: 1px dashed #70a9b2; border-radius: 8px; }
[data-testid="stAlert"] { border-radius: 7px; }
</style>
""", unsafe_allow_html=True)
brand_image = Path(__file__).resolve().parent.parent / 'images.jpg'
title_column, brand_column = st.columns([3, 2], vertical_alignment='center')
with title_column:
    st.title('BP100 HE BOM Configurator')
    st.caption('Proof of concept - Local historical data')
with brand_column:
    if brand_image.is_file():
        image_data = base64.b64encode(brand_image.read_bytes()).decode('ascii')
        st.markdown(f'<div class="brand-logo" role="img" aria-label="SteelcoBelimed, Miele Group Member" style="background-image: url(data:image/jpeg;base64,{image_data})"></div>', unsafe_allow_html=True)

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

pdf_ready = False
detected_codes = set()
visual_codes = None
st.info('Reconstruct a recorded production BOM and routing from a historical production sheet. Review the source data before use; this is not an approved new BOM.')
with st.expander('1 · Upload order checklist',expanded=True):
    f=st.file_uploader('Drag and drop a checklist PDF',type='pdf')
    if f:
        try:
            reader=PdfReader(BytesIO(f.getvalue()))
            if reader.is_encrypted and not reader.decrypt(''): raise ValueError('Password-protected PDF')
            content='\n'.join(p.extract_text() or '' for p in reader.pages)
            fields=reader.get_fields() or {}
            detected_codes=extract_codes(fields)
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
            if values: st.dataframe(pd.DataFrame(values,columns=['PDF field','Value']),hide_index=True)
            else: st.warning('No interactive fields detected. Flattened or scanned checklists require manual review; selections are not inferred from the printed list of options.')
            with st.expander('Extracted text'): st.text_area('PDF text',content,height=200,disabled=True)
        except Exception as exc: st.error(f'Cannot read PDF: {exc}')
if not pdf_ready:
    st.info('Upload a readable order checklist PDF to continue.')
    st.stop()
if visual_codes is not None:
    st.success('Configuration read from the checklist: ' + ', '.join(sorted(visual_codes)))
    st.caption('Automatic recognition is limited to supported BP 100 HE revision 07/08 layouts. Verify the result before using it.')
else:
    st.warning('Automatic checkbox recognition was not reliable for this PDF. Select the configuration below.')
try: data=load()
except Exception as exc: st.error(f'Unable to load input data: {exc}'); st.stop()
headers=data['headers']
st.subheader('Checklist configuration')
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
pdf_key = hashlib.sha256(f.getvalue()).hexdigest()
detected_variants = sorted(detected_codes.intersection(variant_codes))
detected_connections = sorted(detected_codes.intersection(connections))
detected_options = sorted(detected_codes.intersection(options))
if detected_codes:
    st.caption('Explicit codes detected in PDF fields: ' + ', '.join(sorted(detected_codes)))
if len(detected_variants) > 1 or len(detected_connections) > 1:
    st.warning('Multiple variants or electrical connections were found. Choose the correct values manually.')
if not detected_codes:
    st.warning('No explicit commercial codes could be mapped from the interactive PDF fields. Select the configuration manually; printed option lists are not treated as selections.')
with st.expander('Review or correct detected configuration', expanded=visual_codes is None):
    col_variant,col_power = st.columns(2)
    with col_variant:
        selected_variant = st.selectbox('Machine variant from checklist',variant_codes,index=variant_codes.index(detected_variants[0]) if len(detected_variants)==1 else None,format_func=lambda c: variant_names.get(c,c)+' ('+c+')',placeholder='Select the variant',key='variant_'+pdf_key)
    with col_power:
        selected_connection = st.selectbox('Electrical connection code',connections,index=connections.index(detected_connections[0]) if len(detected_connections)==1 else None,placeholder='Select the electrical connection',format_func=lambda c: connection_names.get(c,'Unknown connection')+' ('+c+')',key='connection_'+pdf_key)
    selected_options = st.multiselect('Selected option codes',options,default=detected_options,format_func=lambda c: option_names.get(c,'Other option')+' ('+c+')',help='Only select options marked on the uploaded checklist.',key='options_'+pdf_key)
if not selected_variant or not selected_connection:
    st.info('Select the machine variant and electrical connection to see similar historical orders.')
    st.stop()
selected_codes = [selected_variant, selected_connection, *selected_options]
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
st.subheader('3 · Suggested historical references')
st.caption('Ranked by shared commercial codes. Similarity is not a technical validation; additional and missing codes must be reviewed.')
st.dataframe(reference_frame, hide_index=True, use_container_width=True, column_config={'Code similarity':st.column_config.ProgressColumn('Code similarity',min_value=0,max_value=1,format='%.2f')})
reference_options = [item[1] for item in reference_candidates]
sheet = st.selectbox('Inspect a suggested historical reference',reference_options,format_func=lambda r: r+' | '+text(headers.loc[headers['Production Sheet'].map(text)==r,'Machine Code Description'].iloc[0]) if (headers['Production Sheet'].map(text)==r).any() else r)
st.warning('The BOM below is the recorded BOM of the selected reference, not a generated BOM from the uploaded checklist.')
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
a,b,c,d=st.columns(4); a.metric('Machine',machine); b.metric('Production orders',len(ids)); c.metric('BOM lines',len(bom)); d.metric('Routing lines',len(routing))
st.caption(f"Revision {text(h['Revision'])} · {text(h['Machine Code Description'])}. Quantities remain per production order.")
st.subheader('3 · Reconstructed output')
tabs=st.tabs(['Production BOM','Routing','Configuration and notes','Engineering BOM','Diagnostics','Scope'])
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
with tabs[4]:
    st.markdown('**Current sheet**'); st.dataframe(diagnostics,hide_index=True,use_container_width=True)
    negative=tech[pd.to_numeric(tech['Quantity'],errors='coerce')<0]
    st.markdown(f'**Negative quantities in HE engineering BOM: {len(negative)}**'); st.dataframe(negative,hide_index=True,use_container_width=True)
    st.caption('Negative quantities need engineering review. SAP-compatible corrections cannot be inferred safely from quantity alone.')
with tabs[5]:
    st.write('This prototype uses sheet-specific commercial associations and recorded production BOMs. It does not yet generate BOMs for unseen configurations, provide an editable rule engine or connect to SAP. Historical notes may be order-specific.')
    st.write('Accuracy against blind cases and a complete AS400 correction list have not been established.')

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

st.subheader('4 · Machine learning: similar configurations')
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
st.subheader('5 · Model comparison and explanations')
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

output=BytesIO()
with pd.ExcelWriter(output,engine='openpyxl') as writer:
    for name,df in {'BOM':bom,'Routing':routing,'Orders':links,'Commercial codes':association,'Configuration':config,'Notes':notes,'Engineering BOM':technical,'Diagnostics':diagnostics}.items(): df.to_excel(writer,sheet_name=name,index=False)
st.download_button('Download reconstructed workbook',output.getvalue(),file_name='BP100_HE_'+sheet.replace('/','-')+'.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
