import sys, io, base64, json
from pathlib import Path
# Ensure project root is on sys.path so `src` imports work regardless of CWD
proj_root = str(Path(__file__).resolve().parent.parent)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

import dash
from dash import dcc, html, Input, Output, dash_table, ctx, callback, no_update
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

from src.data_loader import load_all_togo_data, get_wa_comparison, load_wb_agri_cache
from src.agriculture_data import get_togo_agriculture_data, PIA_TRANSFORMATION_POTENTIAL, EXPORT_CROPS
from src import togo_map
from src import market_prices as mp
from src.climate_data import get_togo_climate_data
from src.models import SupplyChainRiskModel
from src.forecast import generate_forecasts, get_forecast_summary, FORECAST_YEARS
from src.config import ALL_CROPS, CROP_CATEGORIES

data = load_all_togo_data()
inflation = data["inflation"]
gdp = data["gdp"]
agri_data = get_togo_agriculture_data()
wa_inflation = get_wa_comparison("inflation")
climate_data = get_togo_climate_data()
climate_natl = climate_data[climate_data["Region"] == "National"].copy()
agri_wb = load_wb_agri_cache()

merged = inflation.rename(columns={"Value": "inflation"})
gdp_r = gdp.rename(columns={"Value": "gdp"})
merged = merged.merge(gdp_r[["Year", "gdp"]], on="Year")
merged = merged.merge(climate_natl[["Year", "precip_mm", "temp_c"]], on="Year", how="left")

# New real WB indicators
if len(agri_wb):
    for col, label in [("AG.CON.FERT.ZS", "fert_kg_ha"),
                        ("PA.NUS.FCRF", "exchange_rate"),
                        ("NY.GDP.DEFL.KD.ZG", "gdp_deflator"),
                        ("AG.LND.ARBL.ZS", "arable_pct"),
                        ("AG.PRD.FOOD.XD", "food_index")]:
        sub = agri_wb[agri_wb["indicator"] == col][["Year", "value"]].copy()
        if len(sub):
            sub = sub.rename(columns={"value": label})
            sub["Year"] = sub["Year"].astype(int)
            merged = merged.merge(sub, on="Year", how="left")

risk_model = SupplyChainRiskModel()
risk_df = risk_model.compute_risk_score(merged)

forecasts = generate_forecasts()
forecast_summary = get_forecast_summary(forecasts)

market_df = mp.get_market_prices()
MARKET_REGIONS = list(mp.BASE_PRICES_FCFA_KEYS)

CROP_OPTIONS = [{"label": f"{c}", "value": c}
                for c in sorted(ALL_CROPS)]
CAT_OPTIONS = [{"label": CROP_CATEGORIES[c], "value": c}
               for c in CROP_CATEGORIES]

YEAR_MIN = 2000
FORECAST_YEARS = [2025, 2026, 2027, 2028, 2029, 2030]
DATA_YEAR_MAX = int(max(
    int(agri_data["Year"].max()),
    int(inflation["Year"].max()) if "Year" in inflation.columns else YEAR_MIN,
    int(gdp["Year"].max()) if "Year" in gdp.columns else YEAR_MIN,
    int(market_df["Year"].max()) if "Year" in market_df.columns else YEAR_MIN,
    max(FORECAST_YEARS),
))

# Power BI–inspired palette (hex values mirrored in dashboard/assets/custom.css).
# Categorical order matches the CSS --c1..--c8 tokens so charts and UI agree.
COLORS = {
    "primary": "#118DFF", "secondary": "#2396D4",
    "success": "#2E9F63", "warning": "#F2A93B", "danger": "#D13438",
    "dark": "#252423", "light": "#F2F2F2",
    "céréale": "#118DFF", "tubercule": "#E66C37",
    "oléagineux": "#F2A93B", "fibre": "#9C6ADE", "export": "#0099A6",
}
# Categorical colorway for traces that don't set an explicit color.
COLORWAY = ["#118DFF", "#0099A6", "#2E9F63", "#F2A93B", "#E66C37", "#9C6ADE", "#D13438", "#12239E"]
# Risk-level → color (semantic, consistent across gauge/pie/series).
RISK_COLORS = {"Faible": "#2E9F63", "Modéré": "#F2A93B",
               "Élevé": "#E66C37", "Critique": "#D13438"}
# Sequential blue ramp (low→high) for the production map.
MAP_RAMP = ["#E8F4FE", "#B4DAF6", "#6FB0E3", "#2E86D8", "#0B5DA8"]

FONT_FAMILY = '"Segoe UI", "Segoe UI Web (West European)", -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif'

TOGO_GEOJSON = togo_map.load_geojson()
REGION_NAME_MAP = togo_map.get_region_map()
regions_df = togo_map.get_region_production_data(agri_data, 2024)

# Theme tokens — mirror dashboard/assets/custom.css :root & [data-theme="dark"].
THEMES = {
    "light": {
        "bg": "#F2F2F2", "card_bg": "#FFFFFF", "text": "#252423",
        "border": "#E5E5E5", "navbar": "#FFFFFF", "graph_bg": "#FFFFFF",
        "muted": "#605E5C", "grid": "#EAEAEA", "header_bg": "#FFFFFF",
        "header_bd": "#E5E5E5",
    },
    "dark": {
        "bg": "#252423", "card_bg": "#2A2A2A", "text": "#E6E6E6",
        "border": "#3D3D3D", "navbar": "#252423", "graph_bg": "#2A2A2A",
        "muted": "#A8A8A8", "grid": "#353535", "header_bg": "#252423",
        "header_bd": "#3D3D3D",
    },
}

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    title="AgriDash Togo - Pilotage Agricole Prédictif",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

TAB_IDS = ["tab-dash", "tab-crops", "tab-macro", "tab-map", "tab-climate",
            "tab-forecast", "tab-markets", "tab-risks"]
TAB_LABELS = [("Vue", "fa-home"), ("Cultures", "fa-seedling"), ("Macro", "fa-chart-bar"),
              ("Carte", "fa-map-marked-alt"), ("Climat", "fa-cloud-rain"),
              ("Prévisions", "fa-chart-line"), ("Marchés", "fa-store"),
              ("Risques", "fa-exclamation-triangle")]

# Header is flat — colors come from CSS variables scoped on [data-theme].
navbar_style = {}

navbar = html.Div([
    dbc.Navbar(
        dbc.Container([
            html.Div([
                html.Div(html.I(className="fas fa-leaf"), className="me-2"),
                html.Div([
                    html.Span("AgriDash", className="fw-bold"),
                    html.Span("Togo", className="fw-light ms-1"),
                ], className="d-flex align-items-baseline"),
                html.Span("PIA", className="badge rounded-pill ms-2 px-2",
                          style={"fontSize": "0.6rem", "backgroundColor": "rgba(46,159,99,0.14)",
                                 "color": "var(--good)", "border": "1px solid rgba(46,159,99,0.4)", "fontWeight": 600}),
            ], className="d-flex align-items-center flex-shrink-0", id="brand"),
            dbc.NavbarToggler(id="navbar-toggler", className="border-0 ms-auto"),
            dbc.Collapse(
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink([html.I(className=f"fas {icon} me-1"), label], href="#", id=tab_id, className="nav-custom-link"),
                               className="nav-custom-item")
                    for (label, icon), tab_id in zip(TAB_LABELS, TAB_IDS)
                ], navbar=True, className="mx-auto"),
                id="navbar-collapse", navbar=True,
            ),
            html.Div([
                dbc.Button(html.I(className="fas fa-file-pdf"), id="btn-pdf", size="sm",
                           color="secondary", outline=True, className="me-2"),
                dbc.Switch(id="theme-toggle", value=False,
                           label=html.I(className="fas fa-moon", style={"color": "var(--muted)", "fontSize": "0.85rem"})),
            ], className="d-flex align-items-center flex-shrink-0 ms-2 d-none d-lg-flex"),
        ], fluid=True, className="d-flex flex-nowrap align-items-center px-3"),
        sticky="top", className="mb-2",
        style=navbar_style, dark=False,
    ),
], id="navbar-container", style=navbar_style)

YEAR_PRESETS = [
    {"label": "Historique", "value": [2000, 2024], "id": "preset-hist"},
    {"label": "Tout", "value": [2000, DATA_YEAR_MAX], "id": "preset-tout"},
    {"label": "Prévisions", "value": [2025, DATA_YEAR_MAX], "id": "preset-fcst"},
]

crops_for_kpi = ["maïs", "manioc", "igname", "coton", "soja"]
ALL_CROP_NAMES = sorted(ALL_CROPS.keys())

filtres = html.Div([
    dbc.Card([
        dbc.CardBody([
            html.Div([
                html.I(className="fas fa-calendar-alt me-2"),
                html.Span("Période", className="fw-bold me-3"),
                dbc.ButtonGroup([dbc.Button(p["label"], id=p["id"], color="primary", outline=True, size="sm", className="me-1") for p in YEAR_PRESETS]),
            ], className="d-flex align-items-center mb-2"),
            dcc.RangeSlider(
                id="year-slider", min=YEAR_MIN, max=DATA_YEAR_MAX, step=1,
                value=[2000, DATA_YEAR_MAX],
                marks={y: str(y) for y in sorted(set([2000, 2005, 2010, 2015, 2020, 2025, 2030]))},
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ]),
    ], className="mb-2 shadow-sm", id="filtres-year-card"),
    dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label([html.I(className="fas fa-tags me-1"), "Catégorie"],
                               className="fw-semibold small mb-1"),
                    dcc.Dropdown(id="cat-dropdown", options=CAT_OPTIONS, multi=True,
                                 placeholder="Toutes catégories"),
                ], width=3),
                dbc.Col([
                    html.Label([html.I(className="fas fa-seedling me-1"), "Culture"],
                               className="fw-semibold small mb-1"),
                    dcc.Dropdown(id="crop-dropdown", options=CROP_OPTIONS, multi=True,
                                 value=["maïs", "soja", "coton"],
                                 placeholder="Sélectionnez des cultures"),
                ], width=3),
                dbc.Col([
                    html.Label([html.I(className="fas fa-chart-line me-1"), "Indicateur"],
                               className="fw-semibold small mb-1"),
                dcc.Dropdown(id="indicator-dropdown", options=[
                    {"label": "Inflation (%)", "value": "inflation"},
                    {"label": "PIB ($)", "value": "gdp"},
                    {"label": "Rendement (t/ha)", "value": "yield_t_ha"},
                    {"label": "Production (tonnes)", "value": "production_t"},
                    {"label": "Superficie (ha)", "value": "area_ha"},
                    {"label": "Prix ($/t)", "value": "price_usd_t"},
                    {"label": "Précipitations (mm)", "value": "precip_mm"},
                    {"label": "Température (°C)", "value": "temp_c"},
                    {"label": "Engrais (kg/ha)", "value": "fert_kg_ha"},
                    {"label": "Taux de change (XAF/$)", "value": "exchange_rate"},
                    {"label": "Déflateur PIB (%)", "value": "gdp_deflator"},
                    {"label": "Indice production alimentaire", "value": "food_index"},
                ], value="yield_t_ha", clearable=False),
                ], width=3),
                dbc.Col([
                    html.Label([html.I(className="fas fa-download me-1"), "Export"],
                               className="fw-semibold small mb-1"),
                    dbc.ButtonGroup([
                        dbc.Button("CSV", id="btn-csv", size="sm", color="secondary", outline=True, className="me-1"),
                        dbc.Button("Excel", id="btn-excel", size="sm", color="success", outline=True),
                    ], size="sm"),
                    dcc.Download(id="download-dataframe-csv"),
                    dcc.Download(id="download-dataframe-xlsx"),
                ], width=3),
            ], className="g-2"),
        ]),
    ], className="mb-3 shadow-sm", id="filtres-card"),
])

