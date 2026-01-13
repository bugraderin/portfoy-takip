import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip", layout="wide")

TR_AYLAR_KISA = {'Jan': 'Oca', 'Feb': 'Şub', 'Mar': 'Mar', 'Apr': 'Nis', 'May': 'May', 'Jun': 'Haz',
                'Jul': 'Tem', 'Aug': 'Ağu', 'Sep': 'Eyl', 'Oct': 'Eki', 'Nov': 'Kas', 'Dec': 'Ara'}
TR_AYLAR_TAM = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
                7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}

# --- GOOGLE SHEETS ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
spreadsheet = client.open("portfoyum")

ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
ws_gelir = spreadsheet.worksheet("Gelirler")
ws_gider = spreadsheet.worksheet("Giderler")
ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")

def get_son_bakiye_ve_limit():
    data = ws_ayrilan.get_all_records()
    if data:
        son = data[-1]
        return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
    return 0.0, 0.0

# --- 🧠 FİNANSAL AI MOTORU (YENİ) ---
def finansal_ai_tuyolari(df_p, df_g, df_gi, kalan_bakiye):
    mesajlar = []

    if df_p is not None and not df_p.empty:
        guncel = df_p.iloc[-1]
        toplam = guncel.get('Toplam', 0)
        for col in df_p.columns:
            if col not in ['tarih', 'Toplam'] and toplam > 0:
                oran = guncel[col] / toplam
                if oran >= 0.5:
                    mesajlar.append(
                        f"⚠️ Portföyünün %{int(oran*100)}’i **{col}** ağırlıklı. Çeşitlendirme riski olabilir."
                    )

    if df_g is not None and not df_g.empty and df_gi is not None and not df_gi.empty:
        gelir = df_g.iloc[-1].get('Toplam', 0)
        gider = df_gi.iloc[-1].sum()

        if gider > gelir:
            mesajlar.append("❌ Giderlerin gelirini aşmış. Bütçe açığı var.")
        elif gider > gelir * 0.7:
            mesajlar.append("⚠️ Giderlerin gelirin %70’ini aşmış.")
        else:
            mesajlar.append("✅ Gelir–gider dengen sağlıklı.")

    if kalan_bakiye < 0:
        mesajlar.append("🚨 Bütçeni aşmış durumdasın.")
    elif kalan_bakiye < 1000:
        mesajlar.append("⚠️ Kalan bütçen oldukça düşük.")

    if not mesajlar:
        mesajlar.append("✅ Finansal durum stabil görünüyor.")

    return mesajlar

# --- SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan, tab_ai = st.tabs(
    ["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe", "🤖 Finansal Asistan"]
)

# --- PORTFÖY ---
with tab_portfoy:
    enstrumanlar = ['Hisse Senedi', 'Altın', 'Gümüş', 'Fon', 'Döviz', 'Kripto', 'Mevduat', 'BES']

    with st.sidebar:
        with st.form("p_form"):
            p_in = {e: st.number_input(e, min_value=0.0, value=0.0) for e in enstrumanlar}
            if st.form_submit_button("Kaydet"):
                ws_portfoy.append_row(
                    [datetime.now().strftime('%Y-%m-%d')] + list(p_in.values()),
                    value_input_option='RAW'
                )
                st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'])
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        st.metric("Toplam Varlık", f"{int(df_p.iloc[-1]['Toplam']):,}".replace(",", "."))

# --- GELİRLER ---
with tab_gelir:
    with st.form("g_form"):
        m = st.number_input("Maaş", min_value=0, value=0)
        p = st.number_input("Prim", min_value=0, value=0)
        y = st.number_input("Yatırımlar", min_value=0, value=0)
        if st.form_submit_button("Kaydet"):
            ws_gelir.append_row(
                [datetime.now().strftime('%Y-%m-%d'), m, p, y, m+p+y],
                value_input_option='RAW'
            )
            st.rerun()
    df_g = pd.DataFrame(ws_gelir.get_all_records())

# --- GİDERLER ---
with tab_gider:
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"Kalan Bütçe: {int(kalan_bakiye)} TL")

    with st.form("gi_form"):
        g = st.number_input("Genel Gider", min_value=0, value=0)
        if st.form_submit_button("Kaydet"):
            yeni_kalan = kalan_bakiye - g
            ws_gider.append_row([datetime.now().strftime('%Y-%m-%d'), g], value_input_option='RAW')
            ws_ayrilan.append_row(
                [datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan],
                value_input_option='RAW'
            )
            st.rerun()

    df_gi = pd.DataFrame(ws_gider.get_all_records())

# --- BÜTÇE ---
with tab_ayrilan:
    with st.form("b_form"):
        yeni = st.number_input("Yeni Limit", min_value=0)
        if st.form_submit_button("Başlat"):
            ws_ayrilan.append_row(
                [datetime.now().strftime('%Y-%m-%d'), yeni, yeni],
                value_input_option='RAW'
            )
            st.rerun()

# --- 🤖 FİNANSAL ASİSTAN ---
with tab_ai:
    st.subheader("🤖 Finansal Yapay Zekâ Asistanı")

    tuyolar = finansal_ai_tuyolari(
        df_p if 'df_p' in globals() else None,
        df_g if 'df_g' in globals() else None,
        df_gi if 'df_gi' in globals() else None,
        kalan_bakiye if 'kalan_bakiye' in globals() else 0
    )

    for t in tuyolar:
        if "🚨" in t or "❌" in t:
            st.error(t)
        elif "⚠️" in t:
            st.warning(t)
        else:
            st.success(t)
