# AgriDash Togo

Documentation complete du projet d'optimisation et de pilotage des chaines de valeur agricoles au Togo.

## 1. Presentation generale

AgriDash Togo est un projet Python de data analyse et de tableau de bord interactif pour suivre les filieres agricoles strategiques du Togo. Le projet combine plusieurs familles de donnees :

- donnees macroeconomiques issues de la Banque mondiale, notamment inflation et PIB ;
- donnees climatiques issues de NASA POWER, avec precipitation et temperature par region ;
- donnees agricoles estimees ou derivees pour les principales cultures togolaises ;
- donnees de prix de marche par region et par culture ;
- modeles de risque, de prevision et d'aide a la decision.

L'objectif principal est de fournir une vue exploitable sur la production agricole, les rendements, les prix, les risques macroeconomiques et climatiques, ainsi que les opportunites de transformation et d'arbitrage regional.

Le projet contient aussi une application Dash nommee AgriDash Togo, qui permet d'explorer les indicateurs sous forme de graphiques, cartes, tableaux, filtres et exports.

## 2. Fonctionnalites principales

Le projet permet de :

- charger les donnees World Bank fournies localement ;
- comparer le Togo avec d'autres pays d'Afrique de l'Ouest sur l'inflation ;
- generer des donnees agricoles par culture de 2000 a 2025 ;
- recuperer ou lire en cache les donnees climatiques NASA POWER ;
- generer des prix de marche regionaux de 2015 a 2030 ;
- calculer un score de risque d'approvisionnement ;
- produire des previsions agricoles jusqu'en 2030 ;
- visualiser les resultats dans un dashboard Dash ;
- exporter des donnees en CSV, Excel et PDF ;
- deployer l'application sur Render via `render.yaml`.

## 3. Structure du projet

```text
.
├── README.md
├── requirements.txt
├── render.yaml
├── dashboard/
│   ├── app.py
│   └── assets/custom.css
├── src/
│   ├── config.py
│   ├── data_loader.py
│   ├── agriculture_data.py
│   ├── climate_data.py
│   ├── market_prices.py
│   ├── forecast.py
│   ├── models.py
│   ├── pipeline.py
│   ├── togo_map.py
│   └── visualization.py
├── scripts/
│   ├── fetch_external_data.py
│   ├── retry_faostat.py
│   ├── compare_external_vs_local.py
│   ├── summarize_local_prices.py
│   └── generate_report_pdf.py
├── data/
│   ├── togo_climate_nasa_power.csv
│   ├── togo_forecasts.csv
│   ├── togo_market_prices.csv
│   ├── togo_regions.geojson
│   ├── togo_wb_agriculture.csv
│   └── external/
├── notebooks/
│   └── 01_EDA_Togo.ipynb
├── models/
├── outputs/
├── Images/
└── API_*_DS2_fr_csv_*/
```

## 4. Installation

Depuis la racine du projet :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Les dependances principales sont :

- `pandas` et `numpy` pour la manipulation de donnees ;
- `plotly`, `dash` et `dash-bootstrap-components` pour le dashboard ;
- `scikit-learn` pour les modeles de prediction et de risque ;
- `prophet` pour les previsions temporelles ;
- `requests` pour les appels API externes ;
- `matplotlib`, `seaborn` et `weasyprint` pour graphiques et exports ;
- `gunicorn` pour le deploiement web ;
- `pytest` pour les tests automatises.

## 5. Lancer le projet

### Lancer le dashboard en local

```bash
python3 dashboard/app.py
```

Puis ouvrir :

```text
http://localhost:8050
```

### Lancer le pipeline d'analyse

```bash
python3 -m src.pipeline
```

Ce pipeline charge les donnees macroeconomiques, les donnees climatiques, calcule les risques et entraine des modeles de rendement par culture.

### Generer les previsions

```bash
python3 -m src.forecast
```

Les previsions sont sauvegardees dans :

```text
data/togo_forecasts.csv
```

### Generer le rapport PDF local

```bash
python3 scripts/generate_report_pdf.py
```

Le rapport est genere dans :

```text
data/external/report_local_only.pdf
```

## 6. Donnees utilisees

### Donnees World Bank

Les dossiers suivants contiennent des exports CSV de la Banque mondiale :

- `API_FP.CPI.TOTL.ZG_DS2_fr_csv_v2_9735/` : inflation ;
- `API_NY.GDP.MKTP.CD_DS2_fr_csv_v2_499/` : PIB.

