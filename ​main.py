import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Finansal Takip", layout="wide")

# Türkçe Ay Sözlükleri
TR_AYLAR_KISA = {'Jan': 'Oca', 'Feb': 'Şub', 'Mar': 'Mar', 'Apr': 'Nis', 'May': 'May', 'Jun': 'Haz', 'Jul': 'Tem', 'Aug': 'Ağu', 'Sep': 'Eyl', 'Oct': 'Eki', 'Nov': 'Kas', 'Dec': 'Ara'}
TR_AYLAR_TAM = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    ws_portfoy = spreadsheet.worksheet("Sayfa5")
    ws_gelir = spreadsheet.worksheet("Gelirler")
    ws_gider = spreadsheet.worksheet("Giderler")
    ws_ayrilan = spreadsheet.worksheet("Gidere Ayrılan Tutar")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}"); st.stop()

# --- CSS Düzenlemeleri ---
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 18px !important; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #eee; }
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

# --- SEKMELER ---
tab_portfoy, tab_gelir, tab_gider, tab_ayrilan = st.tabs(["📊 Portföy", "💵 Gelirler", "💸 Giderler", "🛡️ Bütçe"])

# --- SEKME 1: PORTFÖY ---
with tab_portfoy:
    enstruman_bilgi = {'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦', 'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'}
    enstrumanlar = list(enstruman_bilgi.keys())

    with st.sidebar:
        st.header("📥 Portföy Güncelle")
        try:
            temp_data = ws_portfoy.get_all_records()
            if temp_data:
                df_temp = pd.DataFrame(temp_data)
                son_kayitlar = df_temp.iloc[-1]
            else:
                son_kayitlar = {e: 0.0 for e in enstrumanlar}
        except:
            son_kayitlar = {e: 0.0 for e in enstrumanlar}

        with st.form("p_form", clear_on_submit=True):
            p_in = {}
            for e in enstrumanlar:
                son_val = float(son_kayitlar.get(e, 0))
                p_in[e] = st.number_input(f"{enstruman_bilgi[e]} {e}", min_value=0.0, value=None, format="%.f", help=f"Son: {int(son_val):,}")
            
            if st.form_submit_button("🚀 Kaydet"):
                yeni_satir = [datetime.now().strftime('%Y-%m-%d')]
                for e in enstrumanlar:
                    val = p_in[e] if p_in[e] is not None else float(son_kayitlar.get(e, 0))
                    yeni_satir.append(val)
                
                bugun = datetime.now().strftime('%Y-%m-%d')
                tarihler = ws_portfoy.col_values(1)
                if bugun in tarihler:
                    satir_no = tarihler.index(bugun) + 1
                    ws_portfoy.update(f"A{satir_no}:I{satir_no}", [yeni_satir])
                else:
                    ws_portfoy.append_row(yeni_satir)
                st.success("Kaydedildi!"); st.rerun()

    data_p = ws_portfoy.get_all_records()
    if data_p:
        df_p = pd.DataFrame(data_p)
        df_p['tarih'] = pd.to_datetime(df_p['tarih'])
        df_p['Toplam'] = df_p[enstrumanlar].sum(axis=1)
        guncel = df_p.iloc[-1]

        st.metric("Toplam Varlık", f"{int(guncel['Toplam']):,.0f} TL".replace(",", "."))
        
        # Değişim Analizi
        periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90}
        secilen_periyot = st.selectbox("Analiz Periyodu", list(periyotlar.keys()))
        # ... (Değişim analizi kodun burada aynen devam edebilir) ...

        # Varlık Dağılım Grafiği
        varlik_df = pd.DataFrame([{'Cins': e, 'Tutar': guncel[e]} for e in enstrumanlar if guncel[e] > 0])
        fig_p = px.pie(varlik_df, values='Tutar', names='Cins', hole=0.4, title="Varlık Dağılımı")
        st.plotly_chart(fig_p, use_container_width=True)

