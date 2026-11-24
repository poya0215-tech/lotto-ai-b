"""Descriptive statistics and calibrated null tests; no prediction."""
from itertools import combinations
import numpy as np
import pandas as pd
from scipy.stats import hypergeom


def analyze(records):
    rows=sorted(records,key=lambda r:r['draw_no'])
    ids=np.array([r['draw_no'] for r in rows]); a=np.array([[r[f'n{i}'] for i in range(1,7)] for r in rows],dtype=int)
    if not len(rows): raise ValueError('데이터가 없습니다.')
    x=np.zeros((len(a),45),dtype=int); x[np.arange(len(a))[:,None],a-1]=1
    freq=pd.DataFrame({'전체':x.sum(0)},index=range(1,46))
    for w in (5,10,20,50,100,200): freq[f'최근 {w}회']=x[-w:].sum(0)
    gaps=[]; absent=[]
    for j in range(45):
        hits=ids[x[:,j]==1]; gaps.append(np.diff(hits).mean() if len(hits)>1 else np.nan); absent.append(ids[-1]-hits[-1] if len(hits) else np.nan)
    pairs=x.T@x; triples={}
    for row in a:
        for t in combinations(sorted(row),3): triples[t]=triples.get(t,0)+1
    adjacent=np.diff(ids)==1
    overlap=(x[1:]*x[:-1]).sum(1)[adjacent]
    def dist(v): return pd.Series(v).value_counts().sort_index()
    return dict(freq=freq,gaps=pd.DataFrame({'평균 관측 간격':gaps,'마지막 관측 이후 회차':absent},index=range(1,46)),pairs=pd.DataFrame([(i+1,j+1,pairs[i,j]) for i,j in combinations(range(45),2)],columns=['번호1','번호2','횟수']).sort_values('횟수',ascending=False),triples=pd.DataFrame([(*t,c) for t,c in triples.items()],columns=['번호1','번호2','번호3','횟수']).sort_values('횟수',ascending=False),corr=pd.DataFrame(x,columns=range(1,46)).corr(),odd=dist((a%2).sum(1)),low=dist((a<=22).sum(1)),total=dist(a.sum(1)),ending=dist((a%10).ravel()),consecutive=dist((np.diff(np.sort(a,axis=1),axis=1)==1).sum(1)),overlap=dist(overlap),x=x,ids=ids)


def tests(result, simulations=999, seed=42):
    x=result['x']; n=len(x); rng=np.random.default_rng(seed)
    expected=n*6/45; observed=((x.sum(0)-expected)**2/expected).sum()
    exceed=0
    for _ in range(simulations):
        # independent uniform six-element subsets, not independent balls
        picks=np.argpartition(rng.random((n,45)),5,axis=1)[:,:6]
        counts=np.bincount(picks.ravel(),minlength=45)
        exceed+=((counts-expected)**2/expected).sum()>=observed
    adjacent=np.diff(result['ids'])==1; m=int(adjacent.sum())
    p2=None
    if m:
        overlaps=(x[1:]*x[:-1]).sum(1)[adjacent]
        # exact null overlap distribution; adjacent overlap counts are independent under iid uniform draws
        probs=hypergeom.pmf(np.arange(7),45,6,6); exp=m*probs
        obs=np.bincount(overlaps,minlength=7); stat=((obs-exp)**2/exp).sum()
        sim=rng.multinomial(m,probs,size=simulations)
        p2=(1+np.sum(((sim-exp)**2/exp).sum(1)>=stat))/(simulations+1)
    return {'균등성 p값':(1+exceed)/(simulations+1),'인접 회차 겹침 p값':p2,'인접 회차 쌍':m}
