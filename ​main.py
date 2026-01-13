import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip", layout="wide")

# Türkçe tarih ayarı için yardımcı sözlük
TR_AYLAR = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
            7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}

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

# CSS: Metrik boyutları ve görsel düzenleme
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    [data-testid="stMetricLabel"] { font-size: 14px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        return 0.0, 0.0
    except: return 0.0, 0.0

# --- ANA SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe"])

# --- SEKME 1: PORTFÖY ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'])
        for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        df_p = df_p.sort_values('tarih')
        
        guncel = df_p.iloc[-1]
        onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel

        st.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f}".replace(",", "."), 
                  f"{int(guncel['Toplam'] - onceki['Toplam']):,.0f}")
        
        varlik_listesi = []
        for e in enstrumanlar:
            if guncel[e] > 0:
                degisim = guncel[e] - onceki[e]
                yuzde = (degisim / onceki[e] * 100) if onceki[e] > 0 else 0
                varlik_listesi.append({'Cins': e, 'Tutar': guncel[e], 'Degisim': degisim, 'Yuzde': yuzde, 'Icon': enstruman_bilgi[e]})
        
        df_sirali = pd.DataFrame(varlik_listesi).sort_values(by='Tutar', ascending=False)
        cols = st.columns(4)
        for i, row in enumerate(df_sirali.itertuples()):
            with cols[i % 4]:
                st.metric(f"{row.Icon} {row.Cins}", f"{int(row.Tutar):,.0f}".replace(",", "."), f"%{row.Yuzde:.2f}")

        st.divider()
        sub1, sub2 = st.tabs(["🥧 Dağılım", "⏱️ Gelişim"])
        with sub1:
            fig = px.pie(df_sirali, values='Tutar', names='Cins', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_traces(textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        with sub2:
            df_p['ay_yil'] = df_p['tarih'].dt.month.map(TR_AYLAR) + " " + df_p['tarih'].dt.year.astype(str)
            fig_l = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Varlık Seyri")
            fig_l.update_layout(xaxis_title="Tarih", yaxis_title="Tutar")
            st.plotly_chart(fig_l, use_container_width=True)

# --- SEKME 2: GELİRLER (GÜNCELLENDİ) ---
with tab_gelir:
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0, value=None)
        p = c2.number_input("Prim & Promosyon", min_value=0, value=None)
        y = c3.number_input("Yatırımlar", min_value=0, value=None)
        if st.form_submit_button("Geliri Kaydet"):
            toplam_gelir = (m or 0) + (p or 0) + (y or 0)
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0, toplam_gelir], value_input_option='RAW')
            st.success("Gelir kaydedildi."); st.rerun()

    data_g = ws_gelir.get_all_records()
    if data_g:
        df_g = pd.DataFrame(data_g)
        df_g['tarih'] = pd.to_datetime(df_g['tarih'])
        # Görseldeki sütun isimleriyle eşleme
        cols_to_fix = ["Maaş", "Prim&Promosyon", "Yatırımlar", "Toplam"]
        for c in cols_to_fix: 
            if c in df_g.columns: df_g[c] = pd.to_numeric(df_g[c], errors='coerce').fillna(0)
        
        st.divider()
        g_sub1, g_sub2 = st.tabs(["🥧 Son Durum", "📈 Gelir Gelişimi"])
        
        with g_sub1:
            son = df_g.iloc[-1]
            st.metric("Son Toplam Gelir", f"{int(son.get('Toplam', 0)):,.0f}".replace(",", "."))
            g_pie = pd.DataFrame({
                'Kalem': ["Maaş", "Prim & Promosyon", "Yatırımlar"],
                'Değer': [son.get("Maaş", 0), son.get("Prim&Promosyon", 0), son.get("Yatırımlar", 0)]
            })
            fig_gp = px.pie(g_pie[g_pie['Değer']>0], values='Değer', names='Kalem', hole=0.4)
            st.plotly_chart(fig_gp, use_container_width=True)
            
        with g_sub2:
            df_g['ay_tr'] = df_g['tarih'].dt.month.map(TR_AYLAR)
            fig_gl = px.line(df_g, x='tarih', y='Toplam', markers=True, title="Aylık Toplam Gelir Seyri")
            fig_gl.update_xaxes(tickformat="%b %Y", title="Ay")
            st.plotly_chart(fig_gl, use_container_width=True)

# --- SEKME 3: GİDERLER ---
with tab_gider:
    kalan, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Kalan Bütçe: **{int(kalan):,.0f}**")
    with st.form("gi_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        genel = c1.number_input("Genel", min_value=0, value=None); market = c2.number_input("Market", min_value=0, value=None); kira = c3.number_input("Kira", min_value=0, value=None)
        if st.form_submit_button("Harcamayı Kaydet"):
            # Basitleştirilmiş örnek: Tüm kalemleri sheets yapına göre buraya ekleyebilirsin
            top_h = (genel or 0) + (market or 0) + (kira or 0)
            ws_gider.append_row([datetime.now().strftime('%Y-%m-%d'), genel or 0, market or 0, kira or 0], value_input_option='RAW')
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, kalan - top_h], value_input_option='RAW')
            st.success("Kaydedildi."); st.rerun()

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    st.subheader("🛡️ Limit Belirle")
    with st.form("b_form"):
        yeni_l = st.number_input("Aylık Limit", min_value=0)
        if st.form_submit_button("Başlat"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_l, yeni_l, 0], value_input_option='RAW')
            st.success("Yeni bütçe dönemi başladı."); st.rerun()