kpi_row = dbc.Row(id="kpi-row", className="mb-4 g-3")
tab_container = html.Div(id="tab-content")

app.layout = html.Div([
    navbar, dbc.Container([filtres, kpi_row, tab_container], fluid=True, id="main-container"),
    dcc.Store(id="theme-store", data="light"),
    dcc.Store(id="active-tab", data="tab-dash"),
    dcc.Store(id="selected-region", data=""),
    dcc.Download(id="download-pdf"),
], id="app-container", **{'data-theme': 'light'})


# ============================================================
# CALLBACKS
# ============================================================

@callback(
    Output("theme-store", "data"), Output("app-container", "style"),
    Output("filtres-year-card", "style"), Output("filtres-card", "style"),
    Output("app-container", "data-theme"), Output("navbar-container", "style"),
    Input("theme-toggle", "value"),
)
def toggle_theme(dark):
    # All visual tokens live in CSS variables scoped on [data-theme]; the only
    # job here is to flip the attribute and broadcast the theme name to graphs.
    theme_name = "dark" if dark else "light"
    return theme_name, {}, {}, {}, theme_name, {}

@callback(Output("year-slider", "value"), Input("preset-hist", "n_clicks"),
          Input("preset-tout", "n_clicks"), Input("preset-fcst", "n_clicks"))
def preset_click(*_):
    tid = ctx.triggered_id if ctx.triggered_id else None
    if tid == "preset-hist": return [2000, 2024]
    if tid == "preset-tout": return [2000, DATA_YEAR_MAX]
    if tid == "preset-fcst": return [2025, DATA_YEAR_MAX]
    return no_update

navlink_outputs = [Output(tid, "active") for tid in TAB_IDS]

@callback([Output("active-tab", "data"), *navlink_outputs],
          Input("tab-dash", "n_clicks"), Input("tab-crops", "n_clicks"),
          Input("tab-macro", "n_clicks"), Input("tab-map", "n_clicks"),
          Input("tab-climate", "n_clicks"), Input("tab-forecast", "n_clicks"),
          Input("tab-markets", "n_clicks"), Input("tab-risks", "n_clicks"))
def set_active_tab(*_):
    active = ctx.triggered_id if ctx.triggered_id else "tab-dash"
    return [active] + [tid == active for tid in TAB_IDS]

@callback(Output("crop-dropdown", "value"), Input("cat-dropdown", "value"))
def filter_crops_by_cat(cats):
    if not cats:
        return no_update
    filtered = [c for c in ALL_CROP_NAMES if ALL_CROPS[c]["category"] in cats]
    return filtered if filtered else no_update


# ============================================================
# KPI CALLBACK
# ============================================================
@callback(Output("kpi-row", "children"), Input("year-slider", "value"),
          Input("cat-dropdown", "value"), Input("crop-dropdown", "value"),
          Input("theme-store", "data"))
def update_kpis(years, cats, crops, theme):
    y_min, y_max = years

    adf = agri_data[(agri_data["Year"] >= y_min) & (agri_data["Year"] <= y_max)].copy()
    if cats:
        adf = adf[adf["category"].isin(cats)]
    if crops:
        adf = adf[adf["crop"].isin(crops)]

    adf_lastyear = adf[adf["Year"] == y_max]
    prod_total = adf_lastyear["production_t"].sum()
    food_total = adf_lastyear[adf_lastyear["staple"] == True]["production_t"].sum()

    export_crops = adf_lastyear[adf_lastyear["crop"].isin(EXPORT_CROPS) & adf_lastyear["price_usd_t"].notna()]
    if len(export_crops):
        export_val = (export_crops["production_t"] * export_crops["price_usd_t"]).sum() / 1e6
    else:
        export_val = 0

    rdf = risk_df[(risk_df["Year"] >= y_min) & (risk_df["Year"] <= y_max)]
    if len(rdf):
        last_risk = rdf.iloc[-1]
        rc, rs = last_risk["risk_level"], last_risk["risk_score"]
    else:
        rc, rs = "N/D", 0
    rcol = "success" if rc == "Faible" else "warning" if rc in ["Modéré","Élevé"] else "danger"
    ricon = "fa-check-circle" if rc == "Faible" else "fa-exclamation-triangle" if rc=="Modéré" else "fa-times-circle"

    def kpi_card(icon, label, value, subtitle, color, _border_color):
        return dbc.Col(dbc.Card([
            html.Div(className="kpi-accent", style={"backgroundColor": color}),
            dbc.CardBody([
                html.Div([
                    html.I(className=f"fas {icon} kpi-icon", style={"color": color}),
                    html.Span(label, className="kpi-label"),
                ], className="kpi-head"),
                html.Div(value, className="kpi-value"),
                html.Div(subtitle, className="kpi-sub"),
            ], className="kpi-body"),
        ], className="kpi-card shadow-sm h-100"), width=3)

    def fmt_t(v):
        if v >= 1e6: return f"{v/1e6:.1f}M"
        if v >= 1e3: return f"{v/1e3:.0f}k"
        return f"{v:.0f}"

    n_crops = adf_lastyear["crop"].nunique() if len(adf_lastyear) else 0
    cagr = ((adf[adf["Year"]==y_max]["production_t"].sum() / max(adf[adf["Year"]==y_min]["production_t"].sum(), 1)) ** (1/max(y_max-y_min, 1)) - 1) * 100 if len(adf) and adf[adf["Year"]==y_max]["production_t"].sum() > 0 and adf[adf["Year"]==y_min]["production_t"].sum() > 0 else 0

    export_subtitle = f"{', '.join(sorted(export_crops['crop'].unique()))}" if len(export_crops) else "—"
    return [
        kpi_card("fa-tractor", "Prod. Totale", fmt_t(prod_total),
                 f"tonnes ({y_max}) | {n_crops} culture{'s' if n_crops>1 else ''}",
                 COLORS["primary"], COLORS["primary"]),
        kpi_card("fa-apple-alt", "Prod. Alimentaire", fmt_t(food_total),
                 f"tonnes ({y_max}) | cultures de base",
                 COLORS["success"], COLORS["success"]),
        kpi_card("fa-dollar-sign", "Valeur Export", f"{export_val:.0f}M$",
                 export_subtitle,
                 COLORS["warning"], COLORS["warning"]),
        kpi_card(ricon, "Risque", rc,
             f"Score: {rs:.3f} | TCAM: {cagr:+.1f}%",
                 COLORS[rcol], COLORS[rcol]),
    ]


# ============================================================
# TAB RENDERER
# ============================================================
@callback(Output("tab-content", "children"), Input("active-tab", "data"),
          Input("year-slider", "value"), Input("crop-dropdown", "value"),
          Input("indicator-dropdown", "value"), Input("theme-store", "data"))
def render_tab(tab, years, crops, indicator, theme):
    t = THEMES.get(theme, THEMES["light"])
    if tab == "tab-crops":    return render_crops_tab(years, crops or [], t)
    if tab == "tab-macro":    return render_macro_tab(years, t)
    if tab == "tab-map":      return render_map_tab(t)
    if tab == "tab-climate":  return render_climate_tab(years, t)
    if tab == "tab-forecast": return render_forecast_tab(years, crops or ["maïs", "soja", "coton"], t)
    if tab == "tab-markets":  return render_markets_tab(years, crops or ["maïs"], t)
    if tab == "tab-risks":    return render_risks_tab(years, t)
    return render_dashboard_tab(years, crops or ["maïs", "soja", "coton"], indicator, t)


def section(title, graph_id, col_width=6, height=None):
    return dbc.Col(dbc.Card([
        dbc.CardHeader(html.H6(title, className="mb-0")),
        dbc.CardBody(dcc.Graph(id=graph_id, config={"displayModeBar": False},
                                style={"height": height or 360})),
    ], className="shadow-sm h-100 ds-section"), width=col_width)


# ============================================================
# TAB: VUE D'ENSEMBLE
# ============================================================
def render_dashboard_tab(years, crops, indicator, t):
    return dbc.Row([
        dbc.Col([
            dbc.Row([
                section("Évolution des Rendements", "dash-yield", 6),
                section("Production par Culture", "dash-prod", 6),
            ], className="mb-4 g-3"),
            dbc.Row([
                section("Production par Catégorie", "dash-cat-pie", 5),
                section(f"{indicator.replace('_',' ').title()} dans le temps", "dash-indicator", 7),
            ], className="mb-4 g-3"),
        ], width=9),
        dbc.Col([
            section(f"Score de Risque", "dash-gauge", 12, "220px"),
            dbc.Card([
                dbc.CardHeader(html.H6("Production 2023 par Culture", className="fw-bold mb-0")),
                dbc.CardBody(dcc.Graph(id="dash-prod-bar", config={"displayModeBar": False})),
            ], className="shadow-sm mb-4"),
        ], width=3),
    ], className="g-3")


