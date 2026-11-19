import numpy as np
import pandas as pd
import streamlit as st

@st.cache_resource(show_spinner='Training XGBoost models and evaluating held-out configurations...')
def train_models(examples, top_n=30, k=5):
    from sklearn.model_selection import GroupShuffleSplit
    from xgboost import XGBClassifier
    usable=[(s,sorted(c),p) for s,c,p in examples if c and p]
    groups=['|'.join(c) for _,c,_ in usable]
    if len(set(groups)) < 5: raise ValueError('Not enough distinct code combinations for a group-separated test.')
    idx_train,idx_test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(usable,groups=groups))
    feature_names=sorted({c for _,codes,_ in usable for c in codes})
    X=np.array([[int(c in codes) for c in feature_names] for _,codes,_ in usable],dtype=np.float32)
    counts={}
    for i in idx_train:
        for p in usable[i][2]: counts[p]=counts.get(p,0)+1
    targets=[p for p,n in sorted(counts.items(),key=lambda x:(-x[1],x[0])) if n>=5 and n<=len(idx_train)-5][:top_n]
    if not targets: raise ValueError('No components have enough positive and negative training examples.')
    Y=np.array([[int(p in parts) for p in targets] for _,_,parts in usable],dtype=np.int8)
    models=[]; probabilities=[]
    for j in range(len(targets)):
        model=XGBClassifier(n_estimators=50,max_depth=3,learning_rate=.1,subsample=.9,colsample_bytree=.9,n_jobs=2,random_state=42,eval_metric='logloss')
        model.fit(X[idx_train],Y[idx_train,j]); models.append(model); probabilities.append(model.predict_proba(X[idx_test])[:,1])
    pred_xgb=(np.array(probabilities).T >= .5).astype(int)
    train_sets=[set(usable[i][1]) for i in idx_train]
    knn_scores=[]
    for i in idx_test:
        q=set(usable[i][1]); scores=[(len(q & t)/len(q | t) if q | t else 0,j) for j,t in enumerate(train_sets)]
        nearest=sorted(scores,key=lambda x:(-x[0],x[1]))[:min(k,len(scores))]
        knn_scores.append(Y[idx_train[[j for _,j in nearest]]].mean(axis=0))
    pred_knn=(np.array(knn_scores)>=.5).astype(int)
    def metrics(pred):
        truth=Y[idx_test]; tp=int(((pred==1)&(truth==1)).sum()); fp=int(((pred==1)&(truth==0)).sum()); fn=int(((pred==0)&(truth==1)).sum())
        return {'Precision':tp/(tp+fp) if tp+fp else 0, 'Recall':tp/(tp+fn) if tp+fn else 0, 'Exact match':float(np.all(pred==truth,axis=1).mean())}
    return {'features':feature_names,'targets':targets,'models':models,'metrics':{'XGBoost':metrics(pred_xgb),'kNN':metrics(np.array(pred_knn))},'train_count':len(idx_train),'test_count':len(idx_test),'groups':len(set(groups)),'test_sheets':[usable[i][0] for i in idx_test], 'test_truth':Y[idx_test], 'test_xgb_scores':np.array(probabilities).T, 'test_knn_scores':np.array(knn_scores)}

def predict(model_data, query):
    import xgboost as xgb
    X=np.array([[int(f in query) for f in model_data['features']]],dtype=np.float32)
    probabilities=[float(model.predict_proba(X)[0,1]) for model in model_data['models']]
    return X, probabilities

def explain(model_data, X, target):
    import xgboost as xgb
    model=model_data['models'][model_data['targets'].index(target)]
    values=model.get_booster().predict(xgb.DMatrix(X),pred_contribs=True)[0]
    rows=[{'Commercial code':f,'Selected':bool(X[0,i]),'Contribution (log-odds)':float(values[i])} for i,f in enumerate(model_data['features'])]
    return pd.DataFrame(rows).sort_values('Contribution (log-odds)',key=lambda x:x.abs(),ascending=False),float(values[-1])
