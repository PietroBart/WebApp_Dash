import dash
from dash import dash_table, html, dcc, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc # per styling
import pandas as pd
import numpy as np
#from dash_extensions import Lottie
import os, re
from datetime import datetime, timezone



# Salva data ultimo aggiornamento
CSV_STD_PATH = "merged_std_STOXX_2025-08-12.csv"

def infer_last_update(path: str) -> str:
    base = os.path.basename(path)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", base)  # es. 2025-08-04
    if m:
        dt = datetime.strptime(m.group(1), "%Y-%m-%d")
        return dt.strftime("%b %d, %Y")          # -> "Aug 04, 2025"
    # fallback: mtime del file in UTC
    try:
        ts = os.path.getmtime(path)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return "Unknown"

LAST_UPDATE_STR = infer_last_update(CSV_STD_PATH)


# -----------------------------------------------------#
# --- Configurazione dell'app -------------------------#
# -----------------------------------------------------# 
app_title = "Stock Screening - STOXX Europe 600"

app_description = """
This WebApp allows to perform a quick and intuitive interactive stock screening and relative valuation for the STOXX Europe 600.

**How it works**
- For each stock a list of pre-selected fundamental multiples and technical indicators are rethrived from Reuters.
- Each metric is standardized **within the stock’s industry (GICS industry/sub-sector)** using z-scores, so values are directly comparable within the same industry.
- A **Fundamental score** is computed *within each industry* as a weighted average of three blocks that the user can adjust:
  - **F1 – Equity Multiples**
  - **F2 – Profitability & Balance Sheet**
  - **F3 – Solidity** \n
  The user can edit both the specific **metric-level coefficients** and the **block weights**.  
- A separate **Technical momentum rank** is computed from price/technical indicators that it is **not mixed** with the fundamental score.
- Results are ranked by industry; the user can download the dataframe to Excel and also plot a stock’s metrics vs its industry average.

**Metrics used**
- **Fwd_PE** – Forward price-to-earnings (next FY).
- **Fwd_PEG** – Forward P/E divided by expected growth (P/E-to-growth).
- **Fwd_PB** – Price-to-book value.
- **P_S** – Price-to-sales ratio.
- **Fwd_EPS** – Forecast earnings per share (next FY).
- **EBIT_Margin** – EBIT as a percentage of revenue.
- **EV_FCF_FY1** – Enterprise value to next-year free cash flow.
- **FCF_Conversion_FY1** – Share of operating profits turning into free cash flow (next FY).
- **DPS_FY1** – Dividend per share expected next FY.
- **ROE_FY1** – Return on equity expected next FY.
- **Capex_Revenue_FY1** – Capital expenditures as % of revenue (next FY).
- **CAGR** – Compound annual growth rate (revenues/earnings per dataset definition).
- **ND_EBITDA** – Net debt / EBITDA.
- **ND_EV_FY1** – Net debt as a share of enterprise value (next FY).
- **EV_EBITDA_FY1** – Enterprise value / EBITDA (next FY).
- **CET1_Ratio** – Common Equity Tier 1 ratio (banks’ capital strength).
- **RSI** – Relative Strength Index.
- **RSI_ORDER** – RSI rank/ordering to make cross-section comparisons robust.
- **PX_MA200** – Distance of price from the 200-day moving average.
- **MA10_MA100** – Spread/crossover between 10- and 100-day moving averages.
- **DMI** – Directional Movement Index (trend strength).

**Notes**
- Regarding the standardization by industry, “better/worse” direction is handled via the chosen coefficient signs.
- Two rankings are produced **separately**: a Fundamental rank and a Technical rank (momentum).
- Coverage: STOXX Europe 600 constituents; Data source: Reuters.
"""

instructions = """
1. **Select a sector:** Use the dropdown list to choose a sector.
2. **Adjust metric coefficients (optional):** Manually modify the weights of each metric inside **Equity**, **Profitability** and **Solidity Multiples**.
3. **Adjust group weights (optional):** Use the sliders to set the weight of each group.
4. **Run:** Click the button to compute the fundamental score and the technical ranks by industry using your selected sector and weights.
5. **Download results (optional):** Save the current rankings to Excel.
6. **Plot metrics (optional):** Pick a stock to compare its  metrics with the industry average.
    
*Notes:* Within each group, metric weights are alwasy normalized to 100%. Group weights are normalized as well.
"""