# ============================================================
# TAB: CULTURES (détaillé)
# ============================================================
def render_crops_tab(years, crops, t):
    if not crops:
        crops = ["maïs"]
    last_year = int(agri_data["Year"].max())
    last_data = agri_data[agri_data["Year"] == last_year].groupby("crop")["production_t"].sum().to_dict()
    prod_df = pd.DataFrame([
        {"Culture": c, "Catégorie": ALL_CROPS[c]["category"],
         "Aliment de base": "Oui" if ALL_CROPS[c]["staple"] else "Non",
         f"Production {last_year} (t)": f"{int(last_data.get(c, 0)):,}"}
        for c in ALL_CROP_NAMES
    ])
    pia_rows = []
    for k, v in PIA_TRANSFORMATION_POTENTIAL.items():
        pia_rows.append({"Filière": k, "Taux Transf.": f"{v['taux_transfo']:.0%}",
                         "Produits": ", ".join(v["produits"])})
    pia_df = pd.DataFrame(pia_rows)

    return dbc.Row([
        dbc.Col([
            dbc.Row([
                section("Rendement (séries)", "crops-yield", 6),
                section("Production", "crops-prod", 6),
            ], className="mb-4 g-3"),
            dbc.Row([
                section("Superficie Récoltée", "crops-area", 6),
                section("Prix ($/t)", "crops-price", 6),
            ], className="mb-4 g-3"),
        ], width=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H6("Production 2023", className="fw-bold mb-0")),
                dbc.CardBody(dash_table.DataTable(
                    data=prod_df.to_dict("records"),
                    columns=[{"name": c, "id": c} for c in prod_df.columns],
                    style_table={"overflowX": "auto", "maxHeight": "300px", "overflowY": "auto"},
                    style_cell={"textAlign": "left", "padding": "4px", "fontSize": 12,
                                "backgroundColor": t["card_bg"], "color": t["text"]},
                    style_header={"fontWeight": "bold"},
                    page_size=8,
                )),
            ], className="shadow-sm mb-4"),
            dbc.Card([
                dbc.CardHeader(html.H6("Potentiel PIA", className="fw-bold mb-0")),
                dbc.CardBody(dash_table.DataTable(
                    data=pia_df.to_dict("records"),
                    columns=[{"name": c, "id": c} for c in pia_df.columns],
                    style_table={"overflowX": "auto"},
                    style_cell={"textAlign": "left", "padding": "8px",
                                "backgroundColor": t["card_bg"], "color": t["text"]},
                    style_header={"fontWeight": "bold"},
                )),
            ], className="shadow-sm"),
        ], width=4),
    ], className="g-3")


# ============================================================
# TAB: MACRO
# ============================================================
def render_macro_tab(years, t):
    return dbc.Row([
        dbc.Col([
            dbc.Row([
                section("PIB vs Inflation", "macro-dual", 6),
                section("Comparaison Régionale", "macro-wa", 6),
            ], className="mb-4 g-3"),
            dbc.Row([
                section("Distribution", "macro-dist", 12),
            ], className="g-3"),
        ], width=9),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H6("Statistiques Clés", className="fw-bold mb-0")),
                dbc.CardBody(id="macro-stats"),
            ], className="shadow-sm mb-4"),
            dbc.Card([
                dbc.CardHeader(html.H6("Agriculture WB", className="fw-bold mb-0")),
                dbc.CardBody(dash_table.DataTable(
                    id="macro-agri-table",
                    style_cell={"textAlign": "left", "padding": "4px", "fontSize": 12,
                                "backgroundColor": t["card_bg"], "color": t["text"]},
                    style_header={"fontWeight": "bold"},
                )),
            ], className="shadow-sm mb-4"),
            dbc.Card([
                dbc.CardHeader(html.H6("Télécharger", className="fw-bold mb-0")),
                dbc.CardBody([
                    dbc.Button([html.I(className="fas fa-file-csv me-2"), "CSV"],
                               id="btn-macro-csv", color="secondary", outline=True, size="sm", className="me-2"),
                    dbc.Button([html.I(className="fas fa-file-excel me-2"), "Excel"],
                               id="btn-macro-xlsx", color="success", outline=True, size="sm"),
                    dcc.Download(id="dl-macro-csv"), dcc.Download(id="dl-macro-xlsx"),
                ]),
            ], className="shadow-sm"),
        ], width=3),
    ], className="g-3")


# ============================================================
# TAB: CARTE
# ============================================================
def render_map_tab(t):
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-map-marked-alt me-1"),
                    "Carte Agricole du Togo",
                    html.Span("  cliquer sur une région pour explorer", className="small text-muted fw-normal"),
                ], className="fw-bold"),
                dbc.CardBody(dcc.Graph(id="map-chart", config={"displayModeBar": False})),
            ], className="shadow-sm mb-4"),
        ], width=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-table me-1"),
                    "Production par Région",
                ], className="fw-bold"),
                dbc.CardBody([
                    dash_table.DataTable(
                        id="map-table",
                        data=regions_df.to_dict("records"),
                        columns=[{"name": "Région", "id": "region"},
                                 {"name": "Production (t)", "id": "production_t",
                                  "type": "numeric", "format": {"specifier": ",.0f"}},
                                 {"name": "Part (%)", "id": "production_pct",
                                  "type": "numeric", "format": {"specifier": ".1f"}}],
                        style_cell={"textAlign": "left", "padding": "8px",
                                    "backgroundColor": t["card_bg"], "color": t["text"]},
                        style_header={"fontWeight": "bold"},
                        row_selectable="single",
                        selected_rows=[],
                    ),
                    html.Div(id="region-detail", className="mt-3 small"),
                    html.Hr(),
                    html.H6([html.I(className="fas fa-industry me-1"), "Infrastructure PIA"], className="fw-bold"),
                    html.P("La Plateforme Industrielle d'Adétikopé (PIA) est le hub "
                           "agro-industriel stratégique pour la transformation locale.",
                           className="small text-muted"),
                    html.Ul([
                        html.Li([html.I(className="fas fa-arrow-right fa-xs me-1"), "Transformation soja: huile, tourteau, lait"], className="small"),
                        html.Li([html.I(className="fas fa-arrow-right fa-xs me-1"), "Égrenage coton: fibre, huile de coton"], className="small"),
                        html.Li([html.I(className="fas fa-arrow-right fa-xs me-1"), "Décorticage noix de cajou"], className="small"),
                        html.Li([html.I(className="fas fa-arrow-right fa-xs me-1"), "Minoterie maïs et manioc"], className="small"),
                        html.Li([html.I(className="fas fa-arrow-right fa-xs me-1"), "Zone franche avec incentives fiscales"], className="small"),
                    ], className="small"),
                ]),
            ], className="shadow-sm"),
        ], width=4),
    ], className="g-3")


@callback(
    Output("selected-region", "data"),
    Output("map-table", "data"),
    Output("map-table", "selected_rows"),
    Output("region-detail", "children"),
    Input("map-chart", "clickData"),
    Input("year-slider", "value"),
    Input("selected-region", "data"),
)
def highlight_region(clickData, years, current_selection):
    rdf = togo_map.get_region_production_data(agri_data, years[1])

    ctx_trigger = dash.callback_context.triggered[0]["prop_id"] if dash.callback_context.triggered else ""

    if "map-chart.clickData" in ctx_trigger and clickData:
        try:
            pt = clickData.get("points", [])[0]
            customdata = pt.get("customdata")
            location = customdata or pt.get("location") or pt.get("hovertext") or ""
            region_name = REGION_NAME_MAP.get(location, location)
            if region_name == current_selection:
                return "", rdf.to_dict("records"), [], html.Div()
            sel = rdf[rdf["region"] == region_name]
            if len(sel):
                idx = sel.index[0]
                crops = togo_map.get_region_crops(agri_data, region_name, years[1])
                detail = html.Div([
                    html.P([html.I(className="fas fa-info-circle me-1"),
                            f"Région sélectionnée: {region_name}"],
                           className="fw-bold mb-2"),
                    html.P([html.I(className="fas fa-seedling me-1"),
                            f"Production: {sel.iloc[0]['production_t']/1e6:.2f}M t"],
                           className="mb-1 small"),
                    html.P([html.I(className="fas fa-percentage me-1"),
                            f"Part nationale: {sel.iloc[0]['production_pct']:.1f}%"],
                           className="mb-2 small"),
                    html.Hr(style={"margin": "6px 0"}),
                    html.P("Top cultures:", className="small fw-bold mb-1"),
                    html.Ul(
                        [html.Li(f"{r['crop']}: {r['region_prod_t']/1e6:.2f}M t",
                                 className="small")
                         for _, r in crops.head(4).iterrows()],
                        className="mb-0 ps-3",
                    ),
                ])
                return region_name, sel.to_dict("records"), [int(idx)], detail
        except Exception:
            pass
        return "", rdf.to_dict("records"), [], html.Div()

    if current_selection and current_selection in rdf["region"].values:
        sel = rdf[rdf["region"] == current_selection]
        idx = int(sel.index[0])
        crops = togo_map.get_region_crops(agri_data, current_selection, years[1])
        detail = html.Div([
            html.P([html.I(className="fas fa-info-circle me-1"),
                    f"Région: {current_selection}"],
                   className="fw-bold mb-2"),
            html.P([html.I(className="fas fa-seedling me-1"),
                    f"Production: {sel.iloc[0]['production_t']/1e6:.2f}M t"],
                   className="mb-1 small"),
            html.P([html.I(className="fas fa-percentage me-1"),
                    f"Part nationale: {sel.iloc[0]['production_pct']:.1f}%"],
                   className="mb-2 small"),
            html.Hr(style={"margin": "6px 0"}),
            html.P("Top cultures:", className="small fw-bold mb-1"),
            html.Ul(
                [html.Li(f"{r['crop']}: {r['region_prod_t']/1e6:.2f}M t",
                         className="small")
                 for _, r in crops.head(4).iterrows()],
                className="mb-0 ps-3",
            ),
        ])
        return current_selection, sel.to_dict("records"), [idx], detail

    return "", rdf.to_dict("records"), [], html.Div()


# ============================================================
# TAB: CLIMAT
# ============================================================
def render_climate_tab(years, t):
    return dbc.Row([
        dbc.Col([
            dbc.Row([
                section("Précipitations Annuelles (NASA POWER)", "climate-precip", 6),
                section("Température Annuelle Moyenne", "climate-temp", 6),
            ], className="mb-4 g-3"),
            dbc.Row([
                section("Précipitations par Région", "climate-region-precip", 6),
                section("Température par Région", "climate-region-temp", 6),
            ], className="mb-4 g-3"),
        ], width=9),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H6("Résumé Climatique", className="fw-bold mb-0")),
                dbc.CardBody(id="climate-summary"),
            ], className="shadow-sm mb-4"),
            dbc.Card([
                dbc.CardHeader(html.H6("Corr. Climat-Rendement", className="fw-bold mb-0")),
                dbc.CardBody(dcc.Graph(id="climate-corr", config={"displayModeBar": False})),
            ], className="shadow-sm"),
        ], width=3),
    ], className="g-3")


