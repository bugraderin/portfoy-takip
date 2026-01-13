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
 
    # ÖZET KARTLARI
    col1, col2, col3 = st.columns(3)
    guncel_verisi = df.iloc[-1]
    guncel_toplam = guncel_verisi['Toplam']
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
        st.line_chart(df.set_index('tarih')['Toplam'])
        
    with tab2:
        import matplotlib.pyplot as plt
        son_durum = df[enstrumanlar].iloc[-1]
        pastane_verisi = son_durum[son_durum > 0]
        if not pastane_verisi.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.pie(pastane_verisi, labels=pastane_verisi.index, autopct='%1.1f%%', startangle=140)
            st.pyplot(fig)
 
    st.divider()
 
    # --- 4. PERFORMANS ANALİZİ (GÜNCELLENEN KISIM) ---
    st.subheader("⏱️ Dönemsel Performans Analizi")
    
    periyotlar = {
        "1 Gün": 1, "1 Ay": 30, "3 Ay": 90,
        "6 Ay": 180, "1 Yıl": 365, "3 Yıl": 1095, "5 Yıl": 1825
    }
    
    secilen_label = st.selectbox("Analiz periyodu seçin:", list(periyotlar.keys()))
    
    gun_farki = periyotlar[secilen_label]
    hedef_tarih = datetime.now() - timedelta(days=gun_farki)
    
    # MANTIK DEĞİŞİKLİĞİ:
    # Hedef tarihten ÖNCEKİ en son kaydı bulmaya çalışır.
    # Eğer yoksa (yani yeni başladıysan), mevcut olan EN ESKİ kaydı başlangıç kabul eder.
    gecmis_df = df[df['tarih'] <= hedef_tarih]
    
    if gecmis_df.empty:
        # Eğer hedef tarihte veri yoksa, sistemdeki ilk (en eski) veriyi al
        baslangic_verisi = df.iloc[0]
        baslangic_notu = "(Sistemdeki en eski veriniz baz alındı)"
    else:
        baslangic_verisi = gecmis_df.iloc[-1]
        baslangic_notu = f"({secilen_label} önceki veriniz baz alındı)"
    
    # Başlangıç ve Güncel Veri Kıyaslama
    t_baslangic = baslangic_verisi['Toplam']
    
    # Eğer başlangıç ve güncel veri aynıysa (tek kayıt varsa) uyarı ver
    if len(df) > 1:
        t_degisim = ((guncel_toplam - t_baslangic) / t_baslangic) * 100 if t_baslangic > 0 else 0
        
        st.info(f"📅 **{secilen_label}** | Başlangıç: **{t_baslangic:,.2f} TL** | Toplam Değişim: **%{t_degisim:.2f}** \n*{baslangic_notu}*")
        
        st.write("🔍 **Varlık Bazlı Performans Detayları:**")
        m_cols = st.columns(4)
        m_cols_2 = st.columns(4)
        all_cols = m_cols + m_cols_2
        
        for i, e in enumerate(enstrumanlar):
            v_eski = baslangic_verisi[e]
            v_yeni = guncel_verisi[e]
            
            if v_eski > 0:
                e_degisim = ((v_yeni - v_eski) / v_eski) * 100
                all_cols[i].metric(label=e, value=f"{v_yeni:,.0f} TL", delta=f"%{e_degisim:.1f}")
            else:
                all_cols[i].metric(label=e, value=f"{v_yeni:,.0f} TL", delta="Veri Yok", delta_color="off")
    else:
        st.warning("Dönemsel analiz için en az iki farklı güne ait veri girişi yapılmış olmalıdır.")
 
    st.divider()
 
    # --- GEÇMİŞ VERİ TABLOSU ---
    with st.expander("📄 Tüm Geçmiş Veri Tablosunu Gör"):
        st.dataframe(df.sort_values('tarih', ascending=False))
else:
    st.info("💡 Henüz veri bulunamadı.")
