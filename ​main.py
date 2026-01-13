import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
 
# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy Takip", layout="wide")
st.title("📊 Portföy Yönetim Paneli")
 
# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    worksheet = spreadsheet.worksheet("Veri Sayfası")
except Exception as e:
    st.error(f"Bağlantı Hatası: {e}")
    st.stop()
 
# --- 2. VERİ GİRİŞİ VE İKONLAR ---
# İkonlu isimler sözlüğü
enstruman_ikonlar = {
    'Hisse Senedi': '📈 Hisse Senedi',
    'Altın': '🟡 Altın',
    'Gümüş': '⚪ Gümüş',
    'Fon': '🏦 Fon',
    'Döviz': '💵 Döviz',
    'Kripto': '🪙 Kripto',
    'Mevduat': '💰 Mevduat',
    'BES': '🛡️ BES'
}
enstrumanlar = list(enstruman_ikonlar.keys())
 
with st.sidebar:
    st.header("📥 Veri Girişi")
    st.info("Değerleri girip aşağıdaki butona basın.")
    
    with st.form("veri_formu", clear_on_submit=True):
        yeni_degerler = []
        for e in enstrumanlar:
            # İkonlu ismi başlık olarak kullanıyoruz
            val = st.number_input(f"{enstruman_ikonlar[e]} (TL)", min_value=0.0, step=100.0)
            yeni_degerler.append(val)
        
        submit = st.form_submit_button("🚀 Verileri Buluta Kaydet")
 
if submit:
    yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + yeni_degerler
    worksheet.append_row(yeni_satir)
    st.toast("Veriler başarıyla kaydedildi!", icon='✅')
    st.rerun()
 
# --- 3. VERİ İŞLEME ---
data = worksheet.get_all_records()
 
if data:
    df = pd.DataFrame(data)
    for col in enstrumanlar:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'])
        df = df.sort_values('tarih')
    
    df['Toplam'] = df[enstrumanlar].sum(axis=1)
 
    # ÖZET KARTLARI
    guncel_verisi = df.iloc[-1]
    guncel_toplam = guncel_verisi['Toplam']
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Varlık", f"{guncel_toplam:,.0f} TL")
    if len(df) > 1:
        fark = guncel_toplam - df['Toplam'].iloc[-2]
        yuzde_fark = (fark / df['Toplam'].iloc[-2]) * 100
        c2.metric("Günlük Değişim", f"{fark:,.0f} TL", f"%{yuzde_fark:.2f}")
    c3.metric("Veri Giriş Sayısı", len(df))
 
    st.divider()
 
    # --- 4. GRAFİKLER (Geliştirilmiş UI) ---
    t1, t2 = st.tabs(["📈 Gelişim Grafiği", "🥧 Varlık Dağılımı"])
    
    with t1:
        st.line_chart(df.set_index('tarih')['Toplam'])
        
    with t2:
        # Pasta grafiğinin devasa görünmemesi için sütunlara bölüyoruz
        grafik_sol, grafik_orta, grafik_sag = st.columns([1, 2, 1])
        with grafik_orta:
            son_durum = df[enstrumanlar].iloc[-1]
            pastane_verisi = son_durum[son_durum > 0]
            if not pastane_verisi.empty:
                # İkonlu etiketler oluşturma
                labels = [f"{enstruman_ikonlar[k]}" for k in pastane_verisi.index]
                fig, ax = plt.subplots(figsize=(5, 3)) # Boyutu küçülttük
                ax.pie(pastane_verisi, labels=labels, autopct='%1.1f%%',
                       startangle=140, textprops={'fontsize': 7})
                ax.axis('equal')
                st.pyplot(fig)
            else:
                st.warning("Görüntülenecek veri bulunamadı.")
 
    st.divider()
 
    # --- 5. PERFORMANS ANALİZİ ---
    st.subheader("⏱️ Dönemsel Analiz")
    periyotlar = {"1 Gün": 1, "1 Ay": 30, "3 Ay": 90, "6 Ay": 180, "1 Yıl": 365}
    secim = st.selectbox("Kıyaslama süresi seçin:", list(periyotlar.keys()))
    
    hedef_tarih = datetime.now() - timedelta(days=periyotlar[secim])
    gecmis_df = df[df['tarih'] <= hedef_tarih]
    baslangic = gecmis_df.iloc[-1] if not gecmis_df.empty else df.iloc[0]
    
    st.info(f"Seçilen dönem başındaki toplam: **{baslangic['Toplam']:,.0f} TL**")
    
    # Enstrüman performansları
    perf_cols = st.columns(4)
    for i, e in enumerate(enstrumanlar):
        v_eski = baslangic[e]
        v_yeni = guncel_verisi[e]
        col_idx = i % 4
        if v_eski > 0:
            degisim = ((v_yeni - v_eski) / v_eski) * 100
            perf_cols[col_idx].metric(enstruman_ikonlar[e], f"{v_yeni:,.0f}", f"%{degisim:.1f}")
        else:
            perf_cols[col_idx].metric(enstruman_ikonlar[e], f"{v_yeni:,.0f}", "Yeni")
 
    st.divider()
    with st.expander("📄 Tüm Kayıtları Listele"):
        st.dataframe(df.sort_values('tarih', ascending=False), use_container_width=True)
else:
    st.info("💡 Başlamak için sol menüden ilk verinizi kaydedin.")
