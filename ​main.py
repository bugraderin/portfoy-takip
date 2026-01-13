import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import yfinance as yf

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy Paneli", layout="wide")
st.title("⚖️ Akıllı Varlık Yönetimi")

# --- OTOMATİK KUR ÇEKME ---
@st.cache_data(ttl=3600)
def kurlari_al():
    try:
        usd = yf.Ticker("USDTRY=X").history(period="1d")['Close'].iloc[-1]
        eur = yf.Ticker("EURTRY=X").history(period="1d")['Close'].iloc[-1]
        return usd, eur
    except:
        return 30.0, 33.0 # Yedek kurlar

usd_anlik, eur_anlik = kurlari_al()

# --- 1. GOOGLE SHEETS BAĞLANTISI ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("portfoyum")
    worksheet = spreadsheet.worksheet("Veri Sayfası")
except Exception as e:
    st.error(f"Veritabanı Hatası: {e}")
    st.stop()

# --- 2. VARLIK TANIMLARI ---
# Döviz kalktı, USD ve EUR geldi
enstruman_bilgi = {
    'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦',
    'USD': '💵', 'EUR': '💶', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'
}
enstrumanlar = list(enstruman_bilgi.keys())

# --- 3. UI/UX: YENİ VERİ GİRİŞ ALANI ---
with st.sidebar:
    st.header("📥 Yeni Kayıt")
    st.info(f"💵 USD: **{usd_anlik:.2f}** | 💶 EUR: **{eur_anlik:.2f}**")
    
    with st.form("yeni_form", clear_on_submit=True):
        inputs = {}
        # Giriş alanlarını daha temiz yapıyoruz
        for e in enstrumanlar:
            label = f"{enstruman_bilgi[e]} {e}"
            if e in ['USD', 'EUR']:
                # Dolar ve Euro için miktar (adet) girişi
                inputs[e] = st.number_input(f"{label} (Miktar)", min_value=0.0, step=0.01, format="%.2f")
            else:
                # Diğerleri için TL girişi
                inputs[e] = st.number_input(f"{label} (TL Toplam)", min_value=0.0, step=100.0, format="%.0f")
        
        st.write("---")
        submit = st.form_submit_button("✅ Portföyü Güncelle", use_container_width=True)

if submit:
    yeni_satir = [datetime.now().strftime('%Y-%m-%d')] + [inputs[e] for e in enstrumanlar]
    worksheet.append_row(yeni_satir)
    st.toast("Veriler buluta gönderildi!", icon='🚀')
    st.rerun()

# --- 4. VERİ İŞLEME VE SIRALAMA ---
data = worksheet.get_all_records()
if data:
    df = pd.DataFrame(data)
    for col in enstrumanlar:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Döviz dönüşümleri
    df['USD_TL'] = df['USD'] * usd_anlik
    df['EUR_TL'] = df['EUR'] * eur_anlik
    
    # Toplam Portföy (TL bazlı)
    t_cols = [e for e in enstrumanlar if e not in ['USD', 'EUR']]
    df['Toplam'] = df[t_cols].sum(axis=1) + df['USD_TL'] + df['EUR_TL']
    df['tarih'] = pd.to_datetime(df['tarih'])
    df = df.sort_values('tarih')
    
    guncel = df.iloc[-1]

    # --- 5. GÖRSELLEŞTİRME ---
    t1, t2 = st.tabs(["📊 Dağılım ve Sıralama", "📈 Zaman Grafiği"])
    
    with t1:
        # Verileri TL bazlı hazırlayıp SIRALIYORUZ
        plot_data = []
        for e in enstrumanlar:
            val = guncel['USD_TL'] if e == 'USD' else (guncel['EUR_TL'] if e == 'EUR' else guncel[e])
            if val > 0:
                plot_data.append({'Varlık': f"{enstruman_bilgi[e]} {e}", 'Değer': val})
        
        p_df = pd.DataFrame(plot_data).sort_values(by='Değer', ascending=False)
        
        col_left, col_right = st.columns([1.2, 1])
        
        with col_left:
            # Pasta Grafiği (Emoji destekli Plotly)
            fig = px.pie(p_df, values='Değer', names='Varlık', hole=0.5,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_traces(textinfo='percent+label', textposition='inside')
            fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
            
        with col_right:
            st.subheader("🔝 En Büyük Varlıklar")
            for _, row in p_df.iterrows():
                st.write(f"**{row['Varlık']}:** {row['Değer']:,.0f} TL")
                st.progress(min(row['Değer'] / guncel['Toplam'], 1.0))

    with t2:
        st.line_chart(df.set_index('tarih')['Toplam'])

    st.divider()

    # --- 6. PERFORMANS KARTLARI (BÜYÜKTEN KÜÇÜĞE) ---
    st.subheader("💰 Varlık Bazlı Güncel Durum")
    # Kartları sıralı basıyoruz
    p_cols = st.columns(4)
    for i, (_, row) in enumerate(p_df.iterrows()):
        p_cols[i % 4].metric(label=row['Varlık'], value=f"{row['Değer']:,.0f} TL")

else:
    st.info("Henüz veri yok, soldan ilk girişini yap!")
