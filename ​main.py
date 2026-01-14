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

# --- GEMINI AI YAPILANDIRMASI ---
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

# --- CSS Düzenlemeleri ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: bold; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #ddd; }
</style>
""", unsafe_allow_html=True)

# --- VERİ HAZIRLIĞI ---
data_p = ws_portfoy.get_all_records()
enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
enstrumanlar = list(enstruman_bilgi.keys())

toplam_tl = 0
guncel = {}
if data_p:
    df_p = pd.DataFrame(data_p)
    df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
    df_p = df_p.dropna(subset=['tarih']).sort_values('tarih')
    for col in enstrumanlar: 
        df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
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
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None) for e in enstrumanlar}
            if st.form_submit_button("🚀 Kaydet"):
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + [p_in[e] if p_in[e] is not None else float(guncel.get(e, 0)) for e in enstrumanlar]
                ws_portfoy.append_row(yeni_satir, value_input_option='RAW')
                st.rerun()

    st.metric("Toplam Varlık", f"{int(toplam_tl):,.0f} TL".replace(",", "."))

    if data_p and len(df_p) > 1:
        st.write("### ⏱️ Değişim Analizi")
        onceki_toplam = float(df_p.iloc[-2]['Toplam'])
        fark = toplam_tl - onceki_toplam
        yuzde = (fark / onceki_toplam) * 100 if onceki_toplam > 0 else 0
        st.metric("Son Güncellemeden Beri", f"{int(fark):,.0f} TL".replace(",", "."), delta=f"{yuzde:.2f}%")

    st.divider()
    cols = st.columns(4)
    for i, e in enumerate(enstrumanlar):
        deger = guncel.get(e, 0)
        if deger > 0:
            cols[i % 4].metric(f"{enstruman_bilgi[e]} {e}", f"{int(deger):,.0f}".replace(",", "."))

# --- SEKME 5: AI ANALİST ---
with tab_ai:
    st.header("🤖 AI Stratejik Danışman")
    kalan, limit = get_son_bakiye_ve_limit()
    
    if st.button("📊 Verilerimi ve Makaleleri Analiz Et"):
        # Sheets'ten makale/eğitim verilerini çek (A sütunu, A1 başlık hariç)
        try:
            # A sütununu al ve boş olmayanları birleştir
            raw_notlar = ws_ai_kaynak.col_values(1)[1:]
            makale_notlari = " ".join([str(n) for n in raw_notlar if n])
        except Exception as e:
            makale_notlari = "Finansal risk yönetimi ve portföy çeşitlendirmesi."

        with st.spinner("Yapay zeka derin analiz yapıyor..."):
            try:
                # Modeli tanımla (Başına models/ ekleyerek)
                model = genai.GenerativeModel(
                    model_name='models/gemini-1.5-flash',
                    system_instruction=f"Sen Düzey 3 finans uzmanısın. Şu kaynak bilgilere sahipsin: {makale_notlari}. Kullanıcının verilerini bu bilgiler ışığında analiz et."
                )
                
                # Veri Özetini Hazırla
                varlik_detay = ", ".join([f"{e}: {int(guncel.get(e,0))} TL" for e in enstrumanlar if guncel.get(e,0) > 0])
                prompt = f"""
                KULLANICI VERİLERİ:
                - Mevcut Portföy: {varlik_detay}
                - Toplam Varlık: {int(toplam_tl)} TL
                - Aylık Kalan Bütçe: {int(kalan)} TL (Limit: {int(limit)} TL)
                
                ANALİZ İSTEĞİ:
                Bu verileri elindeki Düzey 3 finans notlarıyla karşılaştır. 
                1. Portföydeki riskli yoğunlaşmalar var mı?
                2. Gider ve bütçe dengesi stratejik olarak uygun mu?
                3. Makalelerindeki stratejilere göre 3 somut öneri ver.
                """
                
                response = model.generate_content(prompt)
                st.markdown("### 📝 Stratejik Analiz Raporu")
                st.info(response.text)
                st.caption(f"Analiz Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            except Exception as e:
                st.error(f"Analiz sırasında hata oluştu: {e}")

# --- DİĞER SEKMELER (GELİR/GİDER/BÜTÇE) ---
with tab_gelir:
    st.subheader("💰 Gelir Kayıtları")
    # Mevcut gelir kodlarını buraya ekleyebilirsin

with tab_gider:
    st.subheader("💸 Gider Takibi")
    # Mevcut gider kodlarını buraya ekleyebilirsin

with tab_ayrilan:
    st.subheader("🛡️ Bütçe Yönetimi")
    # Mevcut bütçe kodlarını buraya ekleyebilirsin