presentation = (
    "I am a Corporate Finance graduate currently working in the Front Office at Sorgenia as an Energy Trading Analyst.\n\n"
    "I developed this app using Plotly Dash, as an exercise to learn how to build interactive web applications with Python.\n\n"
    "The goal was to create a simple and intuitive tool to perform a quick basic stock screener and sector-based relative valuation.\n\n"
    "Feel free to connect with me on LinkedIn for more updates and insights."
)


# -----------------------------------------------#
# --- Metadati social media ---------------------#
# -----------------------------------------------#

metas = [
    {"name": "viewport", "content": "width=device-width, initial-scale=1"},
    {"property": "twitter:card", "content": "summary_large_image"},
    {"property": "twitter:title", "content": app_title},
    {"property": "twitter:description", "content": app_description},
    {"property": "og:title", "content": app_title},
    {"property": "og:type", "content": "website"},
    {"property": "og:description", "content": app_description}
]



#-----------------------------------------------------#
# --- Caricamento dei dati e Ranking ------------#
#-----------------------------------------------------#

df_merged_std = pd.read_csv("merged_std_STOXX_2025-08-12.csv")
df_merged_raw = pd.read_csv("merged_raw_STOXX_2025-08-12.csv")
coeff = pd.read_excel("coeff_stream_2.0.xlsx")
coeff.set_index("Sector", inplace=True)


f1_columns = df_merged_std.columns[4:9].tolist()
f2_columns = df_merged_std.columns[9:15].tolist()
f3_columns = df_merged_std.columns[15:18].tolist()
tech_columns = df_merged_std.columns[18:23].tolist()
all_cols = f1_columns + f2_columns + f3_columns + tech_columns

# assicura che le metriche siano numeriche nel raw
for c in (f1_columns + f2_columns + f3_columns + tech_columns):
    if c in df_merged_raw.columns:
        df_merged_raw[c] = pd.to_numeric(df_merged_raw[c], errors="coerce")


# Crea un dizionario di df contenente i multipli disponibili per ogni settore. 
# Aggiunge le colonne ['Sector',"Industry","Name"] ad ogni df per mantenere le informazioni.
df_dict_sector = {}
for sector in df_merged_std["Sector"].unique():
    df_sector = df_merged_std[df_merged_std["Sector"] == sector].copy()
    coeff_row = coeff.loc[sector]
    valid_cols = [col for col in all_cols if coeff_row.get(col, 0) != 0]
    id_cols = ['Sector',"Industry","Name"] 
    df_dict_sector[sector] = df_sector[id_cols + valid_cols] 


# --- Calcolo score per ogni settore ---#
ranked_dict = {}
for sector, df in df_dict_sector.items():
    coeff_row = coeff.loc[sector]
    valid_cols = [col for col in df.columns if col in coeff_row.index and coeff_row[col] != 0]
    f1_cols = [col for col in f1_columns if col in valid_cols]
    f2_cols = [col for col in f2_columns if col in valid_cols]
    f3_cols = [col for col in f3_columns if col in valid_cols]
    tech_cols = [col for col in tech_columns if col in valid_cols]

    f1_weights = np.array([coeff_row[col] for col in f1_cols])
    f2_weights = np.array([coeff_row[col] for col in f2_cols])
    f3_weights = np.array([coeff_row[col] for col in f3_cols])
    tech_weights = np.array([coeff_row[col] for col in tech_cols])
   
    if f1_weights.sum() > 0: f1_weights = f1_weights / f1_weights.sum()
    if f2_weights.sum() > 0: f2_weights = f2_weights / f2_weights.sum()
    if f3_weights.sum() > 0: f3_weights = f3_weights / f3_weights.sum()
    if tech_weights.sum() > 0: tech_weights = tech_weights / tech_weights.sum()

    df_copy = df.copy()
    df_copy["score_F1"] = df_copy[f1_cols].fillna(0).dot(f1_weights) if f1_cols else np.nan
    df_copy["score_F2"] = df_copy[f2_cols].fillna(0).dot(f2_weights) if f2_cols else np.nan
    df_copy["score_F3"] = df_copy[f3_cols].fillna(0).dot(f3_weights) if f3_cols else np.nan
    df_copy["score_tech"] = df_copy[tech_cols].fillna(0).dot(tech_weights) if tech_cols else np.nan
    
    ranked_dict[sector] = df_copy


