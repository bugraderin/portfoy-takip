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
TR_AYLAR_TAM = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
                7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}

# --- GOOGLE SHEETS BAĞLANTISI ---
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

# --- CSS ---
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 18px !important; }
div[data-testid="stMetric"] {
    background-color: #f8f9fa;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #eee;
}
</style>
""", unsafe_allow_html=True)

def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        return 0.0, 0.0
    except:
        return 0.0, 0.0

# --- PORTFÖY AI YORUM FONKSİYONU (SADECE PORTFÖY) ---
def portfoy_ai_yorumu(df_p):
    if df_p is None or df_p.empty:
        return ["📭 Portföyün boş görünüyor. Küçük tutarlarla başlayarak çeşitlendirme yapabilirsin."]

    if "Toplam" not in df_p.columns:
        return ["⚠️ Portföy verisi okunamadı."]

    guncel = df_p.iloc[-1]
    toplam = guncel["Toplam"]

    if toplam <= 0:
        return ["⚠️ Portföyünde varlık var ancak toplam değer sıfıra yakın."]

    enstrumanlar = [c for c in df_p.columns if c not in ["tarih", "Toplam"]]
    dagilim = {e: guncel[e] for e in enstrumanlar if guncel[e] > 0}

    if not dagilim:
        return ["📭 Portföyün boş görünüyor."]

    en_buyuk = max(dagilim, key=dagilim.get)
    oran = (dagilim[en_buyuk] / toplam) * 100

    tuyolar = []
    if oran > 70:
        tuyolar.append(f"🚨 Portföyünün %{oran:.0f}’i **{en_buyuk}** ağırlıklı. Bu yüksek risk oluşturabilir.")
    elif oran > 40:
        tuyolar.append(f"⚠️ **{en_buyuk}** portföyde baskın. Dengeli ama takip edilmeli.")
    else:
        tuyolar.append("✅ Portföyün dengeli görünüyor. Risk dağılımı sağlıklı.")

    tuyolar.append("📌 Uzun vadede düzenli ekleme yapmak dalgalanma riskini azaltabilir.")
    return tuyolar

# --- SEKME TANIMLARI ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_ai = st.tabs(
    ["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🤖 AI"]
)

# ================== PORTFÖY SEKME ==================
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦',
                       'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f")
                    for e in enstrumanlar}
            if st.form_submit_button("🚀 Kaydet"):
                ws_portfoy.append_row(
                    [datetime.now().strftime('%Y-%m-%d')] + [p_in[e] or 0 for e in enstrumanlar],
                    value_input_option='RAW'
                )
                st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'], errors='coerce')
        df_p = df_p.dropna(subset=['tarih']).sort_values('tarih')
        for col in enstrumanlar:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0)
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)

        guncel = df_p.iloc[-1]
        toplam_tl = guncel['Toplam']
        st.metric("Toplam Varlık (TL)", f"{int(toplam_tl):,.0f}".replace(",", "."))

# ================== AI SEKME ==================
with tab_ai:
    st.subheader("🤖 Finansal Yapay Zekâ Asistanı")
    st.caption("Sadece portföyüne bakarak oluşturulan basit tüyolar")

    try:
        tuyolar = portfoy_ai_yorumu(df_p if 'df_p' in globals() else None)
        for t in tuyolar:
            if "🚨" in t:
                st.error(t)
            elif "⚠️" in t:
                st.warning(t)
            else:
                st.success(t)
    except:
        st.info("Portföy verisi okunamadı.")
