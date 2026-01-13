import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import yfinance as yf

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy Takip", layout="wide")
st.title("📊 Akıllı Portföy Yönetimi")

# --- KUR ÇEKME FONKSİYONU ---
@st.cache_data(ttl=3600) # Kurları saatte bir günceller
def kurlari_getir():
    try:
        usd = yf.Ticker("USDTRY=X").history(period="1d")['Close'].iloc[-1]
        eur = yf.Ticker("EURTRY=X").history(period="1d")['Close'].iloc[-1]
        return usd, eur
    except:
        return 30.1, 33.1 # Hata durumunda varsayılan (yaklaşık) kurlar

usd_kur, eur_kur = kurlari_getir()

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

# --- 2. VERİ GİRİŞİ VE İKON TANIMLARI ---
# Döviz'i USD ve EUR olarak ayırdık
enstruman_bilgi = {
    'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦',
    'USD': '💵', 'EUR': '💶', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'
}
enstrumanlar = list(enstruman_bilgi.keys())

with st.sidebar:
    st.header("📥 Veri Girişi")
    st.write(f"📢 **Güncel Kurlar:** USD: {usd_kur:.2f} | EUR: {eur_kur:.2f}")
    
    with st.form("veri_formu", clear_on_submit=True):
        yeni_degerler = []
        for e in enstrumanlar:
            label = f"{enstruman_bilgi[e]} {e} " + ("(Miktar)" if e in ['USD', 'EUR'] else "(TL)")
            val = st.number_input(label, min_value=0.0, step=1.0 if e in ['USD', 'EUR'] else 100.0)
            yeni_degerler.append(val)
        submit = st.form_submit_button("🚀 Verileri Kaydet")

if submit:
    yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + yeni_degerler
    worksheet.append_row(yeni_satir)
    st.toast("Veriler kaydedildi!", icon='✅')
    st.rerun()

# --- 3. VERİ İŞLEME ---
data = worksheet.get_all_records()
if data:
    df = pd.DataFrame(data)
    for col in enstrumanlar:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Dövizleri TL'ye çevirme
    df['USD_TL'] = df['USD'] * usd_kur
    df['EUR_TL'] = df['EUR'] * eur_kur
    
    # Toplam hesaplama (USD ve EUR'nun miktarını değil, TL karşılığını topluyoruz)
    diger_kalemler = [e for e in enstrumanlar if e not in ['USD', 'EUR']]
    df['Toplam'] = df[diger_kalemler].sum(axis=1) + df['USD_TL'] + df['EUR_TL']
    
    df['tarih'] = pd.to_datetime(df['tarih'])
    df = df.sort_values('tarih')

    # ÖZET KARTLARI
    guncel_verisi = df.iloc[-1]
    st.columns(3)[0].metric("Toplam Varlık", f"{guncel_verisi['Toplam']:,.0f} TL")

    st.divider()

    # --- 4. GRAFİKLER ---
    t1, t2 = st.tabs(["📈 Gelişim", "🥧 Varlık Dağılımı"])
    
    with t1:
        st.line_chart(df.set_index('tarih')['Toplam'])
        
    with t2:
        # Görselleştirme için verileri TL karşılıklarıyla hazırlıyoruz
        pasta_verisi = {
            'Hisse Senedi': guncel_verisi['Hisse Senedi'],
            'Altın': guncel_verisi['Altın'],
            'Gümüş': guncel_verisi['Gümüş'],
            'Fon': guncel_verisi['Fon'],
            'USD ($)': guncel_verisi['USD_TL'],
            'EUR (€)': guncel_verisi['EUR_TL'],
            'Kripto': guncel_verisi['Kripto'],
            'Mevduat': guncel_verisi['Mevduat'],
            'BES': guncel_verisi['BES']
        }
        
        pasta_df = pd.DataFrame({
            'Enstrüman': [f"{enstruman_bilgi.get(k.split(' ')[0], '💰')} {k}" for k, v in pasta_verisi.items() if v > 0],
            'Değer': [v for v in pasta_verisi.values() if v > 0]
        })
        
        # SIRALAMA: Büyükten küçüğe
        pasta_df = pasta_df.sort_values(by='Değer', ascending=False)
        
        if not pasta_df.empty:
            fig = px.pie(pasta_df, values='Değer', names='Enstrüman', hole=0.4,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_traces(textinfo='percent+label', textposition='inside')
            fig.update_layout(margin=dict(t=30, b=30, l=30, r=30), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- 5. PERFORMANS KARTLARI (Büyükten Küçüğe) ---
    st.subheader("⏱️ Varlık Bazlı Durum (Büyükten Küçüğe)")
    
    # Kartlar için güncel TL değerlerini içeren bir liste oluşturup sıralıyoruz
    kart_listesi = []
    for e in enstrumanlar:
        if e == 'USD': val = guncel_verisi['USD_TL']
        elif e == 'EUR': val = guncel_verisi['EUR_TL']
        else: val = guncel_verisi[e]
        
        if val > 0:
            kart_listesi.append({'isim': f"{enstruman_bilgi[e]} {e}", 'deger': val})
    
    # Sırala
    kart_listesi = sorted(kart_listesi, key=lambda x: x['deger'], reverse=True)
    
    cols = st.columns(4)
    for i, item in enumerate(kart_listesi):
        cols[i % 4].metric(item['isim'], f"{item['deger']:,.0f} TL")

else:
    st.info("💡 Veri girişi yapın.")
