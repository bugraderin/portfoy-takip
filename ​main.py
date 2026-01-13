import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy ve Finans Takip", layout="wide")
st.title("💰 Finansal Yönetim Paneli")

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    
    # Tüm Sayfaları Tanımla
    ws_portfoy = spreadsheet.worksheet("Veri Sayfası")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}. Lütfen Sheets sayfa isimlerini kontrol edin.")
    st.stop()

# CSS: Sağdaki artı/eksi oklarını gizleme
st.markdown("""<style> input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; } input[type=number] { -moz-appearance: textfield; } </style>""", unsafe_allow_html=True)

# --- 2. ANA SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy Yönetimi", "💵 Gelirler", "💸 Giderler", "🛡️ Gidere Ayrılan"])

# --- SEKME 1: PORTFÖY YÖNETİMİ (MEVCUT KODUNUZ) ---
with tab_portfoy:
    enstruman_bilgi = {
        'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦',
        'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'
    }
    enstrumanlar = list(enstruman_bilgi.keys())

    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        with st.form("portfoy_formu", clear_on_submit=True):
            p_inputs = {}
            for e in enstrumanlar:
                p_inputs[e] = st.number_input(f"{enstruman_bilgi[e]} {e} (TL)", min_value=0.0, value=None, placeholder="Yazın...", format="%.f")
            p_submit = st.form_submit_button("🚀 Portföyü Kaydet", use_container_width=True)

    if p_submit:
        p_verisi = [p_inputs[e] if p_inputs[e] is not None else 0 for e in enstrumanlar]
        ws_portfoy.append_row([datetime.now().strftime('%Y-%m-%d')] + p_verisi, value_input_option='RAW')
        st.toast("Portföy güncellendi!", icon='✅')
        st.rerun()

    data = ws_portfoy.get_all_records()
    if data:
        df = pd.DataFrame(data)
        df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
        df = df.dropna(subset=['tarih'])
        for col in enstrumanlar:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df['Toplam'] = df[enstrumanlar].sum(axis=1)
        df = df.sort_values('tarih')
        guncel = df.iloc[-1]

        c1, c2, c3 = st.columns(3)
        c1.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."))
        if len(df) > 1:
            degisim = guncel['Toplam'] - df['Toplam'].iloc[-2]
            yuzde_gunluk = (degisim / df['Toplam'].iloc[-2]) * 100
            c2.metric("Günlük Değişim", f"{degisim:,.0f} TL", f"%{yuzde_gunluk:.2f}")
        c3.metric("Kayıt Sayısı", len(df))

        st.divider()
        t1, t2 = st.tabs(["🥧 Dağılım", "📈 Gelişim"])
        with t1:
            raw_plot = [{'Varlık': f"{enstruman_bilgi[e]} {e}", 'Değer': guncel[e]} for e in enstrumanlar if guncel[e] > 0]
            plot_df = pd.DataFrame(raw_plot).sort_values(by='Değer', ascending=False)
            col_l, col_r = st.columns([1.2, 1])
            with col_l:
                fig = px.pie(plot_df, values='Değer', names='Varlık', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=350)
                st.plotly_chart(fig, use_container_width=True)
            with col_r:
                for _, row in plot_df.iterrows():
                    p = (row['Değer'] / guncel['Toplam'])
                    st.write(f"**{row['Varlık']}:** %{p*100:.1f}")
                    st.progress(min(p, 1.0))
        with t2:
            st.line_chart(df.set_index('tarih')['Toplam'])

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Kayıtları")
    gelir_kalemleri = ["Maaş", "Prim&Promosyon", "Yatırımlar"]
    with st.form("gelir_formu", clear_on_submit=True):
        g_inputs = {k: st.number_input(f"{k} (TL)", min_value=0, value=None, placeholder="0", format="%d") for k in gelir_kalemleri}
        g_submit = st.form_submit_button("Geliri Kaydet", use_container_width=True)
    
    if g_submit:
        g_row = [datetime.now().strftime('%Y-%m-%d')] + [g_inputs[k] if g_inputs[k] is not None else 0 for k in gelir_kalemleri]
        ws_gelir.append_row(g_row, value_input_option='RAW')
        st.success("Gelir eklendi!")

# --- SEKME 3: GİDERLER ---
with tab_gider:
    st.subheader("💸 Gider Kayıtları")
    gider_kalemleri = ["Genel Giderler", "Market", "Kira", "Aidat", "Kredi Kartı", "Kredi", "Eğitim", "Araba", "Seyahat", "Sağlık", "Çocuk", "Toplu Taşıma"]
    with st.form("gider_formu", clear_on_submit=True):
        c_g1, c_g2 = st.columns(2)
        gi_inputs = {}
        for i, k in enumerate(gider_kalemleri):
            target = c_g1 if i < 6 else c_g2
            gi_inputs[k] = target.number_input(f"{k} (TL)", min_value=0, value=None, placeholder="0", format="%d")
        gi_submit = st.form_submit_button("Gideri Kaydet", use_container_width=True)
    
    if gi_submit:
        gi_row = [datetime.now().strftime('%Y-%m-%d')] + [gi_inputs[k] if gi_inputs[k] is not None else 0 for k in gider_kalemleri]
        ws_gider.append_row(gi_row, value_input_option='RAW')
        st.success("Gider eklendi!")

# --- SEKME 4: GİDERE AYRILAN TUTAR ---
with tab_ayrilan:
    st.subheader("🛡️ Bütçe Planlama")
    ayrilan_kalemler = ["Ayrılan Tutar", "Kalan", "Devreden"]
    with st.form("ayrilan_formu", clear_on_submit=True):
        a_inputs = {k: st.number_input(f"{k} (TL)", min_value=0, value=None, placeholder="0", format="%d") for k in ayrilan_kalemler}
        a_submit = st.form_submit_button("Bütçeyi Güncelle", use_container_width=True)
    
    if a_submit:
        a_row = [datetime.now().strftime('%Y-%m-%d')] + [a_inputs[k] if a_inputs[k] is not None else 0 for k in ayrilan_kalemler]
        ws_ayrilan.append_row(a_row, value_input_option='RAW')
        st.success("Bütçe verisi güncellendi!")

# Alt kısma ortak bir geçmiş listesi ekleyelim
st.divider()
with st.expander("📄 Tüm Kayıtları Görüntüle"):
    s_secim = st.selectbox("Sayfa seçin:", ["Portföy", "Gelirler", "Giderler", "Bütçe"])
    hedef_ws = {"Portföy": ws_portfoy, "Gelirler": ws_gelir, "Giderler": ws_gider, "Bütçe": ws_ayrilan}[s_secim]
    st.dataframe(pd.DataFrame(hedef_ws.get_all_records()).sort_index(ascending=False), use_container_width=True)
