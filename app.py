import streamlit as st
import yfinance as yf
import pandas as pd
import numpy_financial as npf
import numpy as np
import requests
from datetime import date, timedelta
import datetime
import json
from streamlit_local_storage import LocalStorage
import plotly.graph_objects as go  # Für fortgeschrittene Tooltips und duale Y-Achsen

# --- SEITEN-KONFIGURATION ---
st.set_page_config(page_title="Sparplan Rechner", layout="wide")
st.title("📈 Historischer Sparplan Rechner")
st.write("Vergleiche ausschüttende und thesaurierende (Reinvest) Strategien nach Steuern. Parameter werden lokal gespeichert.")

# --- HILFSFUNKTION FÜR LOGO (OPTIMIERT MIT DUCKDUCKGO & FALLBACK) ---
def get_logo_url(ticker, name=""):
    name_upper = name.upper()
    
    # Mapping auf Domains für hochverfügbare Icons (DuckDuckGo Favicon Service)
    issuers = {
        "ISHARES": "ishares.com",
        "BLACKROCK": "blackrock.com",
        "VANGUARD": "vanguard.com",
        "XTRACKERS": "xtrackers.com",
        "DWS": "dws.com",
        "INVESCO": "invesco.com",
        "AMUNDI": "amundi.com",
        "LYXOR": "amundi.com",
        "SPDR": "ssga.com",
        "STATE STREET": "ssga.com",
        "HSBC": "hsbc.com",
        "VANECK": "vaneck.com",
        "WISDOMTREE": "wisdomtree.com",
        "FIDELITY": "fidelity.com",
        "RIO TINTO": "riotinto.com",
        "UBS": "ubs.com",
        "BNP": "bnpparibas.com",
        "LEGAL & GENERAL": "legalandgeneral.com", 
        "L&G": "legalandgeneral.com"               
    }

    domain = None
    for key, d in issuers.items():
        if key in name_upper:
            domain = d
            break
    
    if domain:
        return f"https://icons.duckduckgo.com/ip3/{domain}.ico"

    clean_ticker = ticker.split('.')[0].upper()
    return f"https://financialmodelingprep.com/image-stock/{clean_ticker}.png"

# --- LOCAL STORAGE BRÜCKE ---
localS = LocalStorage()
stored_history = localS.getItem("asset_history")
stored_configs = localS.getItem("asset_configs")

# --- INITIALISIERUNG: SESSION STATE ---
if 'history' not in st.session_state:
    st.session_state.history = []
    if stored_history:
        try:
            parsed_history = json.loads(stored_history) if isinstance(stored_history, str) else stored_history
            if isinstance(parsed_history, list):
                st.session_state.history = parsed_history
        except Exception:
            pass

if 'selected_from_history' not in st.session_state:
    st.session_state.selected_from_history = None

if 'asset_configs' not in st.session_state:
    st.session_state.asset_configs = {}
    if stored_configs:
        try:
            parsed_configs = json.loads(stored_configs) if isinstance(stored_configs, str) else stored_configs
            if isinstance(parsed_configs, dict):
                st.session_state.asset_configs = parsed_configs
        except Exception:
            pass

default_config = {
    "start_capital": 10000.0,
    "monthly_rate": 100.0,
    "fee_type": "Prozentual (%)",
    "fee_value": 1.5,
    "tax_rate": 25.0
}

