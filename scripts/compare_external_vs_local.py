#!/usr/bin/env python3
"""
Normalise et compare les prix locaux (`data/togo_market_prices.csv`)
avec les fichiers externes téléchargés dans `data/external/` (FAOSTAT, World Bank).
Génère un rapport CSV dans `data/external/comparison_report.csv` et des graphiques
dans `data/external/plots/`.

Usage:
    python scripts/compare_external_vs_local.py

Pré-requis: pandas, matplotlib, seaborn
"""
import json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = Path('.')
LOCAL_PRICES = ROOT / 'data' / 'togo_market_prices.csv'
EXT_DIR = ROOT / 'data' / 'external'
PLOTS_DIR = EXT_DIR / 'plots'
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

def read_local():
    if not LOCAL_PRICES.exists():
        raise FileNotFoundError(f"Fichier local introuvable: {LOCAL_PRICES}")
    df = pd.read_csv(LOCAL_PRICES, low_memory=False)
    # normalisation colonnes attendues
    for c in ['price_fcfa_kg','price_usd_t']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

def read_faostat_prices():
    files = list(EXT_DIR.glob('faostat_Prices_*.json'))
    records = []
    for f in files:
        try:
            j = json.loads(f.read_text(encoding='utf8'))
            data = j.get('data') or j.get('Data') or []
            for r in data:
                # tentatives d'extraction courante
                year = r.get('year') or r.get('Year') or r.get('time')
                item = r.get('item') or r.get('Item') or r.get('ItemCode') or r.get('element')
                value = r.get('value') or r.get('Value') or r.get('mean')
                if year is None or value is None:
                    continue
                records.append({'source_file': f.name, 'item': item, 'year': int(year), 'value': float(value)})
        except Exception:
            continue
    if records:
        return pd.DataFrame(records)
    return pd.DataFrame(columns=['source_file','item','year','value'])

def read_worldbank_cpi():
    f = EXT_DIR / 'wb_cpi_tgo.json'
    if not f.exists():
        return pd.DataFrame()
    try:
        j = json.loads(f.read_text(encoding='utf8'))
        # World Bank v2: j[1] is the data list
        data = j[1] if isinstance(j, list) and len(j) > 1 else j.get('data', [])
        records = []
        for r in data:
            year = r.get('date') or r.get('year')
            val = r.get('value')
            if year is None:
                continue
            records.append({'year': int(year), 'cpi': float(val) if val is not None else np.nan})
        return pd.DataFrame(records)
    except Exception:
        return pd.DataFrame()


def align_and_compare(local, fao, wb):
    # Local: expect Year, region, crop, price_fcfa_kg, price_usd_t
    # Convert price_usd_t -> USD/kg
    df = local.copy()
    if 'price_usd_t' in df.columns:
        df['price_usd_kg'] = df['price_usd_t'] / 1000.0
    # implied fx = (price_fcfa_kg*1000) / price_usd_t
    if 'price_fcfa_kg' in df.columns and 'price_usd_t' in df.columns:
        df['implied_fcfa_per_usd'] = (df['price_fcfa_kg'] * 1000.0) / df['price_usd_t']
    # FAO: try to match by item names
    comparisons = []
    items = df['crop'].unique() if 'crop' in df.columns else []
    for it in items:
        it_local = df[df['crop'].str.lower().str.contains(str(it).lower(), na=False)]
        it_fao = fao[fao['item'].astype(str).str.lower().str.contains(str(it).lower(), na=False)] if not fao.empty else pd.DataFrame()
        if it_fao.empty:
            continue
        # aggregate median per year for local
        loc_agg = it_local.groupby('Year').agg({'price_fcfa_kg':'median','price_usd_kg':'median'}).reset_index()
        fao_agg = it_fao.groupby('year').agg({'value':'median'}).reset_index()
        # join on year where possible
        merged = pd.merge(loc_agg, fao_agg, left_on='Year', right_on='year', how='outer')
        merged['crop'] = it
        comparisons.append(merged)
    if comparisons:
        comp_df = pd.concat(comparisons, ignore_index=True, sort=False)
    else:
        comp_df = pd.DataFrame()
    return df, comp_df


def save_report(local, comp):
    out_csv = EXT_DIR / 'comparison_report_local.csv'
    local.to_csv(out_csv, index=False)
    print('Saved local-normalized ->', out_csv)
    if not comp.empty:
        out_comp = EXT_DIR / 'comparison_report_fao.csv'
        comp.to_csv(out_comp, index=False)
        print('Saved FAO comparison ->', out_comp)


def plot_comparisons(comp):
    if comp.empty:
        print('Aucune comparaison FAO disponible pour tracer.')
        return
    sns.set(style='whitegrid')
    crops = comp['crop'].unique()
    for c in crops:
        df = comp[comp['crop']==c]
        plt.figure(figsize=(8,4))
        plt.plot(df['Year'], df['price_fcfa_kg'], marker='o', label='Local median FCFA/kg')
        if 'value' in df.columns:
            # FAO value unit unknown; plot on secondary axis
            ax = plt.gca()
            ax2 = ax.twinx()
            ax2.plot(df['Year'], df['value'], color='orange', marker='x', label='FAO value (raw)')
            ax2.set_ylabel('FAO raw value')
        plt.title(f'Comparaison prix - {c}')
        plt.xlabel('Year')
        plt.ylabel('FCFA/kg (local)')
        plt.legend()
        out = PLOTS_DIR / f'comparison_{c}.png'
        plt.tight_layout()
        plt.savefig(out)
        plt.close()
        print('Saved plot', out)


if __name__ == '__main__':
    print('Lecture du fichier local...')
    local = read_local()
    print('Lecture FAO...')
    fao = read_faostat_prices()
    print('Lecture World Bank CPI...')
    wb = read_worldbank_cpi()
    print(f'Local rows={len(local)}, FAO rows={len(fao)}, WB rows={len(wb)}')
    local_norm, comp = align_and_compare(local, fao, wb)
    save_report(local_norm, comp)
    plot_comparisons(comp)
    print('Terminé.')