# --- Score finale con media ponderata dei rank ---
sector_weights = {
    "Industrials": [0.5, 0.25, 0.25],
    "Health Care": [0.5, 0.25, 0.25],
    "Financials": [0.5, 0.25, 0.25],
    "Consumer Discretionary": [0.5, 0.25, 0.25],
    "Communication Services": [0.5, 0.25, 0.25],
    "Materials": [0.5, 0.25, 0.25],
    "Utilities": [0.5, 0.25, 0.25],
    "Real Estate": [0.5, 0.25, 0.25],
    "Consumer Staples": [0.5, 0.25, 0.25],
    "Information Technology": [0.5, 0.25, 0.25],
    "Energy": [0.5, 0.25, 0.25]
}


# --- Stili per le righe del DataTable dei coefficienti ---
html.Div([
    html.Label("Peso F1:"),
    dcc.Slider(
        id='peso-f1',
        min=0,
        max=1,
        step=0.05,
        value=0.5,
        marks={i/10: f'{i*10}%' for i in range(0, 11)},
        tooltip={"placement": "bottom", "always_visible": True}
    ),

    html.Label("Peso F2:"),
    dcc.Slider(
        id='peso-f2',
        min=0,
        max=1,
        step=0.05,
        value=0.25,
        marks={i/10: f'{i*10}%' for i in range(0, 11)},
        tooltip={"placement": "bottom", "always_visible": True}
    ),

    html.Label("Peso F3:"),
    dcc.Slider(
        id='peso-f3',
        min=0,
        max=1,
        step=0.05,
        value=0.25,
        marks={i/10: f'{i*10}%' for i in range(0, 11)},
        tooltip={"placement": "bottom", "always_visible": True}
    ),

    html.Button("Run", id='btn-run', n_clicks=0)
])


for sector, df in ranked_dict.items():
    if sector not in sector_weights:
        raise ValueError(f"Pesi mancanti per il settore: {sector}")
    
    weights = sector_weights[sector]
    
    df["score_fund"] = (
        df["score_F1"] * weights[0] +
        df["score_F2"] * weights[1] +
        df["score_F3"] * weights[2]
    )
    
    ranked_dict[sector] = df

# ordina per score fund 
for sector, df in ranked_dict.items():
    df_sorted = (
        df.sort_values(by=["Industry", "score_fund"], ascending=[True, False])
    )
    ranked_dict[sector] = df_sorted


# attribuisci rank
for sector, df in ranked_dict.items():
    # Ordina per industry e score_fund discendente
    df_sorted = df.sort_values(by=["Industry", "score_fund"], ascending=[True, False]).copy()

    # Conta il numero totale per ciascuna industry
    industry_counts = df_sorted["Industry"].value_counts()

    # Calcola il rank
    df_sorted["position_num"] = (
        df_sorted.groupby("Industry")["score_fund"]
        .rank(method="first", ascending=False)
        .astype(int)
    )

    df_sorted["position"] = df_sorted.apply(
        lambda row: f"{row['position_num']}/{industry_counts[row['Industry']]}",
        axis=1
    )

    # Droppa la colonna numerica intermedia se serve
    df_sorted.drop(columns=["position_num"], inplace=True)

    # Salva nel dizionario
    ranked_dict[sector] = df_sorted


for sector, df in ranked_dict.items():
    df_sorted = df.copy()

        # score_fund_rank: quintili per Industry
    df_sorted["rank_fund"] = (
        df_sorted.groupby("Industry")["score_fund"]
        .transform(lambda x: pd.qcut(x.rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]))
        .astype(int)
    )

    # score_tech_rank: quintili per Industry
    df_sorted["rank_tech"] = (
        df_sorted.groupby("Industry")["score_tech"]
        .transform(lambda x: pd.qcut(x.rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]))
        .astype(int)
    )

    ranked_dict[sector] = df_sorted

# --- Applica styling per score_fund, rank_tech, rank_fund per Industry ---
styled_ranked_dict = {}
for sector, df in ranked_dict.items():
    df_copy = df.copy()
    score_cols = ["score_fund", "rank_tech", "rank_fund"]
    norm_cols = []

    # Normalizza per Industry
    for col in score_cols:
        norm_col = f"__norm_{col}"
        norm_cols.append(norm_col)
        df_copy[norm_col] = (
            df_copy.groupby("Industry")[col]
            .transform(lambda x: (x - x.min()) / (x.max() - x.min() + 1e-9))
        )

    # Crea styler e applica il gradiente
    styled = df_copy.style
    for col, norm_col in zip(score_cols, norm_cols):
        styled = styled.background_gradient(cmap="RdYlGn", subset=[col], gmap=df_copy[norm_col])

    styled = styled.format(precision=2)  # arrotonda visivamente
    styled_ranked_dict[sector] = styled



