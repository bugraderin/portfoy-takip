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

# CSS: Metrik boyutlarını küçültür ve formları düzenler
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    [data-testid="stMetricLabel"] { font-size: 14px !important; }
    [data-testid="stMetricDelta"] { font-size: 12px !important; }
    div[data-testid="stMetric"] { background-color: #f0f2f6; padding: 8px; border-radius: 8px; }
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }
    </style>
    """, unsafe_allow_html=True)

# --- YARDIMCI FONKSİYON: GÜNCEL BAKİYE ---
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

        t_fark = guncel['Toplam'] - onceki['Toplam']
        t_yuzde = (t_fark / onceki['Toplam'] * 100) if onceki['Toplam'] > 0 else 0
        st.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."), f"{t_fark:,.0f} TL (%{t_yuzde:.2f})")
        
        varlik_listesi = []
        for e in enstrumanlar:
            if guncel[e] > 0:
                degisim = guncel[e] - onceki[e]
                yuzde = (degisim / onceki[e] * 100) if onceki[e] > 0 else 0
                varlik_listesi.append({'Simge': enstruman_bilgi[e], 'Enstrüman': e, 'Tutar': guncel[e], 'Değişim': degisim, 'Yüzde': yuzde})
        
        df_sirali = pd.DataFrame(varlik_listesi).sort_values(by='Tutar', ascending=False)
        cols = st.columns(4)
        for i, (index, row) in enumerate(df_sirali.iterrows()):
            with cols[i % 4]:
                st.metric(label=f"{row['Simge']} {row['Enstrüman']}", value=f"{int(row['Tutar']):,.0f} TL".replace(",", "."), delta=f"{row['Değişim']:,.0f} TL (%{row['Yüzde']:.2f})")

        st.divider()
        sub_tab_pasta, sub_tab_gelisim = st.tabs(["🥧 Varlık Dağılımı", "⏱️ Performans ve Gelişim"])
        with sub_tab_pasta:
            st.plotly_chart(px.pie(df_sirali, values='Tutar', names='Enstrüman', hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3), use_container_width=True)
        with sub_tab_gelisim:
            periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365}
            secim = st.selectbox("Kıyaslama süresi:", list(periyotlar.keys()), index=1)
            h_tarih = datetime.now() - timedelta(days=periyotlar[secim])
            gecmis_df = df_p[df_p['tarih'] <= h_tarih]
            baslangic = gecmis_df.iloc[-1] if not gecmis_df.empty else df_p.iloc[0]
            p_yuzde = ((guncel['Toplam'] - baslangic['Toplam']) / baslangic['Toplam'] * 100) if baslangic['Toplam'] > 0 else 0
            st.success(f"Değişim: %{p_yuzde:.2f}")
            st.plotly_chart(px.line(df_p, x='tarih', y='Toplam', markers=True), use_container_width=True)

# --- SEKME 2: GELİRLER (GÜNCELLENDİ) ---
with tab_gelir:
    st.subheader("💵 Gelir Girişi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0, value=None)
        p = c2.number_input("Prim", min_value=0, value=None)
        y = c3.number_input("Yatırım", min_value=0, value=None)
        if st.form_submit_button("Geliri Kaydet"):
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0], value_input_option='RAW')
            st.success("Gelir eklendi.")
            st.rerun()

    st.divider()
    st.subheader("🥧 Gelir Dağılımı")
    data_gelir = ws_gelir.get_all_records()
    if data_gelir:
        df_g_list = pd.DataFrame(data_gelir)
        for col in ["Maaş", "Prim", "Yatırım"]:
            if col in df_g_list.columns: df_g_list[col] = pd.to_numeric(df_g_list[col], errors='coerce').fillna(0)
        
        # Sadece son girilen kaydı görselleştir (Aylık durum için en günceli)
        son_gelir = df_g_list.iloc[-1]
        g_pasta_data = pd.DataFrame({
            'Kategori': ["Maaş", "Prim", "Yatırım"],
            'Tutar': [son_gelir["Maaş"], son_gelir["Prim"], son_gelir["Yatırım"]]
        })
        g_pasta_data = g_pasta_data[g_pasta_data['Tutar'] > 0]
        
        if not g_pasta_data.empty:
            st.plotly_chart(px.pie(g_pasta_data, values='Tutar', names='Kategori', hole=0.4, title="Son Kaydedilen Gelir Dağılımı"), use_container_width=True)
        else:
            st.info("Görselleştirilecek gelir verisi henüz yok.")

# --- SEKME 3: GİDERLER ---
with tab_gider:
    st.subheader("💸 Gider Girişi")
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{kalan_bakiye:,.0f} TL**")
    with st.form("gi_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3); genel = c1.number_input("Genel Giderler", min_value=0, value=None); market = c2.number_input("Market", min_value=0, value=None); kira = c3.number_input("Kira", min_value=0, value=None)
        c4, c5, c6 = st.columns(3); aidat = c4.number_input("Aidat", min_value=0, value=None); kk = c5.number_input("Kredi Kartı", min_value=0, value=None); kredi = c6.number_input("Kredi", min_value=0, value=None)
        c7, c8, c9 = st.columns(3); egitim = c7.number_input("Eğitim", min_value=0, value=None); araba = c8.number_input("Araba", min_value=0, value=None); seyahat = c9.number_input("Seyahat", min_value=0, value=None)
        c10, c11, c12 = st.columns(3); saglik = c10.number_input("Sağlık", min_value=0, value=None); cocuk = c11.number_input("Çocuk", min_value=0, value=None); ulashim = c12.number_input("Toplu Taşıma", min_value=0, value=None)
        if st.form_submit_button("✅ Harcamayı Kaydet"):
            kalemler = [genel, market, kira, aidat, kk, kredi, egitim, araba, seyahat, saglik, cocuk, ulashim]
            toplam_h = sum([x or 0 for x in kalemler])
            if toplam_h > 0:
                yeni_kalan = kalan_bakiye - toplam_h
                ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + [x or 0 for x in kalemler], value_input_option='RAW')
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan], value_input_option='RAW')
                st.success(f"Kaydedildi. Kalan: {yeni_kalan} TL"); st.rerun()

    st.divider()
    st.subheader("🥧 Harcama Dağılımı")
    data_g = ws_gider.get_all_records()
    if data_g:
        df_g = pd.DataFrame(data_g)
        kategoriler = ["Genel Giderler", "Market", "Kira", "Aidat", "Kredi Kartı", "Kredi", "Eğitim", "Araba", "Seyahat", "Sağlık", "Çocuk", "Toplu Taşıma"]
        for col in kategoriler:
            if col in df_g.columns: df_g[col] = pd.to_numeric(df_g[col], errors='coerce').fillna(0)
        toplamlar = df_g[kategoriler].sum()
        pasta_data = toplamlar[toplamlar > 0].reset_index()
        pasta_data.columns = ['Kategori', 'Tutar']
        st.plotly_chart(px.pie(pasta_data, values='Tutar', names='Kategori', hole=0.4), use_container_width=True)

# --- SEKME 4: BÜTÇE PLANI ---
with tab_ayrilan:
    st.subheader("🛡️ Limit Tanımla")
    with st.form("a_form", clear_on_submit=True):
        y_lim = st.number_input("Yeni Aylık Limit (TL)", min_value=0, value=None)
        if st.form_submit_button("Bütçeyi Başlat"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), y_lim or 0, y_lim or 0], value_input_option='RAW')
            st.success("Bütçe başlatıldı."); st.rerun()
