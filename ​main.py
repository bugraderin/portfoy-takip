import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip", layout="wide")

# Türkçe Ay Sözlüğü
TR_AYLAR = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 
            7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}

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

# CSS: Metrik ve Görsel Düzenleme
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    [data-testid="stMetricLabel"] { font-size: 14px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# --- YARDIMCI FONKSİYONLAR ---
def get_son_bakiye_ve_limit():
    try:
        data = ws_ayrilan.get_all_records()
        if data:
            son = data[-1]
            return float(son.get('Kalan', 0)), float(son.get('Ayrılan Tutar', 0))
        return 0.0, 0.0
    except: return 0.0, 0.0

# --- ANA SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe"])

# --- SEKME 1: PORTFÖY ---
with tab_portfoy:
    enstruman_bilgi = {
        'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 
        'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'
    }
    enstrumanlar = list(enstruman_bilgi.keys())

    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        with st.form("p_form", clear_on_submit=True):
            p_in = {e: st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f") for e in enstrumanlar}
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

        st.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f}".replace(",", "."), f"{int(guncel['Toplam'] - onceki['Toplam']):,.0f}")
        
        varlik_data = []
        for e in enstrumanlar:
            if guncel[e] > 0:
                degisim = guncel[e] - onceki[e]
                yuzde = (degisim / onceki[e] * 100) if onceki[e] > 0 else 0
                varlik_data.append({'Cins': e, 'Tutar': guncel[e], 'Yüzde': yuzde, 'Icon': enstruman_bilgi[e]})
        
        df_v = pd.DataFrame(varlik_data).sort_values(by="Tutar", ascending=False)
        cols = st.columns(4)
        for i, (index, row) in enumerate(df_v.iterrows()):
            with cols[i % 4]:
                st.metric(f"{row['Icon']} {row['Cins']}", f"{int(row['Tutar']):,.0f}".replace(",", "."), f"%{row['Yüzde']:.2f}")

        st.divider()
        sub_tab1, sub_tab2 = st.tabs(["🥧 Varlık Dağılımı", "📈 Gelişim Analizi"])
        with sub_tab1:
            df_v['Etiket'] = df_v['Icon'] + " " + df_v['Cins']
            fig_p = px.pie(df_v, values='Tutar', names='Etiket', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_p, use_container_width=True)
        with sub_tab2:
            df_p['tarih_tr'] = df_p['tarih'].dt.day.astype(str) + " " + df_p['tarih'].dt.month.map(TR_AYLAR)
            fig_l = px.line(df_p, x='tarih', y='Toplam', markers=True, title="Toplam Varlık Seyri", custom_data=['tarih_tr'])
            fig_l.update_traces(hovertemplate="Tarih: %{customdata[0]}<br>Toplam: %{y:,.0f}")
            # Seçim kutusunu (box select) ve diğer araçları kaldır, sadece zoom ve pan kalsın
            fig_l.update_layout(dragmode='pan', modebar_remove=['select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d', 'toImage'])
            st.plotly_chart(fig_l, use_container_width=True)

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0, value=None)
        p = c2.number_input("Prim & Promosyon", min_value=0, value=None)
        y = c3.number_input("Yatırımlar", min_value=0, value=None)
        if st.form_submit_button("Geliri Kaydet"):
            toplam = (m or 0) + (p or 0) + (y or 0)
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m or 0, p or 0, y or 0, toplam], value_input_option='RAW')
            st.success("Kaydedildi."); st.rerun()

    data_g = ws_gelir.get_all_records()
    if data_g:
        df_g = pd.DataFrame(data_g)
        df_g['tarih'] = pd.to_datetime(df_g['tarih'], errors='coerce')
        # Sütun isimlerini görseldeki gibi eşle
        for col in ["Maaş", "Prim&Promosyon", "Yatırımlar", "Toplam"]:
            if col in df_g.columns: df_g[col] = pd.to_numeric(df_g[col], errors='coerce').fillna(0)
        
        g_sub1, g_sub2 = st.tabs(["🥧 Dağılım", "📈 Aylık Seyir"])
        with g_sub1:
            son_g = df_g.iloc[-1]
            g_pie_df = pd.DataFrame({'Kategori': ["Maaş", "Prim & Promosyon", "Yatırımlar"], 'Tutar': [son_g.get("Maaş", 0), son_g.get("Prim&Promosyon", 0), son_g.get("Yatırımlar", 0)]})
            st.plotly_chart(px.pie(g_pie_df[g_pie_df['Tutar']>0], values='Tutar', names='Kategori', hole=0.4), use_container_width=True)
        with g_sub2:
            df_g['tarih_tr'] = df_g['tarih'].dt.month.map(TR_AYLAR) + " " + df_g['tarih'].dt.year.astype(str)
            fig_gl = px.line(df_g, x='tarih', y='Toplam', markers=True, title="Aylık Gelir Gelişimi", custom_data=['tarih_tr'])
            fig_gl.update_traces(hovertemplate="Dönem: %{customdata[0]}<br>Gelir: %{y:,.0f}")
            # Seçim kutusunu (box select) ve diğer araçları kaldır
            fig_gl.update_layout(dragmode='pan', modebar_remove=['select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d', 'toImage'])
            st.plotly_chart(fig_gl, use_container_width=True)

