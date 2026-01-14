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
    # Google Sheets Bağlantısı
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
    ws_ai_kaynak = spreadsheet.worksheet("AI")
except Exception as e:
    st.error(f"Google Sheets Bağlantı Hatası: {e}")
    st.stop()

# --- GEMINI AI YAPILANDIRMASI (Try Bloğundan Sonra) ---
if "GEMINI_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    except Exception as e:
        st.error(f"AI Yapılandırma Hatası: {e}")
else:
    st.warning("⚠️ GEMINI_API_KEY bulunamadı. Lütfen Secrets ayarlarına ekleyin.")

# --- FONKSİYONLAR ---
def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        return 0.0, 0.0
    except: return 0.0, 0.0

# --- CSS Düzenlemeleri (Renk ve Görünüm) ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: bold; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #ddd; }
</style>
""", unsafe_allow_html=True)

# Türkçe Ay Sözlükleri
TR_AYLAR_KISA = {'Jan': 'Oca', 'Feb': 'Şub', 'Mar': 'Mar', 'Apr': 'Nis', 'May': 'May', 'Jun': 'Haz',
                'Jul': 'Tem', 'Aug': 'Ağu', 'Sep': 'Eyl', 'Oct': 'Eki', 'Nov': 'Kas', 'Dec': 'Ara'}
TR_AYLAR_TAM = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
                7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}

# --- SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_ai = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🤖 AI Analist"])

# --- VERİ HAZIRLIĞI ---
data_p = ws_portfoy.get_all_records()
enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
enstrumanlar = list(enstruman_bilgi.keys())

if data_p:
    df_p = pd.DataFrame(data_p)
    df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
    df_p = df_p.dropna(subset=['tarih']).sort_values('tarih')
    for col in enstrumanlar: df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
    df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
    guncel = df_p.iloc[-1]
    toplam_tl = guncel['Toplam']

# --- SEKME 1: PORTFÖY ---
with tab_portfoy:
    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        # Sidebar form kodları (Kısaltıldı, eski kodunla aynı mantık)
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None) for e in enstrumanlar}
            if st.form_submit_button("🚀 Kaydet"):
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + [p_in[e] if p_in[e] is not None else float(guncel[e]) for e in enstrumanlar]
                ws_portfoy.append_row(yeni_satir, value_input_option='RAW')
                st.rerun()

    st.metric("Toplam Varlık", f"{int(toplam_tl):,.0f} TL".replace(",", "."))

    # Değişim Analizi
    st.write("### ⏱️ Değişim Analizi")
    periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "1 Yıl": 365}
    secilen_p = st.selectbox("Periyot", list(periyotlar.keys()))
    
    if len(df_p) > 1:
        hedef_tarih = guncel['tarih'] - timedelta(days=periyotlar[secilen_p])
        baz_deger = float(df_p.iloc[-2]['Toplam']) if secilen_p == "1 Gün" else float(df_p[df_p['tarih'] > hedef_tarih]['Toplam'].mean())
        fark = toplam_tl - baz_deger
        yuzde = (fark / baz_deger) * 100 if baz_deger > 0 else 0
        st.metric(f"{secilen_p} Değişimi", f"{int(fark):,.0f} TL".replace(",", "."), delta=f"{yuzde:.2f}%")

    st.divider()
    # Enstrümanlar
    onceki = df_p.iloc[-2] if len(df_p) > 1 else guncel
    cols = st.columns(4)
    varlik_listesi = []
    for i, e in enumerate(enstrumanlar):
        if guncel[e] > 0:
            degisim = ((guncel[e] - onceki[e]) / onceki[e] * 100) if onceki[e] > 0 else 0
            cols[i % 4].metric(f"{enstruman_bilgi[e]} {e}", f"{int(guncel[e]):,.0f}".replace(",", "."), delta=f"{degisim:.2f}%")
            varlik_listesi.append({'Cins': e, 'Tutar': guncel[e]})

# --- SEKME 5: AI ANALİST ---
with tab_ai:
    st.header("🤖 AI Stratejik Danışman")
    kalan, limit = get_son_bakiye_ve_limit()
    
    # Sheets'ten makale verilerini çek
    try:
        makale_notlari = " ".join(ws_ai_kaynak.col_values(1)[1:]) # Başlık hariç tüm A sütunu
    except:
        makale_notlari = "Finansal genel bilgiler."

    if st.button("📊 Verilerimi ve Makaleleri Harmanla"):
        with st.spinner("Yapay zeka derin analiz yapıyor..."):
            # Dinamik Sistem Talimatı
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=f"Sen Düzey 3 finans uzmanısın. Şu bilgilere sahipsin: {makale_notlari}. Kullanıcının verilerini bu uzmanlıkla yorumla."
            )
            
            varlik_metni = ", ".join([f"{v['Cins']}: {int(v['Tutar'])} TL" for v in varlik_listesi])
            prompt = f"""
            GÜNCEL VERİLER:
            - Portföy: {varlik_metni}
            - Toplam: {int(toplam_tl)} TL
            - Kalan Aylık Bütçe: {int(kalan)} TL / {int(limit)} TL
            
            GÖREV: Bu verileri makale bilgilerine dayanarak analiz et. Riskleri ve yapılması gereken 3 stratejik hamleyi söyle.
            """
            
            response = model.generate_content(prompt)
            st.markdown("### 📝 Stratejik Analiz Notları")
            st.info(response.text)

# --- GELİR/GİDER/BÜTÇE (Mevcut kodların devamı...) ---
# (Bu kısımları bozmadan kendi dosyanın sonundaki gibi bırakabilirsin)