#-----------------------------------------------------#
# --- Inizializzazione dell'app Dash -----------------#
#-----------------------------------------------------#
app = dash.Dash(__name__,
                 meta_tags=metas,
                 external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                 suppress_callback_exceptions=True  # non compare errore se non trona una componente in una tab, perchè viene usata in un'altra
)

#dbc.themes.COSMO
#dbc.themes.FLATLY
#dbc.themes.LUX
#dbc.themes.SLATE
#dbc.themes.SUPERHERO
#dbc.themes.YETI


#-----------------------------------------------------#
#---------------Layout dell'app-----------------------#
#-----------------------------------------------------#

# — Layout root —
app.layout = html.Div(
    className="app-bg",  # sfondo colorato
    children=[
        # header fisso 
        html.Div(
        className="sticky-top shadow-sm app-header",
        children=dbc.Container(
            className="content-narrow",  # per tenerlo largo come il resto
            children=[
                html.H2(app_title, className="m-0 fw-bold", style={"fontSize": "34px"}),
                html.Small("Fundamental and Technical analysis", className="text-white-50 d-block mt-1",style={"fontSize": "18px"}),
            ],
        ),
    ),

        # contenuto principale
        dbc.Container(
            id="page",
            fluid=True,     # permette di usare tutto lo spazio disponibile      
            className="content-narrow",
            children=[
                dbc.Tabs(
                    id="tabs",
                    active_tab="tab-intro",
                    className="mt-3 panel tabs-lg",   # pannello bianco intorno alle tabs
                    children=[
                        dbc.Tab(label="Intro", tab_id="tab-intro"),
                        dbc.Tab(label="Play", tab_id="tab-play"),
                        dbc.Tab(label="About Me", tab_id="tab-about"),
                    ],
                ),
                html.Div(id="tabs-content", className="mt-4 panel")
            ],
        )
    ],
)

