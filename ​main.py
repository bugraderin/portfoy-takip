import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import yfinance as yf

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Portföy Takip", layout="wide")
st.title("📊 Portföy Yönetim Paneli")

# --- ANLIK KUR ÇEKME ---
@st.cache_data(ttl=3600)
def kurlari_getir():
    try:
        usd = yf.Ticker("USDTRY=X").history(period="1d")['Close'].iloc[-1]
        eur = yf.Ticker("EURTRY=X").history(period="1d")['Close'].iloc[-1]
        return usd, eur
    except:
        return 30.2, 33.2 # Bağlantı hatası durumunda yaklaşık kurlar

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

# --- 2. VARLIK TANIMLARI ---
# Döviz geri geldi, ancak miktar girişi için USD ve EUR detaylarını kullanacağız
enstruman_bilgi = {
    'Hisse Senedi': '📈', 'Altın': '🟡', 'Gümüş': '⚪', 'Fon': '🏦',
    'Döviz': '💵', 'Kripto': '₿', 'Mevduat': '💰', 'BES': '🛡️'
}
enstrumanlar = list(enstruman_bilgi.keys())

# --- 3. UI: VERİ GİRİŞ ALANI ---
with st.sidebar:
    st.header("📥 Veri Girişi")
    st.caption(f"💵 $: {usd_kur:.2f} | 💶 €: {eur_kur:.2f}")
    
    with st.form("veri_formu", clear_on_submit=True):
        inputs = {}
        for e in enstrumanlar:
            label = f"{enstruman_bilgi[e]} {e}"
            if e == 'Döviz':
                # Döviz başlığı altında USD ve EUR miktarlarını ayrı ayrı alıyoruz
                st.write("---")
                u_amt = st.number_input("💵 Eldeki Dolar ($) Miktarı", min_value=0.0, step=1.0, format="%.2f")
                e_amt = st.number_input("💶 Eldeki Euro (€) Miktarı", min_value=0.0, step=1.0, format="%.2f")
                inputs['USD_Miktar'] = u_amt
                inputs['EUR_Miktar'] = e_amt
                st.write("---")
            else:
                inputs[e] = st.number_input(f"{label} (TL)", min_value=0.0, step=100.0, format="%.0f")
        
        submit = st.form_submit_button("🚀 Kaydet", use_container_width=True)

if submit:
    # Veritabanına kaydederken USD ve EUR miktarlarını saklıyoruz (Sütun yapını buna göre güncellemelisin)
    # Sıralama: Tarih, Hisse, Altın, Gümüş, Fon, USD_Miktarı, EUR_Miktarı, Kripto, Mevduat, BES
    yeni_satir = [
        datetime.now().strftime('%Y-%m-%d'),
        inputs['Hisse Senedi'], inputs['Altın'], inputs['Gümüş'], inputs['Fon'],
        inputs['USD_Miktar'], inputs['EUR_Miktar'],
        inputs['Kripto'], inputs['Mevduat'], inputs['BES']
    ]
    worksheet.append_row(yeni_satir)
    st.toast("Portföy güncellendi!", icon='✅')
    st.rerun()

# --- 4. VERİ İŞLEME ---
data = worksheet.get_all_records()
if data:
    df = pd.DataFrame(data)
    # Sayısal dönüşüm
    for col in df.columns:
        if col != 'tarih':
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Döviz hesaplama: USD ve EUR miktarlarını TL'ye çevirip tek bir "Döviz" sütunu yapıyoruz
    df['Döviz_TL'] = (df['USD_Miktar'] * usd_kur) + (df['EUR_Miktar'] * eur_kur)
    
    # Toplam Portföy
    liste_tl = ['Hisse Senedi', 'Altın', 'Gümüş', 'Fon', 'Kripto', 'Mevduat', 'BES']
    df['Toplam'] = df[liste_tl].sum(axis=1) + df['Döviz_TL']
    
    df['tarih'] = pd.to_datetime(df['tarih'])
    df = df.sort_values('tarih')
    
    guncel = df.iloc[-1]

    # --- 5. GÖRSELLEŞTİRME VE SIRALAMA ---
    t1, t2 = st.tabs(["🥧 Varlık Dağılımı", "📈 Gelişim Grafiği"])
    
    with t1:
        # Verileri SIRALI hazırlıyoruz (Büyükten küçüğe)
        raw_data = [
            {'Varlık': '📈 Hisse Senedi', 'Değer': guncel['Hisse Senedi']},
            {'Varlık': '🟡 Altın', 'Değer': guncel['Altın']},
            {'Varlık': '⚪ Gümüş', 'Değer': guncel['Gümüş']},
            {'Varlık': '🏦 Fon', 'Değer': guncel['Fon']},
            {'Varlık': '💵 Döviz', 'Değer': guncel['Döviz_TL']},
            {'Varlık': '₿ Kripto', 'Değer': guncel['Kripto']},
            {'Varlık': '💰 Mevduat', 'Değer': guncel['Mevduat']},
            {'Varlık': '🛡️ BES', 'Değer': guncel['BES']}
        ]
        
        plot_df = pd.DataFrame(raw_data).sort_values(by='Değer', ascending=False)
        plot_df = plot_df[plot_df['Değer'] > 0] # Sadece varlığı olanları göster
        
        c_sol, c_sag = st.columns([1.2, 1])
        
        with c_sol:
            # Pasta Grafiği
            fig = px.pie(plot_df, values='Değer', names='Varlık', hole=0.5,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_traces(textinfo='percent+label', textposition='inside')
            fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
            
        with c_sag:
            st.subheader("🔝 Varlık Sıralaması")
            for _, row in plot_df.iterrows():
                yuzde = (row['Değer'] / guncel['Toplam']) * 100
                st.write(f"**{row['Varlık']}:** {row['Değer']:,.0f} TL (%{yuzde:.1f})")
                st.progress(min(row['Değer'] / guncel['Toplam'], 1.0))

    with t2:
        st.line_chart(df.set_index('tarih')['Toplam'])

    # --- 6. PERFORMANS KARTLARI (Büyükten Küçüğe) ---
    st.divider()
    st.subheader("💰 Güncel Durum (Sıralı)")
    cols = st.columns(4)
    for i, (_, row) in enumerate(plot_df.iterrows()):
        cols[i % 4].metric(row['Varlık'], f"{row['Değer']:,.0f} TL")

else:
    st.info("💡 Sol menüden ilk verinizi girerek başlayın.")