# ============================================================
# TAB: PRÉVISIONS
# ============================================================
def render_forecast_tab(years, crops, t):
    fcst = forecasts.copy()
    if crops:
        fcst = fcst[fcst["crop"].isin(crops)]
    moderate = fcst[fcst["scenario"] == "modéré"].copy() if len(fcst) else pd.DataFrame()

    top_change = forecast_summary.nlargest(3, "prod_change_pct")[["crop", "prod_change_pct"]] if len(forecast_summary) else pd.DataFrame()

    return dbc.Row([
        dbc.Col([
            dbc.Row([
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H6(html.I(className="fas fa-calculator me-2"), className="fw-bold mb-2"),
                        html.H3("2025-2030", className="fw-bold text-primary mb-0"),
                        html.Small("Période de prévision", className="text-muted"),
                    ]),
                ], className="shadow-sm text-center h-100"), width=3),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H6(html.I(className="fas fa-seedling me-2"), className="fw-bold mb-2"),
                        html.H3(f"{fcst['crop'].nunique()}", className="fw-bold text-success mb-0"),
                        html.Small("Cultures projetées", className="text-muted"),
                    ]),
                ], className="shadow-sm text-center h-100"), width=3),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H6(html.I(className="fas fa-chart-bar me-2"), className="fw-bold mb-2"),
                        html.H3("3", className="fw-bold text-warning mb-0"),
                        html.Small("Scénarios climatiques", className="text-muted"),
                    ]),
                ], className="shadow-sm text-center h-100"), width=3),
                dbc.Col(dbc.Card([
                    dbc.CardBody([
                        html.H6(html.I(className="fas fa-arrow-up me-2"), className="fw-bold mb-2"),
                        html.H3(f"{top_change.iloc[0]['crop']}" if len(top_change) else "—",
                                className="fw-bold text-info mb-0", style={"fontSize": "1rem"}),
                        html.Small(f"Meilleure progression" if len(top_change) else "", className="text-muted"),
                    ]),
                ], className="shadow-sm text-center h-100"), width=3),
            ], className="mb-4 g-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-chart-line me-2"),
                            html.Span("Rendement : historique + prévisions Prophet", className="fw-bold"),
                            html.Span("  [zone = intervalle de confiance 95%]", className="small text-muted ms-2"),
                        ]),
                        dbc.CardBody(dcc.Graph(id="forecast-yield", config={"displayModeBar": False})),
                    ], className="shadow-sm mb-4"),
                ], width=12),
            ], className="g-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-industry me-2"),
                            html.Span("Production projetée par culture", className="fw-bold"),
                        ]),
                        dbc.CardBody(dcc.Graph(id="forecast-prod", config={"displayModeBar": False})),
                    ], className="shadow-sm mb-4"),
                ], width=12),
            ], className="g-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fas fa-balance-scale me-2"),
                            html.Span("Comparaison des scénarios climatiques", className="fw-bold"),
                        ]),
                        dbc.CardBody(dcc.Graph(id="forecast-scenario", config={"displayModeBar": False})),
                    ], className="shadow-sm"),
                ], width=12),
            ], className="g-3"),
        ], width=9),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-sliders-h me-1"),
                    "Scénario",
                ], className="fw-bold"),
                dbc.CardBody([
                    dbc.RadioItems(
                        id="scenario-select",
                        options=[
                            {"label": " Modéré (tendance)", "value": "modéré"},
                            {"label": " Optimiste (+12%)", "value": "optimiste"},
                            {"label": " Pessimiste (-15%)", "value": "pessimiste"},
                        ],
                        value="modéré",
                        labelStyle={"display": "block", "margin": "8px 0",
                                    "padding": "8px 12px",
                                    "borderRadius": "8px",
                                    "border": f"1px solid {t['border']}",
                                    "cursor": "pointer",
                                    "transition": "all 0.2s"},
                        labelCheckedStyle={
                            "backgroundColor": "rgba(46, 134, 193, 0.15)",
                            "borderColor": COLORS["secondary"],
                            "fontWeight": "bold",
                        },
                    ),
                ]),
            ], className="shadow-sm mb-4"),
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-table me-1"),
                    [html.I(className="fas fa-arrow-right me-1"), "Résumé 2025-2030"],
                ], className="fw-bold"),
                dbc.CardBody(dash_table.DataTable(
                    id="forecast-table",
                    style_cell={"textAlign": "left", "padding": "4px", "fontSize": 11,
                                "backgroundColor": t["card_bg"], "color": t["text"],
                                "border": "none"},
                    style_header={"fontWeight": "bold", "backgroundColor": "rgba(46, 134, 193, 0.1)"},
                    style_table={"overflowX": "auto"},
                    page_size=8,
                )),
            ], className="shadow-sm mb-4"),
            dbc.Card([
                dbc.CardHeader([
                    html.I(className="fas fa-gauge-high me-1"),
                    "Risque projeté 2030",
                ], className="fw-bold"),
                dbc.CardBody(dcc.Graph(id="forecast-risk-gauge", config={"displayModeBar": False},
                                       style={"height": "200px"})),
            ], className="shadow-sm"),
        ], width=3),
    ], className="g-3")


# ============================================================
# TAB: MARCHÉS
# ============================================================
def render_markets_tab(years, crops, t):
    return dbc.Row([
        dbc.Col([
            dbc.Row([
                section("Prix par Région (FCFA/kg)", "mkts-heatmap", 12, "500px"),
            ], className="mb-4 g-3"),
            dbc.Row([
                section("Évolution des Prix (FCFA/kg)", "mkts-ts", 6),
                section("Spread Prix par Région", "mkts-bar", 6),
            ], className="mb-4 g-3"),
        ], width=9),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H6([html.I(className="fas fa-store me-1"), "Résumé Prix"], className="fw-bold mb-0")),
                dbc.CardBody(id="mkts-summary"),
            ], className="shadow-sm mb-4"),
            dbc.Card([
                dbc.CardHeader(html.H6([html.I(className="fas fa-arrow-right me-1"), "Arbitrage"], className="fw-bold mb-0")),
                dbc.CardBody(id="mkts-arbitrage"),
            ], className="shadow-sm mb-4"),
            dbc.Card([
                dbc.CardHeader(html.H6([html.I(className="fas fa-download me-1"), "Export Marchés"], className="fw-bold mb-0")),
                dbc.CardBody([
                    dbc.Button([html.I(className="fas fa-file-csv me-2"), "CSV"],
                               id="btn-mkts-csv", color="secondary", outline=True, size="sm"),
                    dcc.Download(id="dl-mkts-csv"),
                ]),
            ], className="shadow-sm"),
        ], width=3),
    ], className="g-3")


# ============================================================
# TAB: RISQUES
# ============================================================
def render_risks_tab(years, t):
    ymin, ymax = years
    rdf = risk_df[(risk_df["Year"] >= ymin) & (risk_df["Year"] <= ymax)]
    alerts = []
    last = rdf.iloc[-1] if len(rdf) else None
    if last is not None:
        c = "success" if last["risk_level"]=="Faible" else "warning" if last["risk_level"] in ["Modéré","Élevé"] else "danger"
        alerts.append(dbc.Alert([
            html.H5([html.I(className="fas fa-info-circle me-2"), f"Niveau actuel: {last['risk_level']}"], className="alert-heading"),
            html.P(f"Score: {last['risk_score']:.4f} — {int(last['Year'])}"),
        ], color=c, className="mb-2"))
    high = rdf[rdf["risk_level"].isin(["Élevé","Critique"])]
    if len(high):
        alerts.append(dbc.Alert([
            html.H5([html.I(className="fas fa-exclamation-triangle me-2 text-danger"), f"{len(high)} période(s) critique(s)"], className="alert-heading"),
            html.P(", ".join(str(int(y)) for y in high["Year"].values)),
        ], color="danger", className="mb-2"))
    if abs(merged["inflation"].iloc[-1]) > 8:
        alerts.append(dbc.Alert([
            html.H5("Alerte Inflation", className="alert-heading"),
            html.P(f"{merged['inflation'].iloc[-1]:.1f}% — risque sur intrants"),
        ], color="danger", className="mb-2"))
    if not alerts:
        alerts.append(html.P("Aucune alerte active.", className="text-success fw-bold"))

    return dbc.Row([
        dbc.Col([
            dbc.Row([
                section("Score de Risque (série)", "risk-ts", 6),
                section("Répartition des Niveaux", "risk-pie", 6),
            ], className="mb-4 g-3"),
        ], width=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H6("Alertes", className="fw-bold mb-0")),
                dbc.CardBody(alerts),
            ], className="shadow-sm mb-4"),
            dbc.Card([
                dbc.CardHeader(html.H6("Données (15 dernières)", className="fw-bold mb-0")),
                dbc.CardBody(dash_table.DataTable(
                    data=rdf.tail(15).round(3).reset_index().to_dict("records"),
                    columns=[{"name": c, "id": c} for c in rdf.tail(15).reset_index().columns],
                    style_table={"overflowX": "auto", "maxHeight": "300px", "overflowY": "auto"},
                    style_cell={"textAlign": "left", "padding": "6px", "fontSize": 12,
                                "backgroundColor": t["card_bg"], "color": t["text"]},
                    style_header={"fontWeight": "bold"},
                    page_size=8,
                )),
            ], className="shadow-sm"),
        ], width=4),
    ], className="g-3")


# ============================================================
# DOWNLOAD CALLBACKS
# ============================================================
@callback(Output("download-dataframe-csv", "data"),
          Input("btn-csv", "n_clicks"), prevent_initial_call=True)
def dl_csv(_):
    df = agri_data.pivot_table(index="Year", columns="crop",
        values=["yield_t_ha", "production_t", "area_ha", "price_usd_t"])
    df.columns = [f"{c[0]}_{c[1]}" for c in df.columns]
    out = merged.merge(df.reset_index(), on="Year", how="left")
    return dcc.send_data_frame(out.to_csv, "agridash_togo_data.csv", index=False)

@callback(Output("download-dataframe-xlsx", "data"),
          Input("btn-excel", "n_clicks"), prevent_initial_call=True)
def dl_xlsx(_):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        agri_data.to_excel(w, sheet_name="Crops", index=False)
        merged.to_excel(w, sheet_name="Macro", index=False)
    buf.seek(0)
    return dcc.send_bytes(buf.read(), "agridash_togo_data.xlsx")