# Callback per aggiornare contenuto in base alla tab selezionata
@app.callback(
    Output("tabs-content", "children"),
    Input("tabs", "active_tab")  
)
def render_tab(tab):
    if tab == "tab-intro":
        return html.Div([
            html.H2("Welcome to the Sector Ranking App"),
            dcc.Markdown(app_description),
            #html.P(app_description),

            html.Br()
        ])    
        

    elif tab == "tab-play":
        return html.Div([

            html.Div(
                [html.Span("Last update: ", className="text-muted me-1"),
                html.Strong(LAST_UPDATE_STR)],
                className="text-end small mb-2"
            ),

            html.H4("Step process"),
            dcc.Markdown(instructions, style={"marginBottom": "20px", "fontSize": "16px"}),

            html.Hr(), # aggiunge una linea

            html.H4("1. Select sector:"),
            dcc.Dropdown(
                id='dropdown-settore',
                options=[{"label": s, "value": s} for s in ranked_dict.keys()],
                value=list(ranked_dict.keys())[0]
            ),


            html.Hr(),

            html.Br(),# spazio vuoto tra le sezioni    

            # Modifica per i coefficienti
            html.H4("2. Coefficients for selected sector (optional):"),

            dbc.Row([
                dbc.Col([
                    html.Div("Equity Multiples total", className="fw-bold mb-1"),
                    dbc.Progress(id="prog-f1", value=0, max=100, color="warning",
                                striped=True, label="0%", style={"height": "10px"})
                ], md=4),
                dbc.Col([
                    html.Div("Profitability Multiples total", className="fw-bold mb-1"),
                    dbc.Progress(id="prog-f2", value=0, max=100, color="warning",
                                striped=True, label="0%", style={"height": "10px"})
                ], md=4),
                dbc.Col([
                    html.Div("Solidity Multiples total", className="fw-bold mb-1"),
                    dbc.Progress(id="prog-f3", value=0, max=100, color="warning",
                                striped=True, label="0%", style={"height": "10px"})
                ], md=4),
            ], className="g-2"),
            html.Small(id="coeff-progress-help", className="text-muted"),
            html.Br(),

            dash_table.DataTable(
                id="coeff-editor",
                columns=[
                    {"name": "Metric", "id": "metric"},
                    {"name": "Weight", "id": "weight", "type": "numeric"},
                ],
                data=[], editable=True, page_size=12,
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "6px"},
                style_header={"fontWeight": "bold", "backgroundColor": "#eee"},
                style_data_conditional=coeff_row_styles,

            ),

            html.Hr(),

            html.Br(),# spazio vuoto tra le sezioni
            
            html.H4("3. Modify group weights for selected sector (optional):"),

            html.Label("Equity Multiples:"),
            dcc.Slider(
                id='peso-f1',
                min=0, max=1, step=0.05, value=0.5,
                marks={i/10: f'{i*10}%' for i in range(11)},
                tooltip={"placement": "bottom", "always_visible": True}
            ),

            html.Label("Profitability Multiples:"),
            dcc.Slider(
                id='peso-f2',
                min=0, max=1, step=0.05, value=0.25,
                marks={i/10: f'{i*10}%' for i in range(11)},
                tooltip={"placement": "bottom", "always_visible": True}
            ),

            html.Label("Solidity Multiples:"),
            dcc.Slider(
                id='peso-f3',
                min=0, max=1, step=0.05, value=0.25,
                marks={i/10: f'{i*10}%' for i in range(11)},
                tooltip={"placement": "bottom", "always_visible": True}
            ),

            html.Div(className="mt-3", children=[
            html.Div("Total Weights", className="fw-bold mb-1"),
            dbc.Progress(
                id="weights-progress",
                value=0, max=100, color="warning",
                striped=True, animated=False,
                label="0%", style={"height": "12px"}
            ),
            html.Small(id="weights-progress-text", className="text-muted")
        ]),

            html.Hr(), 
            html.Br(),
            html.Button("▶️ Run", id='btn-run', n_clicks=0),   
            html.Br(),

            html.Div(id='output-tabella'),
            html.Br(),
            html.Div([
                html.Button("💼 Scarica Excel", id="btn-download", n_clicks=0),
                dcc.Download(id="download-excel")
                ], style={"marginBottom": "20px"}),

            # card per il grafico stock vs industry
            html.Hr(),
            dbc.Card([
                dbc.CardHeader("6. Stock metrics vs industry", className="text-white",
                               style={"backgroundColor": "#E6B75F", "fontSize": "18px"}),
                dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("Stock"),
                        dcc.Dropdown(
                            id="stock-input",
                            options=sorted(
                                [{"label": n, "value": n} for n in df_merged_raw["Name"].dropna().unique()],
                                key=lambda x: x["label"]
                            ),
                            placeholder="Type or select a stock…",
                            clearable=True
                        )
                    ], md=6),
                    dbc.Col([
                        html.Label("Group"),
                        dcc.Dropdown(
                            id="group-scope",
                            options=[
                                {"label": "All fundamentals multiple", "value": "FALL"},
                                {"label": "Equity multiples", "value": "F1"},
                                {"label": "Profitability multiples", "value": "F2"},
                                {"label": "Solidity multiples", "value": "F3"},
                                {"label": "Technical indicators", "value": "TECH"},
                            ],
                            value="FALL", clearable=False
                        )
                    ], md=4),

                    dbc.Col([
                        html.Label("Choose:"),
                        dcc.RadioItems(
                            id="agg-method",
                            options=[
                                {"label": "Mean", "value": "mean"},
                                {"label": "Median", "value": "median"}
                            ],
                            value="mean",
                            inline=True
                        )
                    ], md=3)

                ]),

                    html.Br(),
                    dcc.Graph(id="stock-bars", figure=px.bar(title="Select a stock to see the chart"))
                ])
            ], className="shadow-sm rounded-3", 
            style={"backgroundColor": "#FFF7E0"},
            ),

            html.Div(
                    dcc.Markdown("This information is intended solely as general information for educational and entertainment purposes only. It does not constitute investment advice, endorsement, or a recommendation to buy or sell any security. The author is not a licensed financial advisor and does not guarantee the accuracy or completeness of the information provided."),
                    className="p-2 mt-5 text-white small", 
                    style={"backgroundColor": "#403e40"},
                ), 

        ])

    
    elif tab == "tab-about":
        return html.Div([
            html.H1("Hello, my name is", style={"fontWeight": "bold", "color": "#888"}),
            html.H2("Pietro Bartolucci.", style={"fontWeight": "bold", "fontSize": "36px"}),

            html.Br(),
            html.P(presentation, style={"fontSize": "16px", "whiteSpace": "pre-line"}),
            html.Br(),

            html.A("➡️ Connect on LinkedIn",
                    href="https://www.linkedin.com/in/pietro-bartolucci",
                    target="_blank",
                    style={"fontWeight": "bold", "color": "#0077B5", "textDecoration": "none", "fontSize": "18px"}),

            html.Br(), html.Br(),

            html.Img(
                src="/assets/3.gif",
                style={
                    "height": "160px",       
                    "width": "160px",        
                    "marginTop": "20px"
         }
)


        ], style={
            "backgroundColor": "#e6f0f5",
            "padding": "40px",
            "borderRadius": "10px",
            "maxWidth": "600px",
            "margin": "auto",
            "textAlign": "center",
            "fontFamily": "Arial"
        })


