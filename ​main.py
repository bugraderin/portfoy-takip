import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import google.generativeai as genai

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip & AI Danışman", layout="wide")

# --- 1. GOOGLE SHEETS & AI BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
    ws_ai_kaynak = spreadsheet.worksheet("AI")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()

# --- AI YAPILANDIRMASI ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("⚠️ GEMINI_API_KEY bulunamadı.")

# --- FONKSİYONLAR ---
def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        return 0.0, 0.0
    except: return 0.0, 0.0

# --- VERİ ÇEKME VE HAZIRLIK ---
data_p = ws_portfoy.get_all_records()
enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
enstrumanlar = list(enstruman_bilgi.keys())

toplam_tl = 0
guncel = {e: 0 for e in enstrumanlar}
if data_p:
    df_p = pd.DataFrame(data_p)
    df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
    df_p = df_p.dropna(subset=['tarih']).sort_values('tarih')
    for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
    df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
    guncel = df_p.iloc[-1]
    toplam_tl = guncel['Toplam']

# --- SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_ai = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🤖 AI Analist"])

# --- SEKME 1: PORTFÖY ---
with tab_portfoy:
    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=float(guncel.get(e, 0))) for e in enstrumanlar}
            if st.form_submit_button("🚀 Kaydet"):
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + [p_in[e] for e in enstrumanlar]
                ws_portfoy.append_row(yeni_satir, value_input_option='RAW')
                st.rerun()

    st.metric("Toplam Varlık", f"{int(toplam_tl):,.0f} TL".replace(",", "."))
    
    if data_p and len(df_p) > 0:
        fig = px.pie(values=[guncel[e] for e in enstrumanlar if guncel[e] > 0], 
                     names=[e for e in enstrumanlar if guncel[e] > 0], title="Varlık Dağılımı")
        st.plotly_chart(fig)

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Ekle")
    with st.form("gelir_form"):
        g_tar = st.date_input("Tarih", datetime.now())
        g_kat = st.selectbox("Kategori", ["Maaş", "Kira", "Faiz", "Ek Gelir", "Diğer"])
        g_tut = st.number_input("Tutar", min_value=0.0)
        if st.form_submit_button("Gelir Kaydet"):
            ws_gelir.append_row([str(g_tar), g_kat, g_tut], value_input_option='RAW')
            st.success("Gelir eklendi!")

# --- SEKME 3: GİDERLER ---
with tab_gider:
    st.subheader("💸 Gider Ekle")
    with st.form("gider_form"):
        gi_tar = st.date_input("Tarih", datetime.now())
        gi_kat = st.selectbox("Kategori", ["Market", "Fatura", "Kira", "Ulaşım", "Eğlence", "Diğer"])
        gi_tut = st.number_input("Tutar", min_value=0.0)
        if st.form_submit_button("Gider Kaydet"):
            ws_gider.append_row([str(gi_tar), gi_kat, gi_tut], value_input_option='RAW')
            st.success("Gider eklendi!")

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    st.subheader("🛡️ Gidere Ayrılan Tutar")
    kalan, limit = get_son_bakiye_ve_limit()
    st.metric("Mevcut Bütçe Limiti", f"{limit:,.0f} TL")
    with st.form("butce_form"):
        yeni_limit = st.number_input("Yeni Bütçe Belirle", min_value=0.0)
        if st.form_submit_button("Bütçeyi Güncelle"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_limit, yeni_limit], value_input_option='RAW')
            st.rerun()

# --- SEKME 5: AI ANALİST ---
with tab_ai:
    st.header("🤖 AI Stratejik Danışman")
    if st.button("📊 Portföyümü ve Notlarımı Analiz Et"):
        try:
            raw_notlar = ws_ai_kaynak.col_values(1)[1:]
            makale_notlari = " ".join([str(n) for n in raw_notlar if n])
            
            model = genai.GenerativeModel(
                model_name='models/gemini-1.5-flash',
                system_instruction=f"Sen Düzey 3 finans uzmanısın. Şu kaynak bilgilere sahipsin: {makale_notlari}."
            )
            
            varlik_detay = ", ".join([f"{e}: {int(guncel.get(e,0))} TL" for e in enstrumanlar if guncel.get(e,0) > 0])
            prompt = f"Varlıklar: {varlik_detay}. Toplam: {int(toplam_tl)} TL. Kalan Bütçe: {int(kalan)} TL. Analiz yap."
            
            response = model.generate_content(prompt)
            st.markdown("### 📝 AI Analiz Raporu")
            st.info(response.text)
        except Exception as e:
            st.error(f"AI Analiz Hatası: {e}")
