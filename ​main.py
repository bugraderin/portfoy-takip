import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
 
# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy Takip", layout="wide")
st.title("📊 Bizim Portföyümüz")
 
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
 
# --- 2. VERİ GİRİŞ FORMU ---
enstrumanlar = ['Hisse Senedi', 'Altın', 'Gümüş', 'Fon', 'Döviz', 'Kripto', 'Mevduat', 'BES']
 
with st.sidebar:
    st.subheader("Yeni Veri Girişi")
    with st.form("veri_formu", clear_on_submit=True):
        yeni_degerler = []
        for e in enstrumanlar:
            val = st.number_input(f"{e} (TL)", min_value=0.0, step=100.0)
            yeni_degerler.append(val)
        submit = st.form_submit_button("Buluta Kaydet")
 
if submit:
    yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + yeni_degerler
    worksheet.append_row(yeni_satir)
    st.success("✅ Kaydedildi!")
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
 
    # --- ÖZET KARTLARI ---
    col1, col2, col3 = st.columns(3)
    guncel_toplam = df['Toplam'].iloc[-1]
    col1.metric("Güncel Toplam Portföy", f"{guncel_toplam:,.2f} TL")
    
    if len(df) > 1:
        degisim = guncel_toplam - df['Toplam'].iloc[-2]
        yuzde = (degisim / df['Toplam'].iloc[-2]) * 100
        col2.metric("Son Değişim (TL)", f"{degisim:,.2f} TL", f"{yuzde:.2f}%")
    col3.metric("Kayıt Sayısı", len(df))
 
    st.divider()
 
    # --- GRAFİKLER ---
    tab1, tab2 = st.tabs(["📈 Zaman İçindeki Gelişim", "🥧 Güncel Dağılım"])
    with tab1:
        st.subheader("Toplam Varlık Değişimi")
        st.line_chart(df.set_index('tarih')['Toplam'])
        
    with tab2:
        st.subheader("Varlık Dağılımı (Son Durum)")
        import matplotlib.pyplot as plt
        son_durum = df[enstrumanlar].iloc[-1]
        pastane_verisi = son_durum[son_durum > 0]
        if not pastane_verisi.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.pie(pastane_verisi, labels=pastane_verisi.index, autopct='%1.1f%%', startangle=140)
            st.pyplot(fig)
 
    st.divider()
 
    # --- 4. PERFORMANS ANALİZİ (YENİ ALAN) ---
    st.subheader("⏱️ Dönemsel Performans Analizi")
    
    # Zaman periyotları tanımları
    periyotlar = {
        "1 Gün": 1,
        "1 Ay": 30,
        "3 Ay": 90,
        "6 Ay": 180,
        "1 Yıl": 365,
        "3 Yıl": 1095,
        "5 Yıl": 1825
    }
    
    secilen_periyot = st.select_slider(
        "Analiz etmek istediğiniz süreyi seçin:",
        options=list(periyotlar.keys())
    )
    
    gun_sayisi = periyotlar[secilen_periyot]
    hedef_tarih = pd.Timestamp(datetime.now() - timedelta(days=gun_sayisi))
    
    # Hedef tarihe en yakın geçmiş veriyi bulalım
    gecmis_df = df[df['tarih'] <= hedef_tarih]
    
    if not gecmis_df.empty:
        baslangic_verisi = gecmis_df.iloc[-1]
        guncel_verisi = df.iloc[-1]
        
        # Toplam Performans Kartı
        t_baslangic = baslangic_verisi['Toplam']
        t_guncel = guncel_verisi['Toplam']
        t_degisim = ((t_guncel - t_baslangic) / t_baslangic) * 100 if t_baslangic > 0 else 0
        
        st.info(f"📅 **{secilen_periyot}** önceki portföy değeri: **{t_baslangic:,.2f} TL** | Toplam Değişim: **%{t_degisim:.2f}**")
        
        # Enstrüman Bazlı Detay
        st.write("🔍 **Enstrüman Bazlı Yüzdelik Değişimler:**")
        cols = st.columns(len(enstrumanlar))
        
        for i, e in enumerate(enstrumanlar):
            v_eski = baslangic_verisi[e]
            v_yeni = guncel_verisi[e]
            
            # Değişim hesapla (Sadece eskiden veri varsa)
            if v_eski > 0:
                e_degisim = ((v_yeni - v_eski) / v_eski) * 100
                cols[i].metric(e, f"%{e_degisim:.1f}", delta_color="normal")
            else:
                cols[i].text(f"{e}\n(Veri Yok)")
    else:
        st.warning(f"Seçilen periyot ({secilen_periyot}) için yeterli geçmiş veri bulunamadı.")
 
    st.divider()
 
    # --- GEÇMİŞ VERİ TABLOSU ---
    with st.expander("📄 Tüm Geçmiş Veri Tablosunu Gör"):
        st.dataframe(df.sort_values('tarih', ascending=False))
else:
    st.info("💡 Henüz veri bulunamadı.")
