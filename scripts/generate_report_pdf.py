#!/usr/bin/env python3
"""Génère `data/external/report_local_only.pdf` à partir des fichiers produits.
"""
from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.image as mpimg

EXT = Path('data/external')
PLOTS = EXT / 'plots_local_only'
OUT = EXT / 'report_local_only.pdf'

# Load meta
analysis = {}
if (EXT / 'analysis_report.json').exists():
    analysis = json.loads((EXT / 'analysis_report.json').read_text(encoding='utf8'))

summary = pd.DataFrame()
if (EXT / 'summary_per_crop.csv').exists():
    summary = pd.read_csv(EXT / 'summary_per_crop.csv')

local = pd.DataFrame()
if (EXT / 'local_prices_normalized.csv').exists():
    local = pd.read_csv(EXT / 'local_prices_normalized.csv')

with PdfPages(OUT) as pdf:
    # Page 1: Title + analysis
    plt.figure(figsize=(8.27,11.69))
    plt.axis('off')
    title = 'Rapport local — Prix marché Togo'
    plt.text(0.5, 0.92, title, ha='center', fontsize=18, weight='bold')
    y = 0.82
    plt.text(0.02, y, 'Résumé d’analyse:', fontsize=12, weight='bold')
    y -= 0.04
    txt = f"Lignes locales analysées: {analysis.get('rows', 'N/A')}\nTaux FCFA/USD utilisé (médiane): {analysis.get('fx_median_used', 'N/A'):.2f}\nAnnées CPI disponibles: {analysis.get('cpi_years', 'N/A')}"
    plt.text(0.02, y, txt, fontsize=10)
    y -= 0.12
    plt.text(0.02, y, 'Top 10 cultures (résumé):', fontsize=12, weight='bold')
    y -= 0.03
    if not summary.empty:
        # show first rows as text
        stxt = summary.head(10).to_string(index=False)
        plt.text(0.02, y, stxt, fontsize=8, family='monospace')
    else:
        plt.text(0.02, y, 'Aucun résumé par culture disponible.', fontsize=10)
    pdf.savefig()
    plt.close()

    # Pages: plots
    if PLOTS.exists():
        imgs = sorted(PLOTS.glob('*.png'))
        for img in imgs:
            try:
                im = mpimg.imread(img)
                plt.figure(figsize=(8.27,11.69))
                plt.imshow(im)
                plt.axis('off')
                pdf.savefig()
                plt.close()
            except Exception:
                continue

    # Page: sample table
    if not local.empty:
        fig, ax = plt.subplots(figsize=(8.27,11.69))
        ax.axis('off')
        ax.set_title('Extrait des données locales (10 premières lignes)')
        tbl = local.head(10)
        ax.table(cellText=tbl.values, colLabels=tbl.columns, loc='center', cellLoc='center')
        plt.tight_layout()
        pdf.savefig()
        plt.close()

print('PDF généré:', OUT)