#-----------------------------------------------------#
# ----------------------- Callback -------------------#
#-----------------------------------------------------#

@app.callback(
    Output("coeff-editor", "data"),
    Input("dropdown-settore", "value")
)
def load_coeff_editor(settore):
    if not settore or settore not in coeff.index:
        return []
    row = coeff.loc[settore]
    present = [c for c in all_cols if (c in row.index) and (c in ranked_dict[settore].columns)]
    data = []
    for c in present:
        v = pd.to_numeric(pd.Series([row.get(c)]), errors="coerce").iloc[0]
        data.append({"metric": c, "weight": 0.0 if pd.isna(v) else float(v)})
    return data

df_downloadable = None # Variabile globale per salvare il df da scaricare



@app.callback(
    Output("weights-progress", "value"),
    Output("weights-progress", "label"),
    Output("weights-progress", "color"),
    Output("weights-progress-text", "children"),
    Input("peso-f1", "value"),
    Input("peso-f2", "value"),
    Input("peso-f3", "value"),
)

def update_weights_progress(w1, w2, w3):
    total = sum((w or 0) for w in [w1, w2, w3])
    pct = int(round(total * 100))
    if abs(total - 1) < 1e-6:
        color, txt = "success", "Perfect: 100%."
    elif total < 1:
        color, txt = "warning", f"Total: {pct}% — Missing: {100 - pct}%"
    else:
        color, txt = "danger", f"Total exceeds 100% by {pct - 100}%"
    return min(pct, 100), f"{pct}%", color, txt

@app.callback(
    Output("prog-f1", "value"), Output("prog-f1", "label"), Output("prog-f1", "color"),
    Output("prog-f2", "value"), Output("prog-f2", "label"), Output("prog-f2", "color"),
    Output("prog-f3", "value"), Output("prog-f3", "label"), Output("prog-f3", "color"),
    Output("coeff-progress-help", "children"),
    Input("coeff-editor", "data")
)
def update_group_progress(data):
    def sum_group(cols):
        s = 0.0
        if not data: 
            return 0.0
        for rec in data:
            m = rec.get("metric")
            if m in cols:
                w = pd.to_numeric(rec.get("weight"), errors="coerce")
                s += 0.0 if pd.isna(w) else float(w)
        return s

    totals = {
        "F1": sum_group(f1_columns),
        "F2": sum_group(f2_columns),
        "F3": sum_group(f3_columns),
    }

    def fmt(total):
        pct = int(round(total * 100))
        if abs(total - 1) < 1e-6: color = "success"
        elif total < 1:           color = "warning"
        else:                     color = "danger"
        return min(pct, 100), f"{pct}%", color

    f1v, f1l, f1c = fmt(totals["F1"])
    f2v, f2l, f2c = fmt(totals["F2"])
    f3v, f3l, f3c = fmt(totals["F3"])

    help_txt = (f"Group totals - F1: {int(round(totals['F1']*100))}%  ·  "
                f"F2: {int(round(totals['F2']*100))}%  ·  "
                f"F3: {int(round(totals['F3']*100))}%.  "
                "Aim for 100% in each group.")

    return f1v, f1l, f1c, f2v, f2l, f2c, f3v, f3l, f3c, help_txt


