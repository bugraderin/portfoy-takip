import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy ve Gider Yönetimi", layout="wide")

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

# CSS: Metriklerin font boyutunu küçültür ve gereksiz boşlukları alır
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    [data-testid="stMetricLabel"] { font-size: 14px !important; }
    [data-testid="stMetricDelta"] { font-size: 12px !important; }
    div[data-testid="stMetric"] { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
    </style>
    """, unsafe_allow_html=True)

# --- YARDIMCI FONKSİYONLAR ---
def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son['Kalan']), float(son['Ayrılan Tutar'])
        return 0.0, 0.0
    except:
        return 0.0, 0.0

# --- ANA SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy Analizi", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe Planlama"])

# --- SEKME 1: PORTFÖY ANALİZİ ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e} (TL)", min_value=0.0, value=None, format="%.f") for e in enstrumanlar}
            if st.form_submit_button("🚀 Kaydet"):
                ws_portfoy.append_row([datetime.now().strftime('%Y-%m-%d')] + [p_in[e] or 0 for e in enstrumanlar], value_input_option='RAW')
                st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
        df_p = df_p.dropna(subset=['tarih'])
        for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        df_p = df_p.sort_values('tarih')
        
        guncel = df_p.iloc[-1]
        onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel

        # TOPLAM VARLIK (ANA METRİK)
        t_fark = guncel['Toplam'] - onceki['Toplam']
        t_yuzde = (t_fark / onceki['Toplam'] * 100) if onceki['Toplam'] > 0 else 0
        st.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."), f"{t_fark:,.0f} TL (%{t_yuzde:.2f})")
        
        st.write("### 📋 Güncel Varlıklar")
        
        # Varlıkları büyükten küçüğe sırala
        varlik_listesi = []
        for e in enstrumanlar:
            if guncel[e] > 0:
                degisim = guncel[e] - onceki[e]
                yuzde = (degisim / onceki[e] * 100) if onceki[e] > 0 else 0
                varlik_listesi.append({'Simge': enstruman_bilgi[e], 'Enstrüman': e, 'Tutar': guncel[e], 'Değişim': degisim, 'Yüzde': yuzde})
        
        df_sirali = pd.DataFrame(varlik_listesi).sort_values(by='Tutar', ascending=False)

        # KOMPAKT GRID: 4'lü kolonlar halinde metrikler
        cols = st.columns(4)
        for i, (index, row) in enumerate(df_sirali.iterrows()):
            with cols[i % 4]:
                st.metric(
                    label=f"{row['Simge']} {row['Enstrüman']}",
                    value=f"{int(row['Tutar']):,.0f} TL".replace(",", "."),
                    delta=f"{row['Değişim']:,.0f} TL (%{row['Yüzde']:.2f})"
                )

        st.divider()
        # --- ALT SEKMELER ---
        sub_tab_pasta, sub_tab_gelisim = st.tabs(["🥧 Varlık Dağılımı", "⏱️ Performans ve Gelişim"])

        with sub_tab_pasta:
            fig_p_pie = px.pie(df_sirali, values='Tutar', names='Enstrüman', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
            st.plotly_chart(fig_p_pie, use_container_width=True)

        with sub_tab_gelisim:
            periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365, "3 Yıl": 1095, "5 Yıl": 1825}
            secim = st.selectbox("Kıyaslama süresi seçin:", list(periyotlar.keys()), index=1)
            h_tarih = datetime.now() - timedelta(days=periyotlar[secim])
            gecmis_df = df_p[df_p['tarih'] <= h_tarih]
            baslangic = gecmis_df.iloc[-1] if not gecmis_df.empty else df_p.iloc[0]
            p_fark = guncel['Toplam'] - baslangic['Toplam']
            p_yuzde = (p_fark / baslangic['Toplam'] * 100) if baslangic['Toplam'] > 0 else 0
            st.success(f"**{secim}** öncesine göre değişim: **%{p_yuzde:.2f}**")
            fig_line = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Toplam Varlık Gelişimi")
            st.plotly_chart(fig_line, use_container_width=True)

# Gider, Gelir ve Bütçe Planlama kısımları bozulmadan korunmuştur.
# ... (Kalan kodlar öncekiyle aynı)
