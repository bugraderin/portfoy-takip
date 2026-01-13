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

# CSS: Spin buttonları gizle ve tablo fontunu küçült
st.markdown("""
    <style> 
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; } 
    input[type=number] { -moz-appearance: textfield; }
    .small-font { font-size:14px !important; }
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

        # 1. ÜST ÖZET (Büyük Metrik)
        t_fark = guncel['Toplam'] - onceki['Toplam']
        t_yuzde = (t_fark / onceki['Toplam'] * 100) if onceki['Toplam'] > 0 else 0
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."), f"{t_fark:,.0f} TL (%{t_yuzde:.2f})")

        # 2. KOMPAKT VARLIK TABLOSU (Sıralı)
        varlik_data = []
        for e in enstrumanlar:
            if guncel[e] > 0:
                degisim = guncel[e] - onceki[e]
                yuzde = (degisim / onceki[e] * 100) if onceki[e] > 0 else 0
                varlik_data.append({
                    "Varlık": f"{enstruman_bilgi[e]} {e}",
                    "Tutar (TL)": guncel[e],
                    "Günlük Değişim": degisim,
                    "Değişim %": yuzde
                })
        
        df_v = pd.DataFrame(varlik_data).sort_values(by="Tutar (TL)", ascending=False)
        
        # Tabloyu Formatla
        with c2:
            st.write("### 📋 Güncel Durum")
            st.dataframe(
                df_v.style.format({
                    "Tutar (TL)": "{:,.0f}",
                    "Günlük Değişim": "{:+,.0f}",
                    "Değişim %": "{:+.2f}%"
                }),
                hide_index=True,
                use_container_width=True
            )

        st.divider()

        # --- ALT SEKMELER ---
        sub_tab_pasta, sub_tab_gelisim = st.tabs(["🥧 Varlık Dağılımı", "⏱️ Performans ve Gelişim"])

        with sub_tab_pasta:
            fig_p_pie = px.pie(df_v, values='Tutar (TL)', names='Varlık', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
            st.plotly_chart(fig_p_pie, use_container_width=True)

        with sub_tab_gelisim:
            periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365, "3 Yıl": 1095, "5 Yıl": 1825}
            secim = st.selectbox("Kıyaslama süresi seçin:", list(periyotlar.keys()), index=1)
            
            h_tarih = datetime.now() - timedelta(days=periyotlar[secim])
            gecmis_df = df_p[df_p['tarih'] <= h_tarih]
            baslangic = gecmis_df.iloc[-1] if not gecmis_df.empty else df_p.iloc[0]
            
            p_fark = guncel['Toplam'] - baslangic['Toplam']
            p_yuzde = (p_fark / baslangic['Toplam'] * 100) if baslangic['Toplam'] > 0 else 0
            st.success(f"**{secim}** öncesine göre toplam değişim: **%{p_yuzde:.2f}**")

            fig_line = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Toplam Varlık Gelişimi")
            st.plotly_chart(fig_line, use_container_width=True)

# --- SEKME 3, 2, 4 (Aynı şekilde korunmuştur) ---
# ... (Gider, Gelir ve Bütçe Planlama kodları önceki ile birebir aynıdır)