# ============================================================
# GRAPH LAYOUT HELPER
# ============================================================
def _template(t):
    """Plotly report theme: Segoe UI, muted axis ink, thin gridlines, dark
    hover card. Inherited by every chart so the report reads as one system."""
    dark = t is THEMES["dark"]
    grid = t.get("grid", "#EAEAEA")
    muted = t.get("muted", "#605E5C")
    ink = t["text"]
    axis_line = muted
    axis_kw = dict(gridcolor=grid, zerolinecolor=grid, ticks="outside",
                   tickcolor=axis_line, ticklen=3, tickwidth=1,
                   tickfont=dict(color=muted, size=10, family=FONT_FAMILY),
                   title_font=dict(size=11, color=muted, family=FONT_FAMILY),
                   automargin=True, showgrid=True)
    return go.layout.Template(layout=go.Layout(
        font=dict(family=FONT_FAMILY, size=12, color=ink),
        colorway=COLORWAY,
        hoverlabel=dict(bgcolor="#252423", bordercolor="#3D3D3D",
                        font=dict(color="#FFFFFF", family=FONT_FAMILY, size=12)),
        xaxis=dict(showline=True, linecolor=axis_line, linewidth=1, **axis_kw),
        yaxis=dict(showline=False, linecolor=grid, linewidth=0, **axis_kw),
        legend=dict(font=dict(family=FONT_FAMILY, size=11, color=muted),
                   bgcolor="rgba(0,0,0,0)", borderwidth=0,
                   orientation="h", yanchor="bottom", y=1.02,
                   xanchor="left", x=0),
        margin=dict(l=44, r=16, t=16, b=34),
    ))


def base_layout(t=None):
    t = t or THEMES["light"]
    return dict(
        template=_template(t),
        paper_bgcolor=t["card_bg"],
        plot_bgcolor=t["card_bg"],
        font=dict(family=FONT_FAMILY, size=12, color=t["text"]),
        margin=dict(l=44, r=16, t=16, b=34),
        hovermode="x unified",
    )