# --- SEKME 2: GELİRLER ---
with tab_gelir:
    st.subheader("💵 Gelir Yönetimi")
    with st.form("g_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        m = c1.number_input("Maaş", min_value=0)
        p = c2.number_input("Prim & Promosyon", min_value=0)
        y = c3.number_input("Yatırımlar", min_value=0)
        if st.form_submit_button("Geliri Kaydet"):
            toplam = (m or 0) + (p or 0) + (y or 0)
            ws_gelir.append_row([datetime.now().strftime('%Y-%m-%d'), m, p, y, toplam])
            st.success("Gelir eklendi!"); st.rerun()

    data_g = ws_gelir.get_all_records()
    if data_g:
        df_g = pd.DataFrame(data_g)
        df_g['Tarih'] = pd.to_datetime(df_g['Tarih'])
        
        col1, col2 = st.columns(2)
        with col1:
            # Pasta Grafik (Kategori Dağılımı)
            gelir_toplamlari = df_g[['Maaş', 'Prim', 'Yatırım']].sum()
            fig_g_pie = px.pie(values=gelir_toplamlari.values, names=gelir_toplamlari.index, title="Gelir Kaynakları Dağılımı")
            st.plotly_chart(fig_g_pie, use_container_width=True)
        
        with col2:
            # Çubuk Grafik (Zaman Serisi)
            fig_g_bar = px.bar(df_g, x='Tarih', y='Toplam', title="Zamana Göre Gelir Akışı", color_discrete_sequence=['#2ecc71'])
            st.plotly_chart(fig_g_bar, use_container_width=True)

# --- SEKME 3: GİDERLER ---
with tab_gider:
    kalan_bakiye, limit = get_son_bakiye_ve_limit()
    st.info(f"💰 Güncel Kalan Bütçe: **{int(kalan_bakiye):,.0f} TL**")
    
    gider_ikonlari = {"Genel Giderler": "📦", "Market": "🛒", "Kira": "🏠", "Aidat": "🏢", "Kredi Kartı": "💳", "Kredi": "🏦", "Eğitim": "🎓", "Araba": "🚗", "Seyahat": "✈️", "Sağlık": "🏥", "Çocuk": "👶", "Toplu Taşıma": "🚌"}
    
    with st.form("gi_form", clear_on_submit=True):
        cols = st.columns(3)
        inputs = {isim: cols[i % 3].number_input(f"{ikon} {isim}", min_value=0) for i, (isim, ikon) in enumerate(gider_ikonlari.items())}
        if st.form_submit_button("✅ Harcamayı Kaydet"):
            toplam_h = sum(inputs.values())
            if toplam_h > 0:
                yeni_kalan = kalan_bakiye - toplam_h
                ws_gider.append_row([datetime.now().strftime('%Y-%m-%d')] + list(inputs.values()))
                ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), limit, yeni_kalan])
                st.success(f"Harca Kaydedildi. Kalan: {int(yeni_kalan)}"); st.rerun()

    data_gi = ws_gider.get_all_records()
    if data_gi:
        df_gi = pd.DataFrame(data_gi)
        # Sadece sayısal kolonları topla (ilk kolon tarih olduğu için dışarıda bırakıyoruz)
        gider_ozet = df_gi.drop(columns=['Tarih']).sum()
        
        # Gider Pasta Grafiği
        fig_gi_pie = px.pie(values=gider_ozet.values, names=gider_ozet.index, title="Harcama Dağılımı (Kategorik)", hole=0.3)
        st.plotly_chart(fig_gi_pie, use_container_width=True)

# --- SEKME 4: BÜTÇE ---
with tab_ayrilan:
    st.subheader("🛡️ Bütçe Ekleme")
    st.write("Buraya yazdığınız tutar, mevcut kalan bütçenizin üzerine eklenecektir.")
    
    kalan_bakiye, mevcut_limit = get_son_bakiye_ve_limit()
    st.write(f"Mevcut Bakiye: **{int(kalan_bakiye):,.0f} TL**")

    with st.form("b_form"):
        yeni_eklenecek = st.number_input("Eklenecek Tutar (TL)", min_value=0)
        if st.form_submit_button("Bakiyeye Ekle"):
            # MANTIK DÜZELTİLDİ: Yeni bakiye = Eski Kalan + Yeni Gelen
            yeni_toplam_kalan = kalan_bakiye + yeni_eklenecek
            # Limit sütununa da bu dönemin yeni ana bütçesini (veya toplam bütçeyi) yazıyoruz
            ws_ayrilan.append_row([datetime.now().strftime('%Y-%m-%d'), yeni_eklenecek, yeni_toplam_kalan])
            st.success(f"Yeni bakiyeniz: {int(yeni_toplam_kalan)} TL"); st.rerun()