Le module `src/data_loader.py` lit ces fichiers, saute les lignes de metadonnees, transforme les colonnes d'annees en format long, puis filtre le Togo ou les pays d'Afrique de l'Ouest.

### Donnees agricoles

Le fichier :

```text
data/togo_wb_agriculture.csv
```

sert de cache pour certains indicateurs agricoles, notamment :

- rendement cerealier ;
- indice de production agricole.

Le module `src/agriculture_data.py` utilise ces donnees comme base, puis estime des series par culture. Les cultures suivies sont :

- maïs ;
- riz paddy ;
- sorgho ;
- mil ;
- manioc ;
- igname ;
- soja ;
- arachide ;
- palme ;
- coton ;
- noix de cajou ;
- café ;
- cacao.

Chaque culture est rattachee a une categorie :

- cereale ;
- tubercule ;
- oleagineux ;
- fibre ;
- export.

### Donnees climatiques

Le module `src/climate_data.py` recupere les donnees NASA POWER pour cinq regions :

- Maritime ;
- Plateaux ;
- Centrale ;
- Kara ;
- Savanes.

Les variables recuperees sont :

- `PRECTOTCORR` : precipitation ;
- `T2M` : temperature moyenne.

Les donnees sont agregees par annee et une moyenne nationale est ajoutee avec `Region = National`.

Le cache local est :

```text
data/togo_climate_nasa_power.csv
```

Si ce fichier existe, le projet l'utilise directement. Sinon, il tente de telecharger les donnees via l'API NASA POWER.

### Donnees de prix de marche

Le module `src/market_prices.py` genere des prix par region, culture et annee. Les prix sont exprimes en :

- FCFA par kg ;
- USD par tonne.

Le cache est :

```text
data/togo_market_prices.csv
```

Les annees couvertes vont de 2015 a 2030. Les prix sont bases sur des prix de reference 2024, puis ajustes avec :

- une tendance annuelle ;
- une variation saisonniere simplifiee ;
- un bruit aleatoire borne.

## 7. Explication des modules Python

### `src/config.py`

Ce fichier centralise les constantes du projet :

- chemins vers les dossiers `data`, `outputs`, `models` et `notebooks` ;
- code pays du Togo ;
- liste des cultures ;
- categories de cultures ;
- indicateurs World Bank ;
- regions du Togo.

C'est le fichier a modifier en priorite si l'on veut ajouter une culture, une categorie ou un indicateur strategique.

### `src/data_loader.py`

Ce module gere la lecture et la preparation des donnees macroeconomiques.

Fonctions importantes :

- `load_world_bank_data(indicator_key)` : charge un indicateur World Bank local ;
- `get_togo_data(indicator_key)` : filtre les donnees pour le Togo ;
- `get_wa_comparison(indicator_key)` : extrait les pays d'Afrique de l'Ouest ;
- `load_wb_agri_cache()` : lit le cache agricole local ;
- `load_all_togo_data()` : regroupe inflation, PIB et donnees agricoles ;
- `summary_stats()` : produit des statistiques descriptives.

### `src/agriculture_data.py`

Ce module construit les series agricoles principales. Il part des indicateurs World Bank disponibles, puis estime :

- rendement en tonnes par hectare ;
- superficie en hectares ;
- production en tonnes ;
- prix export en USD par tonne pour certaines cultures.

Les estimations reposent sur :

- des ratios de rendement par culture ;
- des parts de production de base ;
- un indice de production agricole ;
- une tendance annuelle.

Le module contient aussi `PIA_TRANSFORMATION_POTENTIAL`, qui decrit le potentiel de transformation agro-industrielle de certaines filieres comme soja, coton, cajou, maïs, manioc, palme et arachide.

### `src/climate_data.py`

Ce module gere les donnees climatiques :

- appel a l'API NASA POWER ;
- conversion mensuelle vers annuel ;
- calcul de precipitation annuelle ;
- calcul de temperature annuelle moyenne ;
- creation d'une ligne nationale par annee ;
- sauvegarde dans un cache CSV.

### `src/market_prices.py`

Ce module genere et analyse les prix de marche.

Fonctions importantes :

- `generate_market_prices()` : cree les prix regionaux ;
- `get_market_prices()` : lit le cache ou regenere les prix ;
- `get_market_summary(df, year)` : cree un tableau de synthese par culture ;
- `get_price_volatility(df, crop)` : calcule la volatilite ;
- `get_arbitrage_opportunities(df, year, threshold_pct)` : detecte les ecarts de prix regionaux exploitables.