@app.callback(
    Output('output-tabella', 'children'),
    Input('btn-run', 'n_clicks'),
    State('dropdown-settore', 'value'),
    State('peso-f1', 'value'),
    State('peso-f2', 'value'),
    State('peso-f3', 'value'),
    State('coeff-editor', 'data'),
    prevent_initial_call=True
)


def aggiorna_tabella(n_clicks, settore, peso_f1, peso_f2, peso_f3, coeff_data):
    global df_downloadable, coeff
    try:
        if not settore:
            return html.Div("Seleziona un settore.", style={"color": "red"})

        # Aggiorna i coefficienti dal DataTable
        if coeff_data:
            for rec in coeff_data:
                m = rec.get("metric")
                w = pd.to_numeric(rec.get("weight"), errors="coerce")
                if m in coeff.columns:
                    coeff.loc[settore, m] = 0.0 if pd.isna(w) else float(w)

        # Ricalcola score dei blocchi per il settore con i nuovi coefficienti
        base = df_dict_sector[settore].copy()
        coeff_row = coeff.loc[settore]

        def block_score(df, cols):
            cols = [c for c in cols if c in df.columns]
            if not cols:
                return pd.Series(np.nan, index=df.index)
            w = pd.to_numeric(coeff_row.reindex(cols), errors="coerce").fillna(0.0)
            if w.sum() == 0:
                return pd.Series(np.nan, index=df.index)
            w = w / w.sum()
            return df[cols].fillna(0).dot(w)

        f1_cols = [c for c in f1_columns if c in base.columns]
        f2_cols = [c for c in f2_columns if c in base.columns]
        f3_cols = [c for c in f3_columns if c in base.columns]
        tech_cols = [c for c in tech_columns if c in base.columns]

        df = base.copy()
        df["score_F1"]   = block_score(df, f1_cols)
        df["score_F2"]   = block_score(df, f2_cols)
        df["score_F3"]   = block_score(df, f3_cols)
        df["score_tech"] = block_score(df, tech_cols)

        # Score_fund dai tre slider (normalizzati)
        total = (peso_f1 or 0) + (peso_f2 or 0) + (peso_f3 or 0)
        if total <= 0:
            raise ValueError("I pesi non possono essere tutti zero.")
        w1, w2, w3 = (peso_f1 or 0)/total, (peso_f2 or 0)/total, (peso_f3 or 0)/total

        df["score_fund"] = (
            df["score_F1"].fillna(0)*w1 +
            df["score_F2"].fillna(0)*w2 +
            df["score_F3"].fillna(0)*w3
        )

        # Ordina, position x/y, quintili 
        df_sorted = df.sort_values(by=["Industry", "score_fund"], ascending=[True, False]).copy()
        counts = df_sorted.groupby("Industry")["Name"].transform("count")
        df_sorted["position_num"] = (
            df_sorted.groupby("Industry")["score_fund"]
                     .rank(method="first", ascending=False)
                     .astype(int)
        )
        df_sorted["position"] = df_sorted["position_num"].astype(str) + "/" + counts.astype(str)
        df_sorted.drop(columns=["position_num"], inplace=True)

        df_sorted["rank_fund"] = (
            df_sorted.groupby("Industry")["score_fund"]
                     .transform(lambda x: pd.qcut(x.rank(method="first"), q=5, labels=[1,2,3,4,5]))
                     .astype(int)
        )
        df_sorted["rank_tech"] = (
            df_sorted.groupby("Industry")["score_tech"]
                     .transform(lambda x: pd.qcut(x.rank(method="first"), q=5, labels=[1,2,3,4,5]))
                     .astype(int)
        )

        # Prepara view e download
        df_downloadable = df_sorted.copy()          
        df_view = df_sorted.round(2).replace({np.nan: "-", pd.NA: "-"}).astype(str)

        return dash_table.DataTable(
            columns=[{'name': c, 'id': c} for c in df_view.columns],
            data=df_view.to_dict('records'),
            page_size=15,
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'left', 'padding': '5px'},
            style_header={'fontWeight': 'bold', 'backgroundColor': '#eee'},
            style_data_conditional=[
                {'if': {'column_id': 'rank_fund'}, 'backgroundColor': '#D2FAD2'},
                {'if': {'column_id': 'rank_tech'}, 'backgroundColor': '#D2F0FA'}
            ]
        )

    except Exception as e:
        return html.Div(f"Errore: {str(e)}", style={"color": "red"})

    