# --- HILFSFUNKTIONEN ---
@st.cache_data(ttl=3600)
def search_ticker(query):
    if not query:
        return pd.DataFrame()
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        results = []
        for res in data.get('quotes', []):
            if res.get('quoteType') in ['EQUITY', 'ETF']:
                results.append({
                    "Symbol": res.get('symbol', ''),
                    "Name": res.get('shortname', res.get('symbol', '')),
                    "Börse": res.get('exchDisp', 'Unbekannt'),
                    "Typ": res.get('quoteType', '')
                })
        return pd.DataFrame(results)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_historical_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="max", interval="1mo", auto_adjust=False, back_adjust=False)
        if not data.empty and 'Close' in data.columns:
            if 'Dividends' not in data.columns:
                data['Dividends'] = 0.0
            df = data[['Close', 'Dividends']].copy()
            df = df.dropna(subset=['Close'])
            df['Dividends'] = df['Dividends'].fillna(0.0)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            return df
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_asset_details(ticker):
    try:
        t = yf.Ticker(ticker)
        return {
            "isin": t.isin if t.isin and t.isin != "-" else t.info.get('isin', 'N/A'),
            "long_name": t.info.get('longName') or t.info.get('shortName')
        }
    except:
        return {"isin": "N/A", "long_name": None}

# --- LAYOUT: SUCHE & TREFFERLISTE ---
st.markdown("---")
col_input, col_table = st.columns([1, 2])

selected_ticker = None
selected_name = None

with col_input:
    st.subheader("1. Asset suchen")
    if st.session_state.history:
        history_options = ["--- Neu suchen ---"] + [f"{item['Name']} ({item['Symbol']})" for item in st.session_state.history]
        chosen_history = st.selectbox("Aus Verlauf wählen (letzte 100):", options=history_options)
        
        if chosen_history != "--- Neu suchen ---":
            symbol_part = chosen_history.split("(")[-1].replace(")", "")
            name_part = chosen_history.rsplit(" (", 1)[0]
            st.session_state.selected_from_history = {"Symbol": symbol_part, "Name": name_part}
            
            # --- FUNKTION: EINTRAG LÖSCHEN ---
            if st.button("🗑️ Diesen Eintrag aus Verlauf löschen", type="secondary", use_container_width=True):
                st.session_state.history = [h for h in st.session_state.history if h['Symbol'] != symbol_part]
                localS.setItem("asset_history", json.dumps(st.session_state.history[:100]), key=f"del_{symbol_part}")
                st.session_state.selected_from_history = None
                st.rerun()
        else:
            st.session_state.selected_from_history = None

    search_query = st.text_input("Oder Suchbegriff eingeben:", "LUK2.L")