### `src/forecast.py`

Ce module utilise Prophet pour produire des previsions jusqu'en 2030 lorsque la dependance est disponible. Si Prophet n'est pas installe, le module utilise un modele local de tendance polynomial afin que le projet reste executable.

Il genere trois scenarios :

- `modéré` ;
- `optimiste` ;
- `pessimiste`.

Le scenario optimiste augmente les previsions de rendement. Le scenario pessimiste les reduit. Les resultats sont sauvegardes dans `data/togo_forecasts.csv`.

Les parametres `CROP_PARAMS` definissent pour chaque culture une plage de rendement et une plage de prix. Ils servent a borner les previsions et a eviter des resultats aberrants.

### `src/models.py`

Ce module contient deux classes.

`YieldPredictor` sert a predire les rendements agricoles. Il supporte trois types de modeles :

- random forest ;
- gradient boosting ;
- regression lineaire.

Il contient aussi des fonctions d'ingenierie de variables, avec par exemple :

- PIB retarde ;
- inflation retardee ;
- croissance du PIB ;
- moyenne mobile du PIB ;
- moyenne mobile de l'inflation.

`SupplyChainRiskModel` calcule un score de risque a partir de :

- volatilite de l'inflation ;
- niveau d'inflation ;
- amplitude de la croissance du PIB.

Le score final est normalise entre 0 et 1, puis classe en :

- Faible ;
- Modere ;
- Eleve ;
- Critique.

### `src/pipeline.py`

Ce module orchestre une analyse complete en ligne de commande.

Il execute quatre grandes etapes :

1. chargement des donnees macroeconomiques ;
2. chargement des donnees climatiques ;
3. calcul du risque d'approvisionnement ;
4. entrainement de modeles de rendement pour toutes les cultures.

### `src/togo_map.py`

Ce module gere la carte du Togo.

Il lit :

```text
data/togo_regions.geojson
```

Il fournit aussi :

- une correspondance entre noms de regions GeoJSON et noms utilises dans le dashboard ;
- des centroides regionaux ;
- des parts regionales estimees ;
- une repartition de production par region.

### `src/visualization.py`

Ce module regroupe des fonctions de visualisation reutilisables :

- series temporelles Matplotlib ;
- series temporelles interactives Plotly ;
- heatmap de correlation ;
- comparaison en barres ;
- graphique a double axe.

## 8. Dashboard Dash

Le dashboard principal est dans :

```text
dashboard/app.py
```

Il charge les donnees au demarrage :

- inflation ;
- PIB ;
- donnees agricoles ;
- comparaison Afrique de l'Ouest ;
- climat ;
- risques ;
- previsions ;
- prix de marche ;
- GeoJSON des regions.

### Onglets disponibles

Le dashboard contient les onglets suivants :

- Vue : synthese generale avec KPI et graphiques principaux ;
- Cultures : analyse detaillee par culture ;
- Macro : inflation, PIB et comparaison regionale ;
- Carte : carte regionale du Togo ;
- Climat : precipitation et temperature ;
- Previsions : rendements et production jusqu'en 2030 ;
- Marches : prix regionaux, volatilite et arbitrage ;
- Risques : evolution du score de risque.

### Filtres disponibles

L'utilisateur peut filtrer par :

- periode ;
- categorie de culture ;
- culture ;
- indicateur.

Des presets existent pour :

- historique ;
- toutes les donnees ;
- previsions.

### Exports

Le dashboard permet :

- export CSV ;
- export Excel ;
- export PDF.

### Theme

L'application supporte un theme clair et un theme sombre via un interrupteur.

### Authentification

Le fichier `dashboard/app.py` expose `server = app.server` pour Gunicorn et contient un hook `server.before_request`. La configuration de deploiement Render definit :

- `DASH_USER` ;
- `DASH_PASSWORD`.

Sur Render, le mot de passe est genere automatiquement si l'on utilise `render.yaml`.

## 9. Scripts utilitaires

### `scripts/fetch_external_data.py`

Telecharge des donnees externes dans `data/external/`, notamment :

- prix FAOSTAT pour quelques produits ;
- CPI World Bank du Togo.

Ce script necessite une connexion Internet.

### `scripts/retry_faostat.py`

Script de nouvelle tentative pour les donnees FAOSTAT.

### `scripts/compare_external_vs_local.py`

Compare les donnees externes avec les donnees locales normalisees.

### `scripts/summarize_local_prices.py`

