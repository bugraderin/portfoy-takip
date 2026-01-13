import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Yönetim", layout="wide")
st.title("🚀 Akıllı Portföy ve Gider Takibi")

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

# CSS: Artı/Eksi oklarını gizleme
st.markdown("""<style> input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; } input[type=number] { -moz-appearance: textfield; } </style>""", unsafe_allow_html=True)

# --- YARDIMCI FONKSİYONLAR ---
def get_son_butce_durumu():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son['Kalan']), float(son['Ayrılan Tutar'])
        return 0.0, 0.0
    except:
        return 0.0, 0.0

# --- 2. ANA SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy Analizi", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe Planlama"])

# --- SEKME 1: PORTFÖY ---
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

        c1, c2, c3 = st.columns(3)
        c1.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."))
        if len(df_p) > 1:
            deg = guncel['Toplam'] - df_p['Toplam'].iloc[-2]
            y_deg = (deg / df_p['Toplam'].iloc[-2]) * 100
            c2.metric("Günlük Değişim", f"{deg:,.0f} TL", f"%{y_deg:.2f}")
        
        st.divider()
        st.subheader("⏱️ Dönemsel Performans")
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "9 Ay": 270, "1 Yıl": 365, "3 Yıl": 1095, "5 Yıl": 1825}
        secim = st.selectbox("Kıyaslama süresi:", list(periyotlar.keys()))
        
        h_tarih = datetime.now() - timedelta(days=periyotlar[secim])
        gecmis_df = df_p[df_p['tarih'] <= h_tarih]
        baslangic = gecmis_df.iloc[-1] if not gecmis_df.empty else df_p.iloc[0]
        
        t_fark = guncel['Toplam'] - baslangic['Toplam']
        b_yuzde = (t_fark / baslangic['Toplam'] * 100) if baslangic['Toplam'] > 0 else 0
        st.success(f"**{secim}** öncesine göre büyüme: **%{b_yuzde:.2f}** ({t_fark:,.0f} TL fark)")

        t_da, t_ge = st.tabs(["🥧 Varlık Dağılımı", "📈 Gelişim Grafiği"])
        with t_da:
            plot_df = pd.DataFrame([{'V': f"{enstruman_bilgi[e]} {e}", 'D': guncel[e]} for e in enstrumanlar if guncel[e] > 0]).sort_values('D', ascending=False)
            fig_pie = px.pie(plot_df, values='D', names='V', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
        with t_ge:
            fig_line = px.line(df_p, x='tarih', y='Toplam', markers=True)
            st.plotly_chart(fig_line, use_container_width=True)

# --- SEKME 3: GİDERLER (İSTEDİĞİN TÜMLEŞİK YAPI) ---
with tab_gider:
    st.subheader("💸 Gider Kaydı")
    kalan_bakiye, limit = get_son_butce_durumu()
    st.info(f"💰 Kalan Bütçeniz: **{kalan_bakiye:,.0f} TL**")
    
    with st.form("gi_form", clear_on_submit=True):
        # 1. GRUP: ÖZEL SEÇİMLİ GİDERLER
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 📦 Genel")
            genel_tip = st.selectbox("Tür Seçin", ["Sigara", "Kozmetik", "Kırtasiye", "Evcil Hayvan", "Giyim", "Eğlence", "Diğer"], key="genel_s")
            genel_tutar = st.number_input(f"{genel_tip} Tutarı", min_value=0, value=None, format="%d")

        with col2:
            st.markdown("### 🚗 Araba")
            araba_tip = st.selectbox("Tür Seçin", ["Benzin", "Bakım", "Diğer"], key="araba_s")
            araba_tutar = st.number_input(f"{araba_tip} Tutarı", min_value=0, value=None, format="%d")

        with col3:
            st.markdown("### 🏦 Kredi")
            kredi_tip = st.selectbox("Tür Seçin", ["Banka Kredisi", "Öğrenim Kredisi", "Diğer"], key="kredi_s")
            kredi_tutar = st.number_input(f"{kredi_tip} Tutarı", min_value=0, value=None, format="%d")

        st.divider()
        
        # 2. GRUP: DİĞER SABİT GİDERLER
        st.markdown("### 🏠 Diğer Harcamalar")
        c4, c5, c6, c7 = st.columns(4)
        market = c4.number_input("Market", min_value=0, value=None)
        kira = c5.number_input("Kira", min_value=0, value=None)
        aidat = c6.number_input("Aidat", min_value=0, value=None)
        kk = c7.number_input("Kredi Kartı", min_value=0, value=None)
        
        c8, c9, c10, c11 = st.columns(4)
        egitim = c8.number_input("Eğitim", min_value=0, value=None)
        seyahat = c9.number_input("Seyahat", min_value=0, value=None)
        saglik = c10.number_input("Sağlık", min_value=0, value=None)
        cocuk = c11.number_input("Çocuk", min_value=0, value=None)
        ulashim = c4.number_input("Toplu Taşıma", min_value=0, value=None)

        if st.form_submit_button("✅ Harcamayı Kaydet ve Bütçeden Düş"):
            liste = [genel_tutar, market, kira, aidat, kk, kredi_tutar, egitim, araba_tutar, seyahat, saglik, cocuk, ulashim]
            toplam_h = sum([x or 0 for x in liste])
            yeni_kalan = kalan_bakiye - toplam_h
            
            not_metni = f"Genel:{genel_tip}, Araba:{araba_tip}, Kredi:{kredi_tip}"
            
            # Giderler Sayfasına Kayıt
            gi_row = [datetime.now().strftime('%Y-%m-%d')] + [x or 0 for x in liste] + [not_metni]
            ws_gider.append_row(gi_row, value_input_option='RAW')
            
            # Bütçe Sayfasına Kayıt (Devreden = Eski Kalan)
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan, kalan_bakiye], value_input_option='RAW')
            
            st.success(f"İşlem Başarılı! Kalan: {yeni_kalan} TL")
            st.rerun()

# --- SEKME 4: BÜTÇE PLANI ---
with tab_ayrilan:
    st.subheader("🛡️ Limit Tanımla")
    with st.form("a_form", clear_on_submit=True):
        y_lim = st.number_input("Aylık Limit", min_value=0, value=None)
        ek_devir = st.number_input("Ekstra Devreden", min_value=0, value=None)
        if st.form_submit_button("Bütçeyi Başlat"):
            total = (y_lim or 0) + (ek_devir or 0)
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), y_lim or 0, total, ek_devir or 0], value_input_option='RAW')
            st.rerun()

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Girişi")
    with st.form("g_form", clear_on_submit=True):
        m = st.number_input("Maaş", min_value=0, value=None)
        p = st.number_input("Prim", min_value=0, value=None)
        y = st.number_input("Yatırım", min_value=0, value=None)
        if st.form_submit_button("Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0], value_input_option='RAW')
            st.success("Gelir eklendi.")
