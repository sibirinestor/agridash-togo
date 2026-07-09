#!/usr/bin/env python3
"""Réessaie de récupérer FAOSTAT Prices pour le Togo avec plusieurs stratégies.
Sauvegarde les réponses valides dans `data/external/`.
"""
import requests, json, time
from pathlib import Path
OUT=Path('data/external')
OUT.mkdir(parents=True, exist_ok=True)
items=['maize','rice','cassava']
endpoints=[
    'https://fenixservices.fao.org/faostat/api/v1/en/data/Prices',
    'https://www.fao.org/faostat/api/v1/en/data/Prices',
    'https://data.apps.fao.org/faostat/api/v1/en/data/Prices'
]
user_agents=[
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'curl/7.85.0',
    'python-requests/2.31.0',
]
results={}
for ep in endpoints:
    for ua in user_agents:
        headers={'User-Agent':ua,'Accept':'application/json','Accept-Language':'fr-FR,fr;q=0.9'}
        for item in items:
            url=f"{ep}?country=Togo&item={item}&format=json"
            ok=False
            for attempt in range(1,7):
                try:
                    timeout = 30 + attempt*10
                    r = requests.get(url, timeout=timeout, headers=headers)
                    key=f'{ep}|{ua}|{item}'
                    results.setdefault(key,[]).append({'attempt':attempt,'status':r.status_code})
                    if r.status_code==200:
                        try:
                            j=r.json()
                            if j and ('data' in j and j['data']):
                                fname=OUT / f'faostat_Prices_{item}_{ep.split("//")[-1].replace("/","_")}_{ua.split()[0]}.json'
                                with open(fname,'w',encoding='utf8') as f:
                                    json.dump(j,f,ensure_ascii=False,indent=2)
                                results[key].append({'saved':str(fname)})
                                ok=True
                                break
                            else:
                                results[key].append({'note':'no data'})
                        except Exception as e:
                            results[key].append({'json_error':str(e)})
                    else:
                        results[key].append({'text_snippet':r.text[:200]})
                except Exception as e:
                    results.setdefault(key,[]).append({'error':str(e),'attempt':attempt})
                time.sleep(1+attempt)
            results.setdefault(key,[]).append({'ok':ok})
# write summary
with open(OUT / 'faostat_retry_summary.json','w',encoding='utf8') as f:
    json.dump(results,f,ensure_ascii=False,indent=2)
print('Done. Summary ->', OUT / 'faostat_retry_summary.json')