Produit des statistiques de synthese sur les prix locaux.

### `scripts/generate_report_pdf.py`

Genere un rapport PDF a partir des donnees et graphiques locaux disponibles dans `data/external/`.

## 10. Deploiement Render

Le fichier `render.yaml` configure un service web Python :

```yaml
services:
  - type: web
    name: agridash-togo
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn dashboard.app:server --bind 0.0.0.0:$PORT --timeout 120 --workers 2
```

Render installe les dependances, puis lance Gunicorn sur le serveur Flask expose par Dash.

Variables d'environnement configurees :

- `DASH_USER=admin` ;
- `DASH_PASSWORD` genere automatiquement ;
- `PYTHONUNBUFFERED=1`.

Le health check utilise :

```text
/_alive
```

## 11. Flux de donnees global

Le flux general du projet est le suivant :

1. Les fichiers CSV World Bank sont lus depuis les dossiers `API_*`.
2. Les donnees macroeconomiques sont filtrees pour le Togo.
3. Les donnees agricoles locales ou derivees sont chargees depuis `data/togo_wb_agriculture.csv`.
4. Les series agricoles par culture sont estimees dans `src/agriculture_data.py`.
5. Les donnees climatiques sont lues depuis le cache ou telechargees depuis NASA POWER.
6. Les prix de marche sont lus depuis le cache ou generes.
7. Les risques sont calcules via `SupplyChainRiskModel`.
8. Les previsions sont chargees ou generees via Prophet.
9. Le dashboard combine ces donnees dans des graphiques, tableaux et exports.

## 12. Fichiers de sortie et caches

Les principaux fichiers generes ou utilises comme cache sont :

```text
data/togo_climate_nasa_power.csv
data/togo_forecasts.csv
data/togo_market_prices.csv
data/togo_wb_agriculture.csv
data/external/analysis_report.json
data/external/comparison_report_local.csv
data/external/local_prices_normalized.csv
data/external/report_local_only.pdf
data/external/summary_per_crop.csv
data/external/summary_stats_local_prices.csv
```

Ces fichiers permettent d'eviter de recalculer ou retelecharger les donnees a chaque lancement.

## 13. Limites connues

Quelques points sont importants pour comprendre le niveau de maturite du projet :

- une partie des donnees agricoles est estimee ou simulee, pas forcement observee directement ;
- les prix de marche sont generes a partir d'hypotheses, pas issus d'une base officielle complete ;
- le calcul d'arbitrage regional est indicatif et ne prend pas en compte les couts logistiques ;
- le score de risque est une construction analytique simplifiee ;
- les previsions restent des projections statistiques et doivent etre interpretees avec prudence ;
- les appels NASA POWER et FAOSTAT necessitent Internet si les caches ne sont pas presents ;
- les modeles ne remplacent pas une validation econometrique ou metier approfondie.

## 14. Ameliorations recommandees

Pour faire evoluer le projet, les priorites seraient :

1. documenter la provenance exacte de chaque donnee estimee ;
2. ajouter des donnees de prix observees par marche ;
3. integrer les couts de transport dans l'analyse d'arbitrage ;
4. ajouter une commande unique de type `make run` ou `python3 -m src.pipeline` enrichie ;
5. separer les donnees simulees des donnees observees dans l'interface ;
6. ajouter une page methodologie dans le dashboard ;
7. etendre les tests aux callbacks Dash et aux scripts de rapport.

## 15. Commandes utiles

```bash
# Creer l'environnement virtuel
python3 -m venv .venv

# Activer l'environnement
source .venv/bin/activate

# Installer les dependances
pip install -r requirements.txt

# Lancer le dashboard
python3 dashboard/app.py

# Lancer le pipeline
python3 -m src.pipeline

# Generer les previsions
python3 -m src.forecast

# Recuperer des donnees externes
python3 scripts/fetch_external_data.py

# Generer le rapport PDF
python3 scripts/generate_report_pdf.py

# Lancer les tests
python3 -m pytest
```

## 16. Resume executif

AgriDash Togo est un outil d'aide a l'analyse des filieres agricoles togolaises. Il centralise des donnees economiques, agricoles, climatiques et de marche, puis les transforme en indicateurs visuels pour le pilotage. Le projet est deja structure autour d'un dashboard complet, de modules Python reutilisables et d'un deploiement Render. Les prochaines evolutions doivent surtout renforcer la qualite des donnees, la robustesse des previsions et la validation des hypotheses metier.