@app.callback(
    Output("download-excel", "data"),
    Input("btn-download", "n_clicks"),
    prevent_initial_call=True
)
def download_excel(n_clicks):
    global df_downloadable
    if df_downloadable is not None and not df_downloadable.empty:
        return dcc.send_data_frame(
            df_downloadable.to_excel,
            filename="ranking_settoriale.xlsx",
            sheet_name="Rank",
            index=False
        )
    return dash.no_update


def _cols_for_scope(scope):
    if scope == "F1":   return [c for c in f1_columns if c in df_merged_raw.columns]
    if scope == "F2":   return [c for c in f2_columns if c in df_merged_raw.columns]
    if scope == "F3":   return [c for c in f3_columns if c in df_merged_raw.columns]
    if scope == "TECH": return [c for c in tech_columns if c in df_merged_raw.columns]
    if scope == "FALL": return [c for c in (f1_columns + f2_columns + f3_columns) if c in df_merged_raw.columns]
    return [c for c in (f1_columns + f2_columns + f3_columns + tech_columns) if c in df_merged_raw.columns]

# --- stile righe per gruppi nel coeff-editor ---
def _group_row_style(cols, color):
    if not cols: 
        return []
    # colora le righe il cui campo {metric} è in 'cols'
    filt = " || ".join([f'{{metric}} = "{c}"' for c in cols])
    return [{
        "if": {"filter_query": f"({filt})"},
        "backgroundColor": color
    }]

coeff_row_styles = (
    _group_row_style(f1_columns, "rgba(255, 248, 230, 0.65)") +  
    _group_row_style(f2_columns, "rgba(234, 242, 255, 0.55)") +  
    _group_row_style(f3_columns, "rgba(241, 248, 245, 0.55)")    
)


@app.callback(
    Output("stock-bars", "figure"),
    Input("stock-input", "value"),
    Input("group-scope", "value"),
    Input("agg-method", "value")
)

def update_stock_chart(stock_name, scope, agg_method):
    return draw_stock_vs_industry(stock_name, scope, agg_method)

def draw_stock_vs_industry(stock_name, scope, agg_method="mean"):
    if not stock_name:
        return go.Figure(layout_title_text="Select a stock to see the chart")

    row_df = df_merged_raw[df_merged_raw["Name"] == stock_name]
    if row_df.empty:
        return go.Figure(layout_title_text=f"'{stock_name}' not found.")
    row = row_df.iloc[0]
    industry = row["Industry"]

    # colonne da mostrare
    def _cols_for_scope(scope):
        if scope == "F1":   return [c for c in f1_columns if c in df_merged_raw.columns]
        if scope == "F2":   return [c for c in f2_columns if c in df_merged_raw.columns]
        if scope == "F3":   return [c for c in f3_columns if c in df_merged_raw.columns]
        if scope == "TECH": return [c for c in tech_columns if c in df_merged_raw.columns]
        if scope == "FALL": return [c for c in (f1_columns + f2_columns + f3_columns) if c in df_merged_raw.columns]
        return [c for c in (f1_columns + f2_columns + f3_columns + tech_columns) if c in df_merged_raw.columns]

    cols = _cols_for_scope(scope)
    cols = [c for c in cols if pd.notna(row.get(c))]
    if not cols:
        return go.Figure(layout_title_text="No available metrics for this selection.")

    # media o mediana industry
    ind_df = df_merged_raw[df_merged_raw["Industry"] == industry][cols]
    if agg_method == "median":
        ind_stats = ind_df.median(skipna=True)
    else:
        ind_stats = ind_df.mean(skipna=True)

    stock_vals = [row[c] for c in cols]
    ind_vals   = [ind_stats[c] for c in cols]

    fig = go.Figure()
    fig.add_bar(name=stock_name, x=cols, y=stock_vals)
    fig.add_bar(name=f"{industry} ({agg_method})", x=cols, y=ind_vals, opacity=0.6)

    # layout
    fig.update_layout(
        title=f"{stock_name} vs {industry} average ({agg_method})",
        xaxis_title=None, yaxis_title="Metrics",
        bargap=0.25, height=420, margin=dict(l=20, r=20, t=60, b=80),
        legend_title=None
    )
    fig.update_xaxes(tickangle=-35)
    fig.add_hline(y=0, line_width=1, line_dash="dot", opacity=0.5)

    return fig


import os

server = app.server

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8050)),
        debug=True
    )