# ============================================================
# GRAPH CALLBACKS - VUE D'ENSEMBLE
# ============================================================
@callback(Output("dash-yield", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _yield(years, crops, theme):
    t = THEMES[theme]
    df = agri_data[(agri_data["Year"] >= years[0]) & (agri_data["Year"] <= years[1])]
    if crops:
        df = df[df["crop"].isin(crops)]
    fig = go.Figure(layout=base_layout(t))
    for crop in sorted(df["crop"].unique()):
        sub = df[df["crop"] == crop]
        fig.add_trace(go.Scatter(x=sub["Year"], y=sub["yield_t_ha"], mode="lines+markers",
            name=crop, line=dict(width=2)))
    fig.update_yaxes(title="t/ha"); fig.update_layout(showlegend=True)
    return fig

@callback(Output("dash-prod", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _prod(years, crops, theme):
    t = THEMES[theme]
    df = agri_data[(agri_data["Year"] >= years[0]) & (agri_data["Year"] <= years[1])]
    if crops:
        df = df[df["crop"].isin(crops)]
    fig = go.Figure(layout=base_layout(t))
    for crop in sorted(df["crop"].unique()):
        sub = df[df["crop"] == crop]
        fig.add_trace(go.Scatter(x=sub["Year"], y=sub["production_t"]/1000, mode="lines+markers",
            name=crop, line=dict(width=2)))
    fig.update_yaxes(title="milliers tonnes"); fig.update_layout(showlegend=True)
    return fig

@callback(Output("dash-cat-pie", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _cat_pie(years, theme):
    t = THEMES[theme]
    df = agri_data[(agri_data["Year"] == years[1])]
    cat_totals = df.groupby("category")["production_t"].sum().reset_index()
    fig = go.Figure(data=[go.Pie(labels=cat_totals["category"], values=cat_totals["production_t"],
        hole=0.4, marker=dict(colors=[COLORS.get(c, "#999") for c in cat_totals["category"]]),
        textinfo="label+percent", textposition="outside")])
    fig.update_layout(**base_layout(t), height=280, showlegend=False,
        title={"text": f"Répartition {years[1]}", "font": {"size": 12}})
    return fig

@callback(Output("dash-prod-bar", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _prod_bar(years, theme):
    t = THEMES[theme]
    y_max = years[1]
    adf = agri_data[agri_data["Year"] == min(y_max, int(agri_data["Year"].max()))]
    if adf.empty:
        adf = agri_data[agri_data["Year"] == int(agri_data["Year"].max())]
    df = adf.groupby("crop")["production_t"].sum().reset_index().sort_values("production_t")
    fig = go.Figure(data=[go.Bar(x=df["production_t"]/1000, y=df["crop"],
        orientation="h", marker_color=COLORS["secondary"],
        text=df["production_t"].apply(lambda x: f"{x/1000:.0f}k"))])
    fig.update_layout(**base_layout(t), height=350, showlegend=False,
        xaxis_title="milliers tonnes")
    return fig

@callback(Output("dash-gauge", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _gauge(years, theme):
    t = THEMES[theme]
    rdf = risk_df[(risk_df["Year"] >= years[0]) & (risk_df["Year"] <= years[1])]
    last = rdf.iloc[-1] if len(rdf) else None
    val = last["risk_score"]*100 if last is not None else 0
    lvl = last["risk_level"] if last is not None else "N/A"
    fig = go.Figure(go.Indicator(mode="gauge+number", value=val,
        number={"suffix": "%"}, gauge={"axis":{"range":[0,100]},
        "bar":{"color":COLORS["primary"]},
        "steps":[{"range":[0,25],"color":"rgba(46,159,99,0.15)"},
                 {"range":[25,50],"color":"rgba(242,169,55,0.15)"},
                 {"range":[50,75],"color":"rgba(230,108,55,0.15)"},
                 {"range":[75,100],"color":"rgba(211,52,56,0.15)"}],
        "threshold":{"line":{"color":COLORS["danger"],"width":4},"thickness":0.75,"value":75}},
        title={"text": f"Risque: {lvl}"}))
    fig.update_layout(**base_layout(t), height=200)
    return fig

@callback(Output("dash-indicator", "figure"), Input("year-slider", "value"),
          Input("indicator-dropdown", "value"), Input("theme-store", "data"))
def _indicator(years, ind, theme):
    t = THEMES[theme]
    df = merged[(merged["Year"] >= years[0]) & (merged["Year"] <= years[1])]
    labels = {"inflation": "Inflation (%)", "gdp": "PIB ($)",
              "precip_mm": "Précipitations (mm)", "temp_c": "Température (°C)"}
    if ind in labels:
        y = df[ind] if ind != "gdp" else df["gdp"] / 1e9
        label = labels[ind]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Year"], y=y, mode="lines+markers",
            line=dict(width=3, color=COLORS["primary"]),
            fill="tozeroy", fillcolor="rgba(17,141,255,0.12)"))
        fig.update_layout(**base_layout(t), showlegend=False)
        fig.update_yaxes(title=label); return fig
    return go.Figure()


# ============================================================
# GRAPH CALLBACKS - CULTURES
# ============================================================
def _filter_agri(years, crops):
    df = agri_data[(agri_data["Year"] >= years[0]) & (agri_data["Year"] <= years[1])]
    if crops:
        df = df[df["crop"].isin(crops)]
    return df

@callback(Output("crops-yield", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _crops_yield(years, crops, theme):
    t = THEMES[theme]; df = _filter_agri(years, crops)
    fig = go.Figure(layout=base_layout(t))
    for crop in sorted(df["crop"].unique()):
        sub = df[df["crop"] == crop]
        fig.add_trace(go.Scatter(x=sub["Year"], y=sub["yield_t_ha"], mode="lines+markers",
            name=crop, line=dict(width=3)))
    fig.update_yaxes(title="t/ha"); fig.update_layout(showlegend=True)
    return fig

@callback(Output("crops-prod", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _crops_prod(years, crops, theme):
    t = THEMES[theme]; df = _filter_agri(years, crops)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for crop in sorted(df["crop"].unique()):
        sub = df[df["crop"] == crop]
        fig.add_trace(go.Bar(x=sub["Year"], y=sub["production_t"]/1000, name=crop,
            opacity=0.7), secondary_y=False)
    fig.update_layout(**base_layout(t), barmode="group", legend=dict(orientation="h", y=1.02))
    fig.update_yaxes(title="milliers tonnes", secondary_y=False)
    return fig

@callback(Output("crops-area", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _crops_area(years, crops, theme):
    t = THEMES[theme]; df = _filter_agri(years, crops)
    fig = go.Figure(layout=base_layout(t))
    for crop in sorted(df["crop"].unique()):
        sub = df[df["crop"] == crop]
        fig.add_trace(go.Scatter(x=sub["Year"], y=sub["area_ha"]/1000, mode="lines+markers",
            name=crop, fill="tozeroy", line=dict(width=2)))
    fig.update_yaxes(title="milliers ha"); fig.update_layout(showlegend=True)
    return fig

@callback(Output("crops-price", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _crops_price(years, crops, theme):
    t = THEMES[theme]; df = _filter_agri(years, crops)
    fig = go.Figure(layout=base_layout(t))
    for crop in sorted(df["crop"].unique()):
        sub = df[df["crop"] == crop]
        fig.add_trace(go.Scatter(x=sub["Year"], y=sub["price_usd_t"], mode="lines+markers",
            name=crop, line=dict(width=2, dash="dot")))
    fig.update_yaxes(title="$/t"); fig.update_layout(showlegend=True)
    return fig


# ============================================================
# GRAPH CALLBACKS - MACRO
# ============================================================
@callback(Output("macro-dual", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _macro_dual(years, theme):
    t = THEMES[theme]
    df = merged[(merged["Year"] >= years[0]) & (merged["Year"] <= years[1])]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=df["Year"], y=df["inflation"], mode="lines+markers",
        name="Inflation (%)", line=dict(width=3, color=COLORS["danger"])), secondary_y=False)
    fig.add_trace(go.Scatter(x=df["Year"], y=df["gdp"]/1e9, mode="lines+markers",
        name="PIB (milliards $)", line=dict(width=3, color=COLORS["primary"])), secondary_y=True)
    fig.update_layout(**base_layout(t), legend=dict(orientation="h", y=1.02))
    fig.update_yaxes(title="Inflation (%)", color=COLORS["danger"], secondary_y=False)
    fig.update_yaxes(title="PIB (milliards $)", color=COLORS["primary"], secondary_y=True)
    return fig

@callback(Output("macro-wa", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _macro_wa(years, theme):
    t = THEMES[theme]
    wa = wa_inflation[(wa_inflation["Year"] >= years[0]) & (wa_inflation["Year"] <= years[1])]
    top = wa[wa["Country Name"].isin(["Togo","Côte d'Ivoire","Ghana","Nigéria","Bénin","Sénégal"])]
    fig = px.line(top, x="Year", y="Value", color="Country Name", markers=True)
    fig.update_layout(**base_layout(t), legend=dict(orientation="h", y=1.02, font=dict(size=9)))
    fig.update_yaxes(title="Inflation (%)"); return fig

@callback(Output("macro-dist", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _macro_dist(years, theme):
    t = THEMES[theme]
    df = merged[(merged["Year"] >= years[0]) & (merged["Year"] <= years[1])]
    fig = make_subplots(rows=1, cols=2, subplot_titles=["Distribution Inflation", "Distribution PIB"])
    fig.add_trace(go.Histogram(x=df["inflation"], nbinsx=15, marker_color=COLORS["danger"],
        opacity=0.7, name="Inflation"), row=1, col=1)
    fig.add_trace(go.Histogram(x=df["gdp"]/1e9, nbinsx=15, marker_color=COLORS["primary"],
        opacity=0.7, name="PIB"), row=1, col=2)
    fig.update_layout(**base_layout(t), showlegend=False); return fig

@callback(Output("macro-stats", "children"), Input("year-slider", "value"), Input("theme-store", "data"))
def _macro_stats(years, theme):
    df = merged[(merged["Year"] >= years[0]) & (merged["Year"] <= years[1])]
    tc = THEMES[theme]["text"]
    return [dbc.Row([dbc.Col(l, width=7, style={"color": tc}),
                     dbc.Col(v, width=5, className="fw-bold", style={"color": tc})],
                    className="border-bottom py-1")
            for l, v in [
        ("Moyenne Inflation", f"{df['inflation'].mean():.2f}%"),
        ("Max Inflation", f"{df['inflation'].max():.2f}%"),
        ("Min Inflation", f"{df['inflation'].min():.2f}%"),
        ("PIB Moyen", f"{df['gdp'].mean()/1e9:.2f} Mrd $"),
        ("Croissance PIB Moy.", f"{df['gdp'].pct_change().mean()*100:.2f}%"),
        ("Volatilité Inflation", f"{df['inflation'].std():.2f}"),
    ]]

@callback(Output("macro-agri-table", "data"), Output("macro-agri-table", "columns"),
          Input("year-slider", "value"), Input("theme-store", "data"))
def _macro_agri_table(years, theme):
    ymin, ymax = years
    wb = agri_wb[(agri_wb["Year"] >= ymin) & (agri_wb["Year"] <= ymax)]
    latest = wb.groupby("indicator").last().reset_index()
    label_map = {"crop_production_index": "Indice Prod. Agricole",
                 "cereal_yield_kg_ha": "Rend. Céréales (kg/ha)",
                 "agri_value_added_pct": "Valeur Ajoutée Agricole (% PIB)",
                 "agri_land_pct": "Terres Agricoles (% total)"}
    rows = [{"Indicateur": label_map.get(r["indicator"], r["indicator"]),
             "Valeur": round(r["value"], 2), "Année": int(r["Year"])}
            for _, r in latest.iterrows()]
    return rows, [{"name": c, "id": c} for c in ["Indicateur", "Valeur", "Année"]]


# ============================================================
# GRAPH CALLBACKS - MAP
# ============================================================
@callback(Output("map-chart", "figure"),
          Input("year-slider", "value"), Input("theme-store", "data"),
          Input("crop-dropdown", "value"), Input("selected-region", "data"))
def _map(years, theme, crops, selected_region):
    t = THEMES.get(theme, THEMES["light"])
    rdf = togo_map.get_region_production_data(agri_data, years[1])
    geojson = TOGO_GEOJSON

    region_lookup = {raw: name for raw, name in REGION_NAME_MAP.items()}
    rdf["geojson_key"] = rdf["region"].map(
        lambda r: next((k for k, v in region_lookup.items() if v == r), r)
    )

    def region_color(value):
        if value >= 30: return MAP_RAMP[4]
        if value >= 22: return MAP_RAMP[3]
        if value >= 15: return MAP_RAMP[2]
        if value >= 10: return MAP_RAMP[1]
        return MAP_RAMP[0]

    fig = go.Figure()

    # Draw the Togo GeoJSON polygons directly, without any basemap.
    for i, row in rdf.iterrows():
        is_selected = selected_region and row["region"] == selected_region
        line_color = COLORS["primary"] if is_selected else "#ffffff"
        line_width = 4 if is_selected else 1.8

        feat = [f for f in geojson["features"] if f["properties"]["shapeName"] == row["geojson_key"]]
        if not feat:
            continue
        geometry = feat[0]["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]

        for poly in polygons:
            exterior = poly[0]
            xs = [p[0] for p in exterior]
            ys = [p[1] for p in exterior]
            fig.add_trace(go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                fill="toself",
                fillcolor=region_color(row["production_pct"]),
                line=dict(color=line_color, width=line_width),
                customdata=[row["region"]] * len(xs),
                hovertemplate=f"<b>{row['region']}</b><br>Production: {int(row['production_t']):,} t<br>Part: {row['production_pct']:.1f}%<extra></extra>",
                name=row["region"],
                showlegend=False,
            ))

    # ---- Region labels ----
    centroids = togo_map.REGION_CENTROIDS
    label_df = rdf.copy()
    label_df["lat"] = label_df["region"].map(lambda r: centroids.get(r, {}).get("lat", 8.5))
    label_df["lon"] = label_df["region"].map(lambda r: centroids.get(r, {}).get("lon", 1.0))
    label_df["label"] = label_df.apply(
        lambda r: f"<b>{r['region']}</b><br>{r['production_t']/1e6:.2f}M t<br>{r['production_pct']:.1f}%", axis=1
    )

    label_color = "white" if t.get("card_bg", "#ffffff") != "#ffffff" else "#132238"
    hover_bg = "rgba(0,0,0,0.85)" if label_color == "white" else "rgba(255,255,255,0.95)"

    fig.add_trace(go.Scatter(
        x=label_df["lon"],
        y=label_df["lat"],
        mode="text",
        text=label_df["region"],
        textfont=dict(size=13, color=label_color, family="Arial Black"),
        hoverinfo="text",
        hovertext=label_df["label"],
        customdata=label_df["region"],
        hoverlabel=dict(
            bgcolor=hover_bg,
            font=dict(size=13, color=label_color),
            bordercolor="white",
        ),
        showlegend=False,
    ))

    fig.update_layout(
        height=650,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor=t["card_bg"],
        plot_bgcolor=t["card_bg"],
        clickmode="event+select",
        xaxis=dict(
            visible=False,
            range=[-0.35, 1.95],
            scaleanchor="y",
            scaleratio=1,
            constrain="domain",
        ),
        yaxis=dict(
            visible=False,
            range=[5.95, 11.25],
            constrain="domain",
        ),
    )
    return fig


# ============================================================
# GRAPH CALLBACKS - RISKS
# ============================================================
@callback(Output("risk-ts", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _risk_ts(years, theme):
    t = THEMES[theme]
    rdf = risk_df[(risk_df["Year"] >= years[0]) & (risk_df["Year"] <= years[1])]
    fig = go.Figure()
    for lvl in ["Faible","Modéré","Élevé","Critique"]:
        sub = rdf[rdf["risk_level"]==lvl]
        if len(sub):
            fig.add_trace(go.Scatter(x=sub["Year"], y=sub["risk_score"],
                mode="markers+lines", name=lvl, marker=dict(size=10, color=RISK_COLORS[lvl]),
                line=dict(color=RISK_COLORS[lvl], width=1, dash="dot")))
    fig.add_hrect(y0=0.75,y1=1,fillcolor="rgba(211,52,56,0.06)",line_width=0)
    fig.add_hrect(y0=0.5,y1=0.75,fillcolor="rgba(230,108,55,0.06)",line_width=0)
    fig.update_layout(**base_layout(t), legend=dict(orientation="h", y=1.02))
    fig.update_yaxes(title="Score de Risque", range=[0,1]); return fig

@callback(Output("risk-pie", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _risk_pie(years, theme):
    t = THEMES[theme]
    rdf = risk_df[(risk_df["Year"] >= years[0]) & (risk_df["Year"] <= years[1])]
    counts = rdf["risk_level"].value_counts()
    cmap = RISK_COLORS
    fig = go.Figure(data=[go.Pie(labels=counts.index, values=counts.values, hole=0.4,
        marker=dict(colors=[cmap.get(l,"#999") for l in counts.index]),
        textinfo="label+percent")])
    fig.update_layout(**base_layout(t), height=280); return fig


# ============================================================
# GRAPH CALLBACKS - CLIMATE
# ============================================================
@callback(Output("climate-precip", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _climate_precip(years, theme):
    t = THEMES[theme]
    df = climate_natl[(climate_natl["Year"] >= years[0]) & (climate_natl["Year"] <= years[1])]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Year"], y=df["precip_mm"], name="Précipitations",
        marker_color=COLORS["secondary"], opacity=0.7))
    fig.add_trace(go.Scatter(x=df["Year"], y=df["precip_mm"].rolling(3, min_periods=1).mean(),
        mode="lines", name="Moy. mobile 3 ans", line=dict(width=3, color=COLORS["danger"])))
    fig.update_layout(**base_layout(t), showlegend=True)
    fig.update_yaxes(title="mm/an"); return fig

@callback(Output("climate-temp", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _climate_temp(years, theme):
    t = THEMES[theme]
    df = climate_natl[(climate_natl["Year"] >= years[0]) & (climate_natl["Year"] <= years[1])]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Year"], y=df["temp_c"], mode="lines+markers",
        name="Température", line=dict(width=3, color=COLORS["danger"]),
        fill="tozeroy", fillcolor="rgba(211,52,56,0.12)"))
    fig.add_hline(y=df["temp_c"].mean(), line_dash="dash", line_color="#666",
        annotation_text=f"Moy. {df['temp_c'].mean():.1f}°C")
    fig.update_layout(**base_layout(t), showlegend=True)
    fig.update_yaxes(title="°C"); return fig

@callback(Output("climate-region-precip", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _climate_region_precip(years, theme):
    t = THEMES[theme]
    df = climate_data[(climate_data["Region"] != "National") &
                      (climate_data["Year"] >= years[0]) & (climate_data["Year"] <= years[1])]
    fig = px.line(df, x="Year", y="precip_mm", color="Region", markers=True)
    fig.update_layout(**base_layout(t), legend=dict(orientation="h", y=1.02, font=dict(size=9)))
    fig.update_yaxes(title="mm/an"); return fig

@callback(Output("climate-region-temp", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _climate_region_temp(years, theme):
    t = THEMES[theme]
    df = climate_data[(climate_data["Region"] != "National") &
                      (climate_data["Year"] >= years[0]) & (climate_data["Year"] <= years[1])]
    fig = px.line(df, x="Year", y="temp_c", color="Region", markers=True)
    fig.update_layout(**base_layout(t), legend=dict(orientation="h", y=1.02, font=dict(size=9)))
    fig.update_yaxes(title="°C"); return fig

@callback(Output("climate-summary", "children"), Input("year-slider", "value"), Input("theme-store", "data"))
def _climate_summary(years, theme):
    df = climate_natl[(climate_natl["Year"] >= years[0]) & (climate_natl["Year"] <= years[1])]
    tc = THEMES[theme]["text"]
    rows = [
        ("Précip. Moy.", f"{df['precip_mm'].mean():.0f} mm/an"),
        ("Précip. Min", f"{df['precip_mm'].min():.0f} mm/an"),
        ("Précip. Max", f"{df['precip_mm'].max():.0f} mm/an"),
        ("Temp. Moy.", f"{df['temp_c'].mean():.1f} °C"),
        ("Temp. Min", f"{df['temp_c'].min():.1f} °C"),
        ("Temp. Max", f"{df['temp_c'].max():.1f} °C"),
    ]
    return [dbc.Row([dbc.Col(l, width=7, style={"color": tc}),
                     dbc.Col(v, width=5, className="fw-bold", style={"color": tc})],
                    className="border-bottom py-1") for l, v in rows]

@callback(Output("climate-corr", "figure"), Input("year-slider", "value"), Input("theme-store", "data"))
def _climate_corr(years, theme):
    t = THEMES[theme]
    adf = agri_data[(agri_data["Year"] >= years[0]) & (agri_data["Year"] <= years[1])]
    cdf = climate_natl[(climate_natl["Year"] >= years[0]) & (climate_natl["Year"] <= years[1])]
    m = adf.merge(cdf, on="Year")
    fig = go.Figure(data=go.Heatmap(
        z=m[["precip_mm","temp_c","yield_t_ha"]].corr().values,
        x=["precip_mm","temp_c","yield_t_ha"],
        y=["precip_mm","temp_c","yield_t_ha"],
        colorscale="RdBu_r", zmid=0,
        text=np.round(m[["precip_mm","temp_c","yield_t_ha"]].corr().values, 2),
        texttemplate="%{text}"))
    fig.update_layout(**base_layout(t), height=280)
    return fig


# ============================================================
# GRAPH CALLBACKS - MARKETS
# ============================================================
@callback(Output("mkts-heatmap", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _mkts_heatmap(years, crops, theme):
    t = THEMES[theme]
    yr = min(years[1], int(market_df["Year"].max()))
    df = market_df[(market_df["Year"] == yr)]
    if crops:
        df = df[df["crop"].isin(crops)]
    if df.empty:
        return go.Figure(layout=base_layout(t))
    pivot = df.pivot_table(index="region", columns="crop", values="price_fcfa_kg", aggfunc="first")
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=pivot.columns, y=pivot.index,
        colorscale="YlOrRd", text=np.round(pivot.values, 0),
        texttemplate="%{text}", textfont={"size": 10},
        hovertemplate="Région: %{y}<br>Culture: %{x}<br>Prix: %{text} FCFA/kg<extra></extra>",
    ))
    fig.update_layout(**base_layout(t), height=450,
                      xaxis_title="Culture", yaxis_title="Région")
    return fig


@callback(Output("mkts-ts", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _mkts_ts(years, crops, theme):
    t = THEMES[theme]
    df = market_df[(market_df["Year"] >= max(years[0], 2015)) & (market_df["Year"] <= years[1])]
    if crops:
        df = df[df["crop"].isin(crops)]
    if df.empty:
        return go.Figure(layout=base_layout(t))
    avg = df.groupby(["Year", "region"])["price_fcfa_kg"].mean().reset_index()
    fig = go.Figure(layout=base_layout(t))
    for region in MARKET_REGIONS:
        sub = avg[avg["region"] == region]
        if len(sub):
            fig.add_trace(go.Scatter(x=sub["Year"], y=sub["price_fcfa_kg"],
                mode="lines+markers", name=region, line=dict(width=2)))
    fig.update_yaxes(title="FCFA/kg (moy. cultures sélectionnées)")
    fig.update_layout(showlegend=True)
    return fig


@callback(Output("mkts-bar", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _mkts_bar(years, crops, theme):
    t = THEMES[theme]
    df = market_df[(market_df["Year"] == years[1])]
    if crops:
        df = df[df["crop"].isin(crops)]
    if df.empty:
        return go.Figure(layout=base_layout(t))
    spread = df.groupby("region")["price_fcfa_kg"].mean().reset_index()
    spread = spread.sort_values("price_fcfa_kg")
    national_avg = spread["price_fcfa_kg"].mean()
    spread["diff_pct"] = ((spread["price_fcfa_kg"] - national_avg) / national_avg * 100).round(1)
    colors = [COLORS["danger"] if v > 0 else COLORS["success"] for v in spread["diff_pct"]]
    fig = go.Figure(data=[go.Bar(
        x=spread["diff_pct"], y=spread["region"], orientation="h",
        marker_color=colors,
        text=spread["diff_pct"].apply(lambda x: f"{x:+.1f}%"),
        textposition="outside",
    )])
    fig.add_vline(x=0, line_width=1, line_color="#666")
    fig.update_layout(**base_layout(t), height=300, showlegend=False,
                      xaxis_title="Écart à la moyenne nationale (%)")
    return fig


@callback(Output("mkts-summary", "children"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _mkts_summary(years, crops, theme):
    tc = THEMES[theme]["text"]
    df = market_df[(market_df["Year"] == years[1])]
    if crops:
        df = df[df["crop"].isin(crops)]
    if df.empty:
        return html.P("Aucune donnée")
    avg = df["price_fcfa_kg"].mean()
    mini = df["price_fcfa_kg"].min()
    maxi = df["price_fcfa_kg"].max()
    cheap_region = df.loc[df["price_fcfa_kg"].idxmin(), "region"]
    expensive_region = df.loc[df["price_fcfa_kg"].idxmax(), "region"]
    rows = [
        ("Prix Moyen", f"{avg:.0f} FCFA/kg"),
        ("Prix Min", f"{mini:.0f} FCFA/kg ({cheap_region})"),
        ("Prix Max", f"{maxi:.0f} FCFA/kg ({expensive_region})"),
        ("Régions", f"{df['region'].nunique()}"),
        ("Cultures", f"{df['crop'].nunique()}"),
    ]
    return [dbc.Row([dbc.Col(l, width=7, style={"color": tc}),
                     dbc.Col(v, width=5, className="fw-bold", style={"color": tc})],
                    className="border-bottom py-1") for l, v in rows]


@callback(Output("mkts-arbitrage", "children"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _mkts_arbitrage(years, crops, theme):
    tc = THEMES[theme]["text"]
    df = market_df[(market_df["Year"] == years[1])]
    if crops:
        df = df[df["crop"].isin(crops)]
    if df.empty:
        return html.P("Aucune donnée", className="small text-muted")
    opps = mp.get_arbitrage_opportunities(df, years[1])
    if opps.empty:
        return html.P("Aucune opportunité d'arbitrage significative (>20%)", className="small text-muted")
    return html.Div([
        html.P(f"{len(opps)} opportunité(s) d'arbitrage détectée(s)", className="small fw-bold mb-2"),
        *[html.Div([
            html.Strong(r["crop"], style={"color": tc}),
            html.Div([
                html.Span(f"Acheter: {r['buy_region']} à {r['buy_price']} FCFA/kg", className="text-success d-block small"),
                html.Span(f"Vendre: {r['sell_region']} à {r['sell_price']} FCFA/kg", className="text-danger d-block small"),
                html.Span(f"Spread: {r['spread_pct']}%", className="fw-bold d-block small"),
            ], className="ms-2 mb-2"),
        ], className="border-bottom pb-1 mb-1") for _, r in opps.iterrows()],
    ])


@callback(Output("dl-mkts-csv", "data"), Input("btn-mkts-csv", "n_clicks"),
          prevent_initial_call=True)
def _dl_mkts_csv(_):
    return dcc.send_data_frame(market_df.to_csv, "togo_market_prices.csv", index=False)


# ============================================================
# GRAPH CALLBACKS - FORECAST
# ============================================================
def _forecast_filter(forecasts_df, scenario, crops):
    f = forecasts_df[forecasts_df["scenario"] == (scenario or "modéré")].copy()
    if crops:
        f = f[f["crop"].isin(crops)]
    return f


@callback(Output("forecast-yield", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("scenario-select", "value"),
          Input("theme-store", "data"))
def _forecast_yield(years, crops, scenario, theme):
    t = THEMES[theme]
    fcst = _forecast_filter(forecasts, scenario, crops)
    if fcst.empty:
        return go.Figure(layout=base_layout(t)).update_layout(title="Aucune donnée")

    hist_start = max(years[0], 2000)
    hist = agri_data[(agri_data["Year"] >= hist_start) & (agri_data["Year"] <= 2024)]
    if crops:
        hist = hist[hist["crop"].isin(crops)]

    fig = go.Figure(layout=base_layout(t))
    cat_colors = {c: COLORS[ALL_CROPS[c]["category"]] if ALL_CROPS[c]["category"] in COLORS else "#999" for c in fcst["crop"].unique()}
    for crop in sorted(fcst["crop"].unique()):
        color = cat_colors.get(crop, "#999")
        h = hist[hist["crop"] == crop]
        f = fcst[fcst["crop"] == crop]
        if len(h):
            fig.add_trace(go.Scatter(x=h["Year"], y=h["yield_t_ha"], mode="lines",
                name=crop, line=dict(width=1.5, color=color), legendgroup=crop))
        if len(f):
            fig.add_trace(go.Scatter(x=f["Year"], y=f["yield_upper"], mode="lines",
                line=dict(width=0), showlegend=False, legendgroup=crop))
            fig.add_trace(go.Scatter(x=f["Year"], y=f["yield_lower"], mode="lines",
                fill="tonexty", fillcolor=f"rgba(128,128,128,0.12)",
                line=dict(width=0), showlegend=False, legendgroup=crop))
            fig.add_trace(go.Scatter(x=f["Year"], y=f["yield_t_ha"], mode="markers+lines",
                name=f"{crop} (prév.)", line=dict(width=2, dash="dot", color=color),
                marker=dict(symbol="diamond-open", size=10, color=color, line=dict(width=2)),
                legendgroup=crop))
    fig.add_vline(x=2024.5, line_dash="dash", line_color="#666", line_width=1,
                  annotation_text="Prévisions ▶", annotation_position="top right")
    fig.update_yaxes(title="t/ha")
    fig.update_layout(showlegend=True)
    return fig


@callback(Output("forecast-prod", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("scenario-select", "value"),
          Input("theme-store", "data"))
def _forecast_prod(years, crops, scenario, theme):
    t = THEMES[theme]
    fcst = _forecast_filter(forecasts, scenario, crops)
    if fcst.empty:
        return go.Figure(layout=base_layout(t))

    hist_start = max(years[0], 2015)
    hist = agri_data[(agri_data["Year"] >= hist_start) & (agri_data["Year"] <= 2024)]
    if crops:
        hist = hist[hist["crop"].isin(crops)]

    cat_colors = {c: COLORS[ALL_CROPS[c]["category"]] if ALL_CROPS[c]["category"] in COLORS else "#999" for c in fcst["crop"].unique()}
    fig = go.Figure(layout=base_layout(t))
    for crop in sorted(fcst["crop"].unique()):
        color = cat_colors.get(crop, "#999")
        h = hist[hist["crop"] == crop]
        f = fcst[fcst["crop"] == crop]
        if len(h):
            fig.add_trace(go.Bar(x=h["Year"], y=h["production_t"]/1000,
                name=crop, marker_color=color, opacity=0.3, legendgroup=crop))
        if len(f):
            fig.add_trace(go.Scatter(x=f["Year"], y=f["production_t"]/1000,
                mode="lines+markers", name=f"{crop} (prév.)",
                line=dict(width=3, color=color),
                marker=dict(symbol="diamond", size=12, color=color),
                legendgroup=crop))
    fig.add_vline(x=2024.5, line_dash="dash", line_color="#666", line_width=1)
    fig.update_yaxes(title="milliers tonnes")
    fig.update_layout(showlegend=True)
    return fig


@callback(Output("forecast-scenario", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("theme-store", "data"))
def _forecast_scenario(years, crops, theme):
    t = THEMES[theme]
    fcst = forecasts.copy()
    if crops:
        fcst = fcst[fcst["crop"].isin(crops)]
    if fcst.empty:
        return go.Figure(layout=base_layout(t))

    pivot = fcst.groupby(["Year", "scenario"])["production_t"].sum().reset_index()
    fig = go.Figure(layout=base_layout(t))
    colors = {"modéré": COLORS["primary"], "optimiste": COLORS["success"], "pessimiste": COLORS["danger"]}
    labels = {"modéré": "Modéré (tendance)", "optimiste": "Optimiste (+12%)", "pessimiste": "Pessimiste (-15%)"}
    for scenario in ["modéré", "optimiste", "pessimiste"]:
        sdf = pivot[pivot["scenario"] == scenario]
        if len(sdf):
            fig.add_trace(go.Scatter(x=sdf["Year"], y=sdf["production_t"]/1e6,
                mode="lines+markers", name=labels[scenario],
                line=dict(width=3, color=colors[scenario]),
                marker=dict(symbol="circle", size=14, color=colors[scenario])))
    fig.update_yaxes(title="millions de tonnes", gridcolor="rgba(128,128,128,0.15)")
    fig.update_layout(showlegend=True)
    return fig


@callback(Output("forecast-table", "data"), Output("forecast-table", "columns"),
          Input("year-slider", "value"), Input("crop-dropdown", "value"),
          Input("theme-store", "data"))
def _forecast_table(years, crops, theme):
    fs = forecast_summary.copy()
    if crops:
        fs = fs[fs["crop"].isin(crops)]
    if fs.empty:
        return [], []
    fs = fs.copy()
    fs["yield_change_pct"] = fs["yield_change_pct"].round(1).apply(lambda x: f"{x:+.1f}%")
    fs["prod_change_pct"] = fs["prod_change_pct"].round(1).apply(lambda x: f"{x:+.1f}%")
    fs["yield_2025"] = fs["yield_2025"].round(2)
    fs["yield_2030"] = fs["yield_2030"].round(2)
    fs["prod_2025"] = fs["prod_2025"].round(0).astype(int)
    fs["prod_2030"] = fs["prod_2030"].round(0).astype(int)
    cols = [
        {"name": "Culture", "id": "crop"},
        {"name": "Catégorie", "id": "category"},
        {"name": "Rendement 2025 (t/ha)", "id": "yield_2025"},
        {"name": "Rendement 2030 (t/ha)", "id": "yield_2030"},
        {"name": "Var. Rend.", "id": "yield_change_pct"},
        {"name": "Production 2025 (t)", "id": "prod_2025"},
        {"name": "Production 2030 (t)", "id": "prod_2030"},
        {"name": "Var. Prod.", "id": "prod_change_pct"},
    ]
    data = [{k: v for k, v in r.items()} for r in fs.to_dict("records")]
    return data, cols


@callback(Output("forecast-risk-gauge", "figure"), Input("year-slider", "value"),
          Input("crop-dropdown", "value"), Input("scenario-select", "value"),
          Input("theme-store", "data"))
def _forecast_risk_gauge(years, crops, scenario, theme):
    t = THEMES[theme]
    fcst = _forecast_filter(forecasts, scenario, crops)
    if fcst.empty:
        return go.Figure(layout=base_layout(t))

    prod_2025 = fcst[fcst["Year"] == 2025]["production_t"].sum()
    prod_2030 = fcst[fcst["Year"] == 2030]["production_t"].sum()
    growth = (prod_2030 / max(prod_2025, 1) - 1) * 100
    risk_score = max(0, min(1, (1 - growth / 30) / 2 + 0.3))

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=risk_score * 100,
        number={"suffix": "%", "font": {"color": COLORS["danger"] if risk_score > 0.6 else COLORS["warning"] if risk_score > 0.3 else COLORS["success"], "size": 28}},
        delta={"reference": 50, "valueformat": ".0f", "increasing": {"color": COLORS["danger"]}},
        title={"text": f"Scénario: {scenario or 'modéré'}", "font": {"size": 12}},
        gauge={
            "axis": {"range": [0, 100], "visible": False},
            "bar": {"color": COLORS["danger"] if risk_score > 0.6 else COLORS["warning"] if risk_score > 0.3 else COLORS["success"], "thickness": 0.15},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 30], "color": "rgba(46,159,99,0.15)"},
                {"range": [30, 60], "color": "rgba(242,169,55,0.15)"},
                {"range": [60, 100], "color": "rgba(211,52,56,0.15)"},
            ],
            "threshold": {
                "line": {"color": COLORS["danger"], "width": 3},
                "thickness": 0.6,
                "value": 60,
            },
        },
    ))
    layout = base_layout(t)
    layout["margin"] = dict(l=20, r=20, t=30, b=0)
    fig.update_layout(**layout, height=180)
    return fig


# ============================================================
# PDF EXPORT
# ============================================================
@callback(Output("download-pdf", "data"), Input("btn-pdf", "n_clicks"),
          prevent_initial_call=True)
def _export_pdf(_):
    from weasyprint import HTML
    fs = forecast_summary.copy()
    fs_rows = ""
    if len(fs):
        fs_rows = "<tr><th>Culture</th><th>Rdt 2025</th><th>Rdt 2030</th><th>Var.</th></tr>"
        for _, r in fs.iterrows():
            fs_rows += f"<tr><td>{r['crop']}</td><td>{r['yield_2025']:.2f}</td><td>{r['yield_2030']:.2f}</td><td>{r['yield_change_pct']:+.1f}%</td></tr>"
    last_year = int(agri_data["Year"].max())
    prod_by_crop = agri_data[agri_data["Year"]==last_year].groupby("crop")["production_t"].sum().sort_values(ascending=False)
    html_parts = ["<h1>AgriDash Togo - Rapport</h1>",
                  f"<p>Généré le {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}</p>",
                  f"<hr><h2>Production Totale ({last_year})</h2><table border='1'><tr><th>Culture</th><th>Tonnes</th></tr>"]
    for c, v in prod_by_crop.items():
        html_parts.append(f"<tr><td>{c}</td><td>{v:,.0f}</td></tr>")
    html_parts.append("</table><hr><h2>Prévisions 2025-2030</h2><table border='1'>")
    html_parts.append(fs_rows)
    html_parts.append("</table><hr><h2>Indicateurs Macro</h2>")
    last_inf = inflation[inflation["Year"]==inflation["Year"].max()]["Value"].values
    last_gdp = gdp[gdp["Year"]==gdp["Year"].max()]["Value"].values
    if len(last_inf): html_parts.append(f"<p>Inflation {int(inflation['Year'].max())}: {last_inf[0]:.1f}%</p>")
    if len(last_gdp): html_parts.append(f"<p>PIB {int(gdp['Year'].max())}: {last_gdp[0]/1e9:.1f} Mrd $</p>")
    html_parts.append("<hr><p>AgriDash Togo - Dashboard de Pilotage Agricole Prédictif</p>")
    pdf = HTML(string="<html><body>" + "".join(html_parts) + "</body></html>").write_pdf()
    return dcc.send_bytes(pdf, "agridash_togo_rapport.pdf")


# ============================================================
# WSGI + AUTH
# ============================================================
server = app.server
import os as _os
_AUTH_USER = _os.environ.get("DASH_USER", "admin")
_AUTH_PASS = _os.environ.get("DASH_PASSWORD", "togo2024")
from flask import request as _flask_request, Response as _FlaskResponse

@server.before_request
def _check_auth():
    auth = _flask_request.authorization
    if auth and auth.username == _AUTH_USER and auth.password == _AUTH_PASS:
        return
    if _flask_request.path.startswith("/_alive") or _flask_request.path == "/favicon.ico":
        return
    return _FlaskResponse("Authentication Required", 401,
                          {"WWW-Authenticate": 'Basic realm="AgriDash Togo"'})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