# --- SEKME 3: GİDERLER ---
with tab_gider:
    st.subheader("💸 Gider Yönetimi")
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{int(kalan_bakiye):,.0f}**")
    
    gider_ikonlari = {
        "Genel Giderler": "📦", "Market": "🛒", "Kira": "🏠", "Aidat": "🏢", 
        "Kredi Kartı": "💳", "Kredi": "🏦", "Eğitim": "🎓", "Araba": "🚗", 
        "Seyahat": "✈️", "Sağlık": "🏥", "Çocuk": "👶", "Toplu Taşıma": "🚌"
    }
    
    with st.form("gi_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        genel = c1.number_input(f"{gider_ikonlari['Genel Giderler']} Genel Giderler", min_value=0, value=None)
        market = c2.number_input(f"{gider_ikonlari['Market']} Market", min_value=0, value=None)
        kira = c3.number_input(f"{gider_ikonlari['Kira']} Kira", min_value=0, value=None)
        
        c4, c5, c6 = st.columns(3)
        aidat = c4.number_input(f"{gider_ikonlari['Aidat']} Aidat", min_value=0, value=None)
        kk = c5.number_input(f"{gider_ikonlari['Kredi Kartı']} Kredi Kartı", min_value=0, value=None)
        kredi = c6.number_input(f"{gider_ikonlari['Kredi']} Kredi", min_value=0, value=None)
        
        c7, c8, c9 = st.columns(3)
        egitim = c7.number_input(f"{gider_ikonlari['Eğitim']} Eğitim", min_value=0, value=None)
        araba = c8.number_input(f"{gider_ikonlari['Araba']} Araba", min_value=0, value=None)
        seyahat = c9.number_input(f"{gider_ikonlari['Seyahat']} Seyahat", min_value=0, value=None)
        
        c10, c11, c12 = st.columns(3)
        saglik = c10.number_input(f"{gider_ikonlari['Sağlık']} Sağlık", min_value=0, value=None)
        cocuk = c11.number_input(f"{gider_ikonlari['Çocuk']} Çocuk", min_value=0, value=None)
        ulashim = c12.number_input(f"{gider_ikonlari['Toplu Taşıma']} Toplu Taşıma", min_value=0, value=None)
        
        if st.form_submit_button("✅ Harcamayı Kaydet"):
            kalemler = [genel, market, kira, aidat, kk, kredi, egitim, araba, seyahat, saglik, cocuk, ulashim]
            toplam_h = sum([x or 0 for x in kalemler])
            if toplam_h > 0:
                yeni_kalan = kalan_bakiye - toplam_h
                ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + [x or 0 for x in kalemler], value_input_option='RAW')
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan], value_input_option='RAW')
                st.success(f"Kaydedildi. Kalan: {int(yeni_kalan)}"); st.rerun()

    data_gi = ws_gider.get_all_records()
    if data_gi:
        df_gi = pd.DataFrame(data_gi)
        kats = list(gider_ikonlari.keys())
        for c in kats: 
            if c in df_gi.columns: df_gi[c] = pd.to_numeric(df_gi[c], errors='coerce').fillna(0)
        top_gi = df_gi[kats].sum().reset_index()
        top_gi.columns = ['Kategori', 'Tutar']
        top_gi['Etiket'] = top_gi['Kategori'].map(gider_ikonlari) + " " + top_gi['Kategori']
        st.plotly_chart(px.pie(top_gi[top_gi['Tutar']>0], values='Tutar', names='Etiket', hole=0.4, title="Toplam Gider Dağılımı"), use_container_width=True)

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    st.subheader("🛡️ Limit Tanımla")
    with st.form("b_form"):
        yeni_l = st.number_input("Yeni Aylık Limit", min_value=0)
        if st.form_submit_button("Başlat"):
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_l, yeni_l], value_input_option='RAW')
            st.success("Bütçe güncellendi."); st.rerun()