with col_table:
    st.subheader("2. Trefferliste")
    if st.session_state.selected_from_history:
        selected_ticker = st.session_state.selected_from_history["Symbol"]
        selected_name = st.session_state.selected_from_history["Name"]
        st.success(f"✅ Ausgewählt aus Verlauf: **{selected_name} ({selected_ticker})**")
    else:
        df_results = search_ticker(search_query)
        if not df_results.empty:
            event = st.dataframe(
                df_results,
                width="stretch", 
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            if event.selection.rows:
                selected_row_index = event.selection.rows[0]
                selected_ticker = df_results.iloc[selected_row_index]["Symbol"]
                selected_name = df_results.iloc[selected_row_index]["Name"]
                
                # --- LONG NAME FÜR VERLAUF HOLEN ---
                with st.spinner("Lade Details..."):
                    try:
                        t_info = yf.Ticker(selected_ticker).info
                        long_name = t_info.get('longName') or t_info.get('shortName')
                        if long_name:
                            selected_name = long_name
                    except Exception:
                        pass
                
                st.success(f"✅ Ausgewählt: **{selected_name} ({selected_ticker})**")
                
                new_entry = {"Symbol": selected_ticker, "Name": selected_name}
                if new_entry not in st.session_state.history:
                    st.session_state.history = [h for h in st.session_state.history if h['Symbol'] != selected_ticker]
                    st.session_state.history.insert(0, new_entry)
                    st.session_state.history = st.session_state.history[:100]
                    localS.setItem("asset_history", json.dumps(st.session_state.history), key=f"h_save_{selected_ticker}")
            else:
                st.warning("👆 Bitte klicke auf eine Zeile in der Tabelle, um das Asset auszuwählen.")
        else:
            st.error("Keine Treffer gefunden.")

# --- DATEN LADEN & HEADER MIT LOGO + ISIN + FULL NAME ---
hist_df = pd.DataFrame()
oldest_available_date = pd.to_datetime("2015-01-01").date()
asset_isin = ""
display_name = ""

if selected_ticker:
    st.markdown("---")
    
    # Details (ISIN & Long Name) abrufen
    details = get_asset_details(selected_ticker)
    asset_isin = details["isin"]
    display_name = details["long_name"] if details["long_name"] else selected_name

    col_logo, col_title = st.columns([1, 15])
    with col_logo:
        st.image(get_logo_url(selected_ticker, display_name), width=65)
    with col_title:
        display_isin = f" | ISIN: {asset_isin}" if asset_isin and asset_isin != "-" else ""
        st.subheader(f"Auswertung: {display_name} ({selected_ticker}){display_isin}")

    with st.spinner("Lade Historie..."):
        hist_df = get_historical_data(selected_ticker)
    if not hist_df.empty:
        oldest_available_date = hist_df.index.min().date()
    else:
        st.error("Konnte keine historischen Kurse laden.")

# --- CONFIG BESTIMMEN ---
active_config = default_config.copy()
if selected_ticker and selected_ticker in st.session_state.asset_configs:
    active_config.update(st.session_state.asset_configs[selected_ticker])

safe_ticker = selected_ticker if selected_ticker else "default_ticker"

# --- SIDEBAR: PARAMETER SETZEN ---
st.sidebar.header("Sparplan Parameter")

start_capital = st.sidebar.number_input("Startkapital (€)", min_value=0.0, value=float(active_config.get("start_capital", 10000.0)), step=1000.0, key=f"cap_{safe_ticker}")
monthly_rate = st.sidebar.number_input("Sparrate pro Monat (€)", min_value=0.0, value=float(active_config.get("monthly_rate", 100.0)), step=50.0, key=f"rate_{safe_ticker}")

st.sidebar.markdown("### Gebühren")
fee_index = 0 if active_config.get("fee_type", "Prozentual (%)") == "Prozentual (%)" else 1
fee_type = st.sidebar.radio("Art der Gebühr", ["Prozentual (%)", "Absolut (€)"], index=fee_index, horizontal=True, key=f"feetype_{safe_ticker}")

if fee_type == "Prozentual (%)":
    fee_value = st.sidebar.number_input("Gebühr (%)", min_value=0.0, value=float(active_config.get("fee_value", 1.5)), step=0.1, key=f"fee_perc_{safe_ticker}")
else:
    fee_value = st.sidebar.number_input("Gebühr (€)", min_value=0.0, value=float(active_config.get("fee_value", 1.50)), step=0.5, key=f"fee_abs_{safe_ticker}")

st.sidebar.markdown("### Steuern (auf Dividenden)")
tax_rate = st.sidebar.number_input("Steuerpauschale (%)", min_value=0.0, max_value=100.0, value=float(active_config.get("tax_rate", 25.0)), step=1.0, help="Steuersatz bei Ausschüttungen.", key=f"tax_{safe_ticker}")

st.sidebar.markdown("### Zeitraum & Schnellauswahl")
min_allowed_date = datetime.date(1900, 1, 1)

# Schnellauswahl Buttons
today = date.today()
col_q1, col_q2 = st.sidebar.columns(2)
col_q3, col_q4 = st.sidebar.columns(2)

if col_q1.button("1 Jahr", key=f"1y_{safe_ticker}"):
    st.session_state[f"startdate_{safe_ticker}"] = max(oldest_available_date, today - timedelta(days=365))
    st.session_state[f"enddate_{safe_ticker}"] = today
    st.rerun()

if col_q2.button("3 Jahre", key=f"3y_{safe_ticker}"):
    st.session_state[f"startdate_{safe_ticker}"] = max(oldest_available_date, today - timedelta(days=3*365))
    st.session_state[f"enddate_{safe_ticker}"] = today
    st.rerun()

if col_q3.button("5 Jahre", key=f"5y_{safe_ticker}"):
    st.session_state[f"startdate_{safe_ticker}"] = max(oldest_available_date, today - timedelta(days=5*365))
    st.session_state[f"enddate_{safe_ticker}"] = today
    st.rerun()

if col_q4.button("10 Jahre", key=f"10y_{safe_ticker}"):
    st.session_state[f"startdate_{safe_ticker}"] = max(oldest_available_date, today - timedelta(days=10*365))
    st.session_state[f"enddate_{safe_ticker}"] = today
    st.rerun()

if st.sidebar.button("📅 Frühestes Datum setzen", key=f"min_{safe_ticker}"):
    st.session_state[f"startdate_{safe_ticker}"] = oldest_available_date
    st.rerun()

start_date_val = st.session_state.get(f"startdate_{safe_ticker}", oldest_available_date)
start_date = st.sidebar.date_input("Startdatum", value=start_date_val, min_value=min_allowed_date, max_value=date.today(), format="DD.MM.YYYY", key=f"startdate_{safe_ticker}")

if st.sidebar.button("📅 Heute setzen", key=f"today_{safe_ticker}"):
    st.session_state[f"enddate_{safe_ticker}"] = date.today()
    st.rerun()

end_date_val = st.session_state.get(f"enddate_{safe_ticker}", date.today())
end_date = st.sidebar.date_input("Enddatum", value=end_date_val, min_value=min_allowed_date, max_value=date.today(), format="DD.MM.YYYY", key=f"enddate_{safe_ticker}")

# --- CONFIG IM BROWSER AKTUALISIEREN ---
if selected_ticker:
    current_config = {
        "start_capital": start_capital,
        "monthly_rate": monthly_rate,
        "fee_type": fee_type,
        "fee_value": fee_value,
        "tax_rate": tax_rate,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d")
    }
    saved_config = st.session_state.asset_configs.get(selected_ticker)
    if saved_config != current_config:
        st.session_state.asset_configs[selected_ticker] = current_config
        localS.setItem("asset_configs", json.dumps(st.session_state.asset_configs), key=f"c_save_{selected_ticker}")


# --- BERECHNUNG ---
if selected_ticker and not hist_df.empty:
    df_filtered = hist_df[(hist_df.index.date >= start_date) & (hist_df.index.date <= end_date)]
    
    if df_filtered.empty:
        st.error("In diesem Zeitraum sind keine Kursdaten verfügbar.")
    elif start_date > end_date:
        st.error("Das Startdatum darf nicht nach dem Enddatum liegen.")
    else:
        # Globale Variablen
        invested_brutto = 0.0  
        invested_netto = 0.0   
        total_fees = 0.0
        
        shares_no_reinv = 0.0
        port_vals_no_reinv = []
        cashflows_no_reinv = [] # WICHTIG FÜR IZF
        total_divs_net_no_reinv = 0.0
        
        shares_reinv = 0.0
        port_vals_reinv = []
        cashflows_reinv = [] # WICHTIG FÜR IZF
        total_divs_net_reinv = 0.0
        
        dates = []
        invested_values_brutto = []
        div_data_for_table = []
        div_data_re_for_table = [] 
        growth_factors = []
        prev_price = None
        
        yearly_stats = {}

        tax_multiplier = 1.0 - (tax_rate / 100.0)
        
        for d, row in df_filtered.iterrows():
            price = float(row['Close'])
            div_per_share = float(row['Dividends'])
            year = d.year
            
            if year not in yearly_stats:
                yearly_stats[year] = {
                    "Start_No": shares_no_reinv * price if shares_no_reinv > 0 else (start_capital if d == df_filtered.index[0] else 0),
                    "Start_Re": shares_reinv * price if shares_reinv > 0 else (start_capital if d == df_filtered.index[0] else 0),
                    "Div_No": 0.0,
                    "Div_Re": 0.0,
                    "End_No": 0.0,
                    "End_Re": 0.0
                }

            # --- 1. DIVIDENDEN BEHANDELN ---
            div_gross_no = shares_no_reinv * div_per_share
            div_net_no = div_gross_no * tax_multiplier
            total_divs_net_no_reinv += div_net_no
            yearly_stats[year]["Div_No"] += div_net_no
            
            div_gross_re = shares_reinv * div_per_share
            div_net_re = div_gross_re * tax_multiplier
            total_divs_net_reinv += div_net_re
            yearly_stats[year]["Div_Re"] += div_net_re
            
            if price > 0:
                shares_reinv += (div_net_re / price)
            
            div_data_for_table.append({"Datum": d, "Jahr": year, "Monat": d.strftime("%b"), "Betrag": div_net_no})
            div_data_re_for_table.append({"Datum": d, "Jahr": year, "Monat": d.strftime("%b"), "Betrag": div_net_re}) 

            # --- 2. REGULÄRE INVESTITION ---
            investment_brutto = start_capital if d == df_filtered.index[0] else monthly_rate
            
            if investment_brutto > 0:
                if fee_type == "Prozentual (%)":
                    current_fee = investment_brutto * (fee_value / 100.0)
                else:
                    current_fee = fee_value
                
                current_fee = min(current_fee, investment_brutto)
                investment_netto = investment_brutto - current_fee
                total_fees += current_fee
            else:
                investment_netto = 0.0
            
            invested_brutto += investment_brutto
            invested_netto += investment_netto
            
            if price > 0:
                shares_no_reinv += (investment_netto / price)
                shares_reinv += (investment_netto / price)
            
            # TTWROR Logik
            if prev_price is not None and prev_price > 0:
                growth_factors.append((price + div_per_share * tax_multiplier) / prev_price)
            prev_price = price

            # --- 3. WERTE SPEICHERN ---
            port_vals_no_reinv.append(shares_no_reinv * price)
            port_vals_reinv.append(shares_reinv * price)
            invested_values_brutto.append(invested_brutto)
            dates.append(d)
            
            yearly_stats[year]["End_No"] = shares_no_reinv * price
            yearly_stats[year]["End_Re"] = shares_reinv * price
            
            # WICHTIG FÜR IZF BERECHNUNG
            cashflows_no_reinv.append(-investment_brutto + div_net_no)
            cashflows_reinv.append(-investment_brutto)
        
        # --- ENDABRECHNUNG & IZF BERECHNUNG ---
        last_c = float(df_filtered.iloc[-1]['Close'])
        end_cap_no = shares_no_reinv * last_c
        end_cap_re = shares_reinv * last_c
        
        cashflows_no_reinv[-1] += end_cap_no
        cashflows_reinv[-1] += end_cap_re
        
        irr_no = ((1 + npf.irr(cashflows_no_reinv))**12 - 1) * 100 if not pd.isna(npf.irr(cashflows_no_reinv)) else 0
        irr_re = ((1 + npf.irr(cashflows_reinv))**12 - 1) * 100 if not pd.isna(npf.irr(cashflows_reinv)) else 0
        ttwror_v = (np.prod(growth_factors) - 1) * 100 if growth_factors else 0

        # --- AUSGABE ---
        st.markdown("---")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Brutto eingezahlt", f"{invested_brutto:,.2f} €")
        col_m2.metric("Gebühren", f"- {total_fees:,.2f} €", delta_color="inverse")
        col_m3.metric("Netto investiert", f"{invested_netto:,.2f} €")
        
        # --- CHART BEREICH ---
        st.subheader("Kapitalentwicklung & Kursverlauf")
        
        chart_df = pd.DataFrame({
            "Thesaurierend (Mit Reinvest)": port_vals_reinv,
            "Ausschüttend (Ohne Reinvest)": port_vals_no_reinv,
            "Eingezahltes Kapital": invested_values_brutto
        }, index=dates)

        benchmarks = st.multiselect(
            "Benchmarks hinzufügen:",
            ["MSCI World (IWDA.AS)", "SPDR MSCI ACWI IMI (SPYI.DE)", "S&P 500 (^GSPC)", "DAX (^GDAXI)", "Bitcoin (BTC-EUR)"],
            default=[]
        )

        for b_name in benchmarks:
            t_id = b_name.split("(")[-1].replace(")", "")
            b_df = get_historical_data(t_id)
            b_df = b_df[(b_df.index.date >= start_date) & (b_df.index.date <= end_date)].copy()
            if not b_df.empty:
                b_shares, b_vals = 0.0, []
                # FIX FÜR ZEILE 479 (iterrows anstatt iter)
                for d_b, row_b in b_df.iterrows():
                    p_b = float(row_b['Close'])
                    inv_b = start_capital if len(b_vals) == 0 else monthly_rate
                    b_shares += (inv_b / p_b)
                    b_vals.append(b_shares * p_b)
                chart_df[b_name] = pd.Series(b_vals, index=b_df.index).reindex(dates, method='ffill')

        # --- PLOTLY DUAL Y-AXIS CHART (SORTIERT) ---
        fig = go.Figure()
        
        portfolio_colors = {
            "Thesaurierend (Mit Reinvest)": "#228B22", # Dunkleres Grün
            "Ausschüttend (Ohne Reinvest)": "#90EE90", # Helles Grün
            "Eingezahltes Kapital": "#808080"        # Grau
        }
        
        # LOGIK FÜR ABSTEIGENDE SORTIERUNG (Nach dem Wert der letzten Zeile)
        sorted_cols = chart_df.iloc[-1].sort_values(ascending=False).index
        
        for col in sorted_cols:
            line_style = dict(width=2)
            if col in portfolio_colors:
                line_style['color'] = portfolio_colors[col]
            
            fig.add_trace(go.Scatter(
                x=chart_df.index, y=chart_df[col], mode='lines', name=col,
                line=line_style,
                hovertemplate=f'<b>{col}</b>: %{{y:,.2f}} €<extra></extra>' 
            ))

        # Trace für reinen Aktienkurs (Y-Achse Rechts) - Neon Blau
        fig.add_trace(go.Scatter(
            x=df_filtered.index, y=df_filtered['Close'], mode='lines', 
            name=f"Kurs: {selected_ticker}", yaxis="y2",
            line=dict(color="#00FFFF", width=1.5, dash="dot"), # Neon Blau
            hovertemplate=f'<b>Kurs ({selected_ticker})</b>: %{{y:,.2f}} €<extra></extra>'
        ))

        fig.update_layout(
            hovermode="x unified", separators=',.',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(l=0, r=0, t=50, b=0),
            template="plotly_dark", height=650,
            
            yaxis=dict(
                title="Kapitalentwicklung (€)", showgrid=True, gridcolor="#333", 
                tickformat=',.2f', autorange=True, fixedrange=False, rangemode="nonnegative"
            ),
            
            yaxis2=dict(
                title="Aktienkurs (€)", overlaying="y", side="right", 
                showgrid=False, tickformat=',.2f', autorange=True, fixedrange=False
            ),
            
            xaxis=dict(
                showgrid=True, gridcolor="#333", rangeslider_visible=True,
                rangeselector=dict(buttons=list([
                    dict(count=1, label="1j", step="year", stepmode="backward"),
                    dict(count=5, label="5j", step="year", stepmode="backward"),
                    dict(step="all", label="Alles")
                ]), bgcolor="#1e1e1e")
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # --- TABS FÜR HISTORIE UND MATRIX ---
        st.write("")
        monate_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        # NUR TABS ANZEIGEN WENN ES DIVIDENDEN GAB
        if total_divs_net_no_reinv > 0:
            tab1, tab2 = st.tabs(["💸 Ohne Reinvestition (Ausschüttend)", "🔄 Mit Reinvestition (Thesaurierend)"])

            with tab1:
                c1, c2, c3, c4, c5 = st.columns(5) 
                c1.metric("Endkapital", f"{end_cap_no:,.2f} €", f"{end_cap_no - invested_brutto:,.2f} € Kursgewinn")
                c2.metric("Anteile (Gesamt)", f"{shares_no_reinv:,.4f}", "(Alle aus Einzahlungen)", delta_color="off")
                c3.metric("Auszahlungen (Netto)", f"+ {total_divs_net_no_reinv:,.2f} €")
                c4.metric("IZF (p.a.)", f"{irr_no:.2f} %")
                c5.metric("TTWROR", f"{ttwror_v:.2f} %")
                
                st.write("### Jahreshistorie (Ausschüttend)")
                df_y_no = pd.DataFrame.from_dict(yearly_stats, orient='index')[["Start_No", "End_No", "Div_No"]]
                df_y_no.columns = ["Startkapital", "Endkapital", "Dividende (Netto)"]
                st.dataframe(df_y_no.style.format("{:,.2f} €"), width="stretch")
                
                st.write("### Dividenden Kalender (Ausschüttend)")
                if div_data_for_table:
                    df_t = pd.DataFrame(div_data_for_table)
                    pivot_t = df_t.pivot_table(index='Jahr', columns='Monat', values='Betrag', aggfunc='sum').fillna(0)
                    pivot_t = pivot_t.reindex(columns=[m for m in monate_order if m in pivot_t.columns])
                    pivot_t['Gesamt'] = pivot_t.sum(axis=1)
                    st.dataframe(pivot_t.style.format("{:.2f} €"), width="stretch")
                
            with tab2:
                c1, c2, c3, c4, c5 = st.columns(5) 
                c1.metric("Endkapital", f"{end_cap_re:,.2f} €", f"{end_cap_re - invested_brutto:,.2f} € Gesamtgewinn")
                c2.metric("Anteile (Gesamt)", f"{shares_reinv:,.4f}", f"({shares_no_reinv:,.4f} Einz. | {(shares_reinv - shares_no_reinv):,.4f} Div.)", delta_color="off")
                c3.metric("Reinvestiert (Netto)", f"{total_divs_net_reinv:,.2f} €")
                c4.metric("IZF (p.a.)", f"{irr_re:.2f} %")
                c5.metric("TTWROR", f"{ttwror_v:.2f} %")
                
                st.write("### Jahreshistorie (Thesaurierend)")
                df_y_re = pd.DataFrame.from_dict(yearly_stats, orient='index')[["Start_Re", "End_Re", "Div_Re"]]
                df_y_re.columns = ["Startkapital", "Endkapital", "Reinvestiert (Netto)"]
                st.dataframe(df_y_re.style.format("{:,.2f} €"), width="stretch")
                
                st.write("### Dividenden Kalender (Thesaurierend)")
                if div_data_re_for_table:
                    df_t_re = pd.DataFrame(div_data_re_for_table)
                    pivot_t_re = df_t_re.pivot_table(index='Jahr', columns='Monat', values='Betrag', aggfunc='sum').fillna(0)
                    pivot_t_re = pivot_t_re.reindex(columns=[m for m in monate_order if m in pivot_t_re.columns])
                    pivot_t_re['Gesamt'] = pivot_t_re.sum(axis=1)
                    st.dataframe(pivot_t_re.style.format("{:.2f} €"), width="stretch")

            # --- DIVIDENDEN MATRIX GESAMT ---
            st.subheader("Dividenden Kalender (Gesamt-Übersicht)")
            if div_data_for_table:
                df_total = pd.DataFrame(div_data_for_table)
                pivot_total = df_total.pivot_table(index='Jahr', columns='Monat', values='Betrag', aggfunc='sum').fillna(0)
                pivot_total = pivot_total.reindex(columns=[m for m in monate_order if m in pivot_total.columns])
                pivot_total['Gesamt'] = pivot_total.sum(axis=1)
                st.dataframe(pivot_total.style.format("{:.2f} €"), width="stretch")
                
        else:
            # WENN KEINE DIVIDENDEN GEZAHLT WURDEN (NUR EIN TAB ANZEIGEN)
            tab1 = st.tabs(["📈 Portfolio Historie"])[0]
            
            with tab1:
                c1, c2, c3, c4 = st.columns(4) 
                c1.metric("Endkapital", f"{end_cap_no:,.2f} €", f"{end_cap_no - invested_brutto:,.2f} € Kursgewinn")
                c2.metric("Anteile (Gesamt)", f"{shares_no_reinv:,.4f}", "(Alle aus Einzahlungen)", delta_color="off")
                c3.metric("IZF (p.a.)", f"{irr_no:.2f} %")
                c4.metric("TTWROR", f"{ttwror_v:.2f} %")
                
                st.write("### Jahreshistorie")
                df_y_no = pd.DataFrame.from_dict(yearly_stats, orient='index')[["Start_No", "End_No"]]
                df_y_no.columns = ["Startkapital", "Endkapital"]
                st.dataframe(df_y_no.style.format("{:,.2f} €"), width="stretch")

        # =====================================================================
        # NEU: ROLLIERENDE DEKADEN-RENDITE
        # =====================================================================
        st.markdown("---")
        st.subheader("🔁 Rollierende 10-Jahres-Renditen (Buy & Hold)")
        st.write("Zeigt die jährliche Rendite (CAGR), wenn das Asset jeweils am ersten Tag eines Jahres gekauft und exakt 10 Jahre gehalten worden wäre (inklusive fiktiver Reinvestition der Netto-Dividenden).")

        if not df_filtered.empty:
            # Konstruiere einen sauberen Total Return Index (TRI) für das Basis-Asset
            tri_dates = []
            tri_vals = []
            current_tri_shares = 100.0 / float(df_filtered.iloc[0]['Close']) if float(df_filtered.iloc[0]['Close']) > 0 else 0
            
            for d, row in df_filtered.iterrows():
                p = float(row['Close'])
                div = float(row['Dividends'])
                
                if p > 0 and div > 0:
                    current_tri_shares += (current_tri_shares * div * tax_multiplier) / p
                    
                tri_dates.append(d)
                tri_vals.append(current_tri_shares * p)
                
            df_tri = pd.DataFrame({"TRI": tri_vals}, index=tri_dates)
            df_tri['Year'] = df_tri.index.year
            
            # Den ersten verfügbaren Wert jedes Jahres holen
            yearly_start_vals = df_tri.groupby('Year').first()['TRI']
            
            rolling_data = []
            unique_years = sorted(df_tri['Year'].unique())
            
            for y in unique_years:
                target_y = y + 10 # Wir prüfen auf exakt 10 Jahre Abstand (z.B. Start 2005 -> Start 2015)
                
                if target_y in unique_years:
                    val_start = yearly_start_vals[y]
                    val_end = yearly_start_vals[target_y]
                    
                    if val_start > 0:
                        total_ret = (val_end / val_start) - 1
                        cagr = ((val_end / val_start) ** (1/10)) - 1
                        
                        rolling_data.append({
                            "Zeitraum": f"{y} bis {target_y}",
                            "Gesamtrendite": total_ret * 100,
                            "Rendite p.a. (CAGR)": cagr * 100
                        })
                    
            if rolling_data:
                df_rolling = pd.DataFrame(rolling_data)
                st.dataframe(
                    df_rolling.style.format({
                        "Gesamtrendite": "{:+.2f} %",
                        "Rendite p.a. (CAGR)": "{:+.2f} %"
                    }),
                    width="stretch",
                    hide_index=True
                )
            else:
                st.info("Die gewählte Historie ist zu kurz. Für diese Auswertung werden mindestens 10 zusammenhängende Jahre benötigt.")
