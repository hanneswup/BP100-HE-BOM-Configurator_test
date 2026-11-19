import openpyxl, json, pathlib
root=pathlib.Path(__file__).resolve().parent.parent / 'Data Source'
def rows(name, sheet):
 w=openpyxl.load_workbook(root/name,read_only=True,data_only=True); s=w[sheet]
 for r in s.iter_rows(min_row=2,values_only=True):
  yield [v.strip() if isinstance(v,str) else v for v in r]
headers={str(r[0]):{'sheet':str(r[0]),'revision':r[1],'machine':r[3],'description':r[4], 'codes':[], 'notes':[]} for r in rows('Prd Sheets Headers.xlsx','BP100 HE') if r[0]}
for sheet,tech,commercial,*_ in rows('Technical-Commercial Code Assosiation in Prd Sheets.xlsx','BP 100 HE'):
 if str(sheet) in headers and commercial and commercial not in headers[str(sheet)]['codes']: headers[str(sheet)]['codes'].append(commercial)
for sheet,seq,note,*_ in rows('Prd Sheets Notes.xlsx','BP 100 HE'):
 if str(sheet) in headers and note: headers[str(sheet)]['notes'].append([seq,note])
for h in headers.values(): h['notes']=[n for _,n in sorted(h['notes'],key=lambda x: x[0] or 0)]
pathlib.Path(__file__).with_name('history.js').write_text('window.HISTORY = '+json.dumps(list(headers.values()),ensure_ascii=False,default=str)+';',encoding='utf-8')
print(len(headers),'production sheets exported')
