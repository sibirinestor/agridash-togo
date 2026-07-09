#!/usr/bin/env python3
"""
Script pour télécharger des données FAOSTAT (Prices) et World Bank CPI pour le Togo.
Exécutez-le localement (il peut nécessiter une connexion réseau). Les fichiers seront sauvegardés dans `data/external/`.
"""
import requests
import json
import os
import time
from pathlib import Path

OUT_DIR = Path('data/external')
OUT_DIR.mkdir(parents=True, exist_ok=True)

ITEMS = ['maize', 'rice', 'cassava']

HEADERS = {'User-Agent': 'odc-fetch-script/1.0 (+https://example.org)'}

def fetch_with_retries(url, retries=3, timeout=20):
    for i in range(1, retries+1):
        try:
            r = requests.get(url, timeout=timeout, headers=HEADERS)
            return r
        except Exception as e:
            if i == retries:
                raise
            time.sleep(1 + i)

def fetch_faostat_prices(item):
    # FAOSTAT endpoint - adapte le paramètre item si besoin
    url = f'https://fenixservices.fao.org/faostat/api/v1/en/data/Prices?country=Togo&item={item}&format=json'
    r = fetch_with_retries(url)
    if r.status_code == 200:
        j = r.json()
        out = OUT_DIR / f'faostat_Prices_{item}.json'
        with out.open('w', encoding='utf8') as f:
            json.dump(j, f, ensure_ascii=False, indent=2)
        print('Saved', out)
    else:
        print('FAOSTAT failed', r.status_code, r.text[:200])

def fetch_worldbank_cpi():
    url = 'http://api.worldbank.org/v2/country/tgo/indicator/FP.CPI.TOTL?format=json&per_page=500'
    r = fetch_with_retries(url)
    if r.status_code == 200:
        j = r.json()
        out = OUT_DIR / 'wb_cpi_tgo.json'
        with out.open('w', encoding='utf8') as f:
            json.dump(j, f, ensure_ascii=False, indent=2)
        print('Saved', out)
    else:
        print('World Bank failed', r.status_code, r.text[:200])

if __name__ == '__main__':
    print('Fetching FAOSTAT Prices for:', ITEMS)
    for it in ITEMS:
        try:
            fetch_faostat_prices(it)
        except Exception as e:
            print('Error fetching FAOSTAT', it, e)
    print('\nFetching World Bank CPI for Togo')
    try:
        fetch_worldbank_cpi()
    except Exception as e:
        print('Error fetching World Bank CPI', e)
    print('\nDone. Check data/external/')
