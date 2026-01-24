import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip", layout="wide")

# Türkçe Ay Sözlükleri
TR_AYLAR_KISA = {'Jan': 'Oca', 'Feb': 'Şub', 'Mar': 'Mar', 'Apr': 'Nis', 'May': 'May', 'Jun': 'Haz',
                'Jul': 'Tem', 'Aug': 'Ağu', 'Sep': 'Eyl', 'Oct': 'Eki', 'Nov': 'Kas', 'Dec': 'Ara'}

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    # Senin orijinal sayfaların
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
    
    # Yeni fon sayfaların
    ws_fon_listesi = spreadsheet.worksheet("Fon_Listesi")
    ws_veri_giris = spreadsheet.worksheet("Veri_Giris")
    ws_tefas_fiyat = spreadsheet.worksheet("TefasFonVerileri")
    ws_befas_fiyat = spreadsheet.worksheet("BefasFonVerileri")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# --- 2. CSS ---
st.markdown("""<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
</style>""", unsafe_allow_html=True)

def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        return 0.0, 0.0
    except: return 0.0, 0.0

# --- 3. SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_v2 = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🚀 Portföy V2"])

# --- SEKME 1: PORTFÖY (Orijinal Kodun) ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())
    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        try:
            data_sidebar = ws_portfoy.get_all_records()
            son_kayitlar = pd.DataFrame(data_sidebar).iloc[-1] if data_sidebar else {e: 0.0 for e in enstrumanlar}
        except: son_kayitlar = {e: 0.0 for e in enstrumanlar}
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f") for e in enstrumanlar}
            if st.form_submit_button("🚀 Kaydet"):
                yeni = [datetime.now().strftime('%Y-%m-%d')] + [p_in[e] if p_in[e] is not None else float(son_kayitlar.get(e, 0)) for e in enstrumanlar]
                ws_portfoy.append_row(yeni); st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p.columns = [c.strip() for c in df_p.columns] # Sütunları temizle ki DuplicateError vermesin
        df_p['tarih'] = pd.to_datetime(df_p['tarih'])
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        st.metric("Toplam Varlık (TL)", f"{int(df_p.iloc[-1]['Toplam']):,.0f}")
        st.plotly_chart(px.line(df_p, x='tarih', y='Toplam'), use_container_width=True)

# --- SEKME 2 & 3 & 4 (Orijinal Kodun) ---
with tab_gelir:
    with st.form("g_form"):
        m = st.number_input("Maaş"); p = st.number_input("Prim"); y = st.number_input("Yatırım")
        if st.form_submit_button("Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m, p, y, m+p+y]); st.rerun()

with tab_gider:
    kb, lim = get_son_bakiye_ve_limit()
    st.info(f"💰 Bütçe: {kb:,.0f} TL")
    with st.form("gi_form"):
        g_ad = st.text_input("Gider"); g_t = st.number_input("Tutar")
        if st.form_submit_button("Kaydet"):
            ws_gider.append_row([datetime.now().strftime('%Y-%m-%d'), g_ad, g_t])
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), lim, kb-g_t]); st.rerun()

with tab_ayrilan:
    kb, _ = get_son_bakiye_ve_limit()
    ekle = st.number_input("Tutar")
    if st.button("Ekle"):
        ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), ekle, kb+ekle]); st.rerun()

# --- SEKME 5: PORTFÖY V2 (Yeni Eklenen) ---
with tab_v2:
    st.header("🚀 Fon Portföyü")
    try:
        df_list = pd.DataFrame(ws_fon_listesi.get_all_records())
        f_sec = st.selectbox("Fon Seç:", [f"{r['Fon Kodu']} - {r['Fon Adı']}" for _, r in df_list.iterrows()], index=None)
        if f_sec:
            kod = f_sec.split(" - ")[0]
            src = st.radio("Kaynak:", ["Tefas", "Befas"])
            lot = st.number_input("Lot:", min_value=0.0)
            ws_f = ws_tefas_fiyat if src == "Tefas" else ws_befas_fiyat
            f_df = pd.DataFrame(ws_f.get_all_records())
            f_row = f_df[f_df['Fon Kodu'] == kod]
            if not f_row.empty:
                fiyat = float(f_row.iloc[0]['Son Fiyat'])
                st.write(f"Değer: {lot*fiyat:,.2f} TL")
                if st.button("Portföyüme Ekle"):
                    ws_veri_giris.append_row([datetime.now().strftime("%Y-%m-%d"), kod, f_sec.split(" - ")[1], lot, fiyat, lot*fiyat, src])
                    st.success("Eklendi!"); st.rerun()
        st.divider()
        st.dataframe(pd.DataFrame(ws_veri_giris.get_all_records()), use_container_width=True)
    except Exception as e: st.write("Veri bekleniyor...")
