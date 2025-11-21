import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from budget_forecast import BudgetForecaster
import numpy as np

# Sayfa konfigürasyonu
st.set_page_config(
    page_title="2026 Satış Bütçe Tahmini",
    page_icon="📊",
    layout="wide"
)

# CSS ile bazı styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<p class="main-header">📊 2026 Satış Bütçe Tahmini Sistemi</p>', unsafe_allow_html=True)

# Sidebar - Parametreler
st.sidebar.header("📋 Tahmin Parametreleri")

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Büyüme Hedefi")
growth_input_type = st.sidebar.radio(
    "Hedef Giriş Tipi",
    ["Tüm Yıl İçin Tek Hedef", "Ay Bazında Hedef"],
    index=0,
    help="Tek hedef veya her ay için ayrı hedef"
)

monthly_growth_targets = {}

if growth_input_type == "Tüm Yıl İçin Tek Hedef":
    growth_param = st.sidebar.slider(
        "Yıllık Satış Büyüme Hedefi (%)",
        min_value=-20.0,
        max_value=50.0,
        value=15.0,
        step=1.0,
        help="2026 yılı için hedeflenen satış büyümesi"
    ) / 100
    
    # Tüm aylar için aynı hedef
    for month in range(1, 13):
        monthly_growth_targets[month] = growth_param
    
else:
    st.sidebar.markdown("**Her Ay İçin Büyüme Hedefi (%):**")
    st.sidebar.caption("↓ Aşağı kaydırarak tüm ayları görebilirsiniz")
    
    # Ay isimleri
    month_names = {
        1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
        5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
        9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
    }
    
    # Her ay için slider
    for month in range(1, 13):
        monthly_growth_targets[month] = st.sidebar.slider(
            f"{month_names[month]} ({month})",
            min_value=-20.0,
            max_value=50.0,
            value=15.0,
            step=1.0,
            key=f"month_{month}"
        ) / 100
    
    # Ortalama göster
    avg_monthly = sum(monthly_growth_targets.values()) / 12
    st.sidebar.info(f"📊 Ortalama Hedef: %{avg_monthly*100:.1f}")
    
    growth_param = avg_monthly  # Genel hesaplamalar için ortalama kullan

st.sidebar.markdown("---")
st.sidebar.subheader("📈 Karlılık Hedefi")
margin_improvement = st.sidebar.slider(
    "Brüt Marj İyileşme Hedefi (puan)",
    min_value=-5.0,
    max_value=10.0,
    value=2.0,
    step=0.5,
    help="Mevcut brüt marj üzerine eklenecek puan"
) / 100

st.sidebar.markdown("---")
st.sidebar.subheader("📦 Stok Hedefi")

stock_param_type = st.sidebar.radio(
    "Stok Parametresi",
    ["Stok/SMM Oranı", "Stok Tutar Değişimi"],
    index=0,
    help="Stok hedefini oran veya tutar bazında belirle"
)

if stock_param_type == "Stok/SMM Oranı":
    stock_ratio_target = st.sidebar.slider(
        "Hedef Stok/SMM Oranı",
        min_value=0.3,
        max_value=2.0,
        value=0.8,
        step=0.1,
        help="Stok tutarı / Satılan Malın Maliyeti oranı"
    )
    stock_change_pct = None
else:
    stock_change_pct = st.sidebar.slider(
        "Stok Tutar Değişimi (%)",
        min_value=-50.0,
        max_value=100.0,
        value=0.0,
        step=5.0,
        help="2025'e göre stok tutarında % artış veya azalış"
    ) / 100
    stock_ratio_target = None

st.sidebar.markdown("---")
st.sidebar.subheader("Tahmin Yöntemi")
forecast_method = st.sidebar.selectbox(
    "Model Tipi",
    ["Gelişmiş (Trend + Mevsimsellik + Momentum)", 
     "Orta (Trend + Mevsimsellik)",
     "Basit (Sadece Büyüme Parametresi)"],
    index=0
)

# File upload
st.sidebar.markdown("---")
st.sidebar.subheader("📂 Veri Yükleme")
uploaded_file = st.sidebar.file_uploader(
    "Excel Dosyası Yükle",
    type=['xlsx'],
    help="2024-2025 verilerini içeren Excel dosyası"
)

# Load data
@st.cache_data
def load_data(file_path):
    forecaster = BudgetForecaster(file_path)
    return forecaster

try:
    if uploaded_file is not None:
        # Geçici dosyaya kaydet
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        with st.spinner('Veri yükleniyor...'):
            forecaster = load_data(tmp_path)
        
        # Geçici dosyayı sil
        os.unlink(tmp_path)
    else:
        st.info("👆 Lütfen soldaki menüden Excel dosyanızı yükleyin.")
        st.stop()
    
    # Tahmin yap
    with st.spinner('Tahmin hesaplanıyor...'):
        # Stok hedefini belirle
        if stock_change_pct is not None:
            # Stok tutar değişimi seçildi - 2025 ortalama stokunu hesapla
            avg_stock_2025 = forecaster.data[forecaster.data['Year'] == 2025]['Stock'].mean()
            target_stock_2026 = avg_stock_2025 * (1 + stock_change_pct)
            
            # COGS'a göre oran hesapla (tahmin içinde kullanılacak)
            avg_cogs_2025 = forecaster.data[forecaster.data['Year'] == 2025]['COGS'].mean()
            if avg_cogs_2025 > 0:
                stock_ratio_calc = target_stock_2026 / avg_cogs_2025
            else:
                stock_ratio_calc = 0.8
            
            full_data = forecaster.get_full_data_with_forecast(
                growth_param=growth_param,
                margin_improvement=margin_improvement,
                stock_ratio_target=stock_ratio_calc
            )
        else:
            # Stok/SMM oranı seçildi
            full_data = forecaster.get_full_data_with_forecast(
                growth_param=growth_param,
                margin_improvement=margin_improvement,
                stock_ratio_target=stock_ratio_target
            )
        
        summary = forecaster.get_summary_stats(full_data)
    
    # Ana metrikler
    st.markdown("## 📈 Özet Metrikler")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        sales_2026 = summary[2026]['Total_Sales']
        sales_2025 = summary[2025]['Total_Sales']
        sales_growth = ((sales_2026 - sales_2025) / sales_2025 * 100) if sales_2025 > 0 else 0
        
        st.metric(
            label="2026 Toplam Satış",
            value=f"₺{sales_2026:,.0f}",
            delta=f"%{sales_growth:.1f} vs 2025"
        )
    
    with col2:
        margin_2026 = summary[2026]['Avg_GrossMargin%']
        margin_2025 = summary[2025]['Avg_GrossMargin%']
        margin_change = margin_2026 - margin_2025
        
        st.metric(
            label="2026 Brüt Marj",
            value=f"%{margin_2026:.1f}",
            delta=f"{margin_change:+.1f} puan"
        )
    
    with col3:
        gp_2026 = summary[2026]['Total_GrossProfit']
        gp_2025 = summary[2025]['Total_GrossProfit']
        gp_growth = ((gp_2026 - gp_2025) / gp_2025 * 100) if gp_2025 > 0 else 0
        
        st.metric(
            label="2026 Brüt Kar",
            value=f"₺{gp_2026:,.0f}",
            delta=f"%{gp_growth:.1f} vs 2025"
        )
    
    with col4:
        stock_2026 = summary[2026]['Avg_Stock']
        stock_2025 = summary[2025]['Avg_Stock']
        stock_change = ((stock_2026 - stock_2025) / stock_2025 * 100) if stock_2025 > 0 else 0
        
        if stock_change_pct is not None:
            # Tutar değişimi göster
            st.metric(
                label="2026 Ort. Stok",
                value=f"₺{stock_2026:,.0f}",
                delta=f"%{stock_change:+.1f} vs 2025"
            )
        else:
            # Oran göster
            stock_ratio_2026 = summary[2026]['Avg_Stock_COGS_Ratio']
            st.metric(
                label="2026 Stok/SMM Oranı",
                value=f"{stock_ratio_2026:.2f}",
                delta=f"Hedef: {stock_ratio_target:.2f}"
            )
    
    st.markdown("---")
    
    # Tab'lar
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Aylık Trend", "🎯 Ana Grup Analizi", "📅 Yıllık Karşılaştırma", "📋 Detay Veriler"])
    
    with tab1:
        st.subheader("Aylık Satış Trendi (2024-2026)")
        
        # Aylık toplam satış
        monthly_sales = full_data.groupby(['Year', 'Month'])['Sales'].sum().reset_index()
        
        fig = go.Figure()
        
        for year in [2024, 2025, 2026]:
            year_data = monthly_sales[monthly_sales['Year'] == year]
            
            line_style = 'solid' if year < 2026 else 'dash'
            line_width = 2 if year < 2026 else 3
            
            fig.add_trace(go.Scatter(
                x=year_data['Month'],
                y=year_data['Sales'],
                mode='lines+markers',
                name=f'{year}' + (' (Tahmin)' if year == 2026 else ''),
                line=dict(dash=line_style, width=line_width),
                marker=dict(size=8)
            ))
        
        fig.update_layout(
            title="Aylık Satış Karşılaştırması",
            xaxis_title="Ay",
            yaxis_title="Satış (TRY)",
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Brüt Marj Trendi
        st.subheader("Aylık Brüt Marj % Trendi")
        
        monthly_margin = full_data.groupby(['Year', 'Month']).apply(
            lambda x: (x['GrossProfit'].sum() / x['Sales'].sum() * 100) if x['Sales'].sum() > 0 else 0
        ).reset_index(name='Margin%')
        
        fig2 = go.Figure()
        
        for year in [2024, 2025, 2026]:
            year_data = monthly_margin[monthly_margin['Year'] == year]
            
            line_style = 'solid' if year < 2026 else 'dash'
            
            fig2.add_trace(go.Scatter(
                x=year_data['Month'],
                y=year_data['Margin%'],
                mode='lines+markers',
                name=f'{year}' + (' (Tahmin)' if year == 2026 else ''),
                line=dict(dash=line_style),
                marker=dict(size=8)
            ))
        
        fig2.update_layout(
            title="Aylık Brüt Marj % Karşılaştırması",
            xaxis_title="Ay",
            yaxis_title="Brüt Marj %",
            hovermode='x unified',
            height=500
        )
        
        st.plotly_chart(fig2, use_container_width=True)
    
    with tab2:
        st.subheader("Ana Grup Bazında Performans")
        
        # Yıllık grup bazında satış
        group_sales = full_data.groupby(['Year', 'MainGroup'])['Sales'].sum().reset_index()
        
        # 2026 için en büyük 10 grup
        top_groups_2026 = group_sales[group_sales['Year'] == 2026].nlargest(10, 'Sales')['MainGroup'].tolist()
        
        group_sales_filtered = group_sales[group_sales['MainGroup'].isin(top_groups_2026)]
        
        fig3 = px.bar(
            group_sales_filtered,
            x='MainGroup',
            y='Sales',
            color='Year',
            barmode='group',
            title='Top 10 Ana Grup - Yıllık Satış Karşılaştırması'
        )
        
        fig3.update_layout(height=500, xaxis_tickangle=-45)
        st.plotly_chart(fig3, use_container_width=True)
        
        # Büyüme analizi
        st.subheader("Ana Grup Büyüme Analizi (2025 → 2026)")
        
        sales_2025 = group_sales[group_sales['Year'] == 2025][['MainGroup', 'Sales']]
        sales_2025.columns = ['MainGroup', 'Sales_2025']
        
        sales_2026 = group_sales[group_sales['Year'] == 2026][['MainGroup', 'Sales']]
        sales_2026.columns = ['MainGroup', 'Sales_2026']
        
        growth_analysis = sales_2025.merge(sales_2026, on='MainGroup')
        growth_analysis['Growth%'] = ((growth_analysis['Sales_2026'] - growth_analysis['Sales_2025']) / 
                                       growth_analysis['Sales_2025'] * 100)
        growth_analysis = growth_analysis.sort_values('Growth%', ascending=False)
        
        fig4 = px.bar(
            growth_analysis.head(15),
            x='MainGroup',
            y='Growth%',
            title='Top 15 Ana Grup - Büyüme Oranı',
            color='Growth%',
            color_continuous_scale='RdYlGn'
        )
        
        fig4.update_layout(height=500, xaxis_tickangle=-45)
        st.plotly_chart(fig4, use_container_width=True)
    
    with tab3:
        st.subheader("Yıllık Toplam Karşılaştırma")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Satış ve Kar karşılaştırması
            yearly_summary = pd.DataFrame({
                'Yıl': [2024, 2025, 2026],
                'Satış': [summary[2024]['Total_Sales'], 
                         summary[2025]['Total_Sales'],
                         summary[2026]['Total_Sales']],
                'Brüt Kar': [summary[2024]['Total_GrossProfit'],
                            summary[2025]['Total_GrossProfit'],
                            summary[2026]['Total_GrossProfit']]
            })
            
            fig5 = go.Figure()
            fig5.add_trace(go.Bar(name='Satış', x=yearly_summary['Yıl'], y=yearly_summary['Satış']))
            fig5.add_trace(go.Bar(name='Brüt Kar', x=yearly_summary['Yıl'], y=yearly_summary['Brüt Kar']))
            
            fig5.update_layout(
                title='Yıllık Satış ve Brüt Kar',
                barmode='group',
                height=400
            )
            
            st.plotly_chart(fig5, use_container_width=True)
        
        with col2:
            # Brüt Marj % karşılaştırması
            yearly_margin = pd.DataFrame({
                'Yıl': [2024, 2025, 2026],
                'Brüt Marj %': [summary[2024]['Avg_GrossMargin%'],
                               summary[2025]['Avg_GrossMargin%'],
                               summary[2026]['Avg_GrossMargin%']]
            })
            
            fig6 = go.Figure()
            fig6.add_trace(go.Scatter(
                x=yearly_margin['Yıl'],
                y=yearly_margin['Brüt Marj %'],
                mode='lines+markers',
                line=dict(width=3),
                marker=dict(size=12)
            ))
            
            fig6.update_layout(
                title='Yıllık Brüt Marj %',
                height=400,
                yaxis_title='Brüt Marj %'
            )
            
            st.plotly_chart(fig6, use_container_width=True)
        
        # Özet tablo
        st.subheader("Yıllık Özet Tablo")
        
        summary_table = pd.DataFrame({
            'Metrik': ['Toplam Satış (TRY)', 'Toplam Brüt Kar (TRY)', 
                      'Brüt Marj %', 'Ort. Stok (TRY)', 'Stok/SMM Oranı'],
            '2024': [
                f"₺{summary[2024]['Total_Sales']:,.0f}",
                f"₺{summary[2024]['Total_GrossProfit']:,.0f}",
                f"%{summary[2024]['Avg_GrossMargin%']:.2f}",
                f"₺{summary[2024]['Avg_Stock']:,.0f}",
                f"{summary[2024]['Avg_Stock_COGS_Ratio']:.2f}"
            ],
            '2025': [
                f"₺{summary[2025]['Total_Sales']:,.0f}",
                f"₺{summary[2025]['Total_GrossProfit']:,.0f}",
                f"%{summary[2025]['Avg_GrossMargin%']:.2f}",
                f"₺{summary[2025]['Avg_Stock']:,.0f}",
                f"{summary[2025]['Avg_Stock_COGS_Ratio']:.2f}"
            ],
            '2026 (Tahmin)': [
                f"₺{summary[2026]['Total_Sales']:,.0f}",
                f"₺{summary[2026]['Total_GrossProfit']:,.0f}",
                f"%{summary[2026]['Avg_GrossMargin%']:.2f}",
                f"₺{summary[2026]['Avg_Stock']:,.0f}",
                f"{summary[2026]['Avg_Stock_COGS_Ratio']:.2f}"
            ]
        })
        
        st.dataframe(summary_table, use_container_width=True, hide_index=True)
    
    with tab4:
        st.subheader("Detaylı Veri Tablosu")
        
        # Yıl seçimi
        selected_year = st.selectbox("Yıl Seçin", [2024, 2025, 2026])
        
        # Filtrelenmiş data
        filtered_data = full_data[full_data['Year'] == selected_year].copy()
        
        # Formatla
        filtered_data['Sales'] = filtered_data['Sales'].apply(lambda x: f"₺{x:,.0f}")
        filtered_data['GrossProfit'] = filtered_data['GrossProfit'].apply(lambda x: f"₺{x:,.0f}")
        filtered_data['GrossMargin%'] = filtered_data['GrossMargin%'].apply(lambda x: f"%{x*100:.2f}")
        filtered_data['Stock'] = filtered_data['Stock'].apply(lambda x: f"₺{x:,.0f}")
        filtered_data['COGS'] = filtered_data['COGS'].apply(lambda x: f"₺{x:,.0f}")
        filtered_data['Stock_COGS_Ratio'] = filtered_data['Stock_COGS_Ratio'].apply(lambda x: f"{x:.2f}")
        
        # Sıralama
        filtered_data = filtered_data.sort_values(['Month', 'MainGroup'])
        
        st.dataframe(
            filtered_data[['Month', 'MainGroup', 'Sales', 'GrossProfit', 
                          'GrossMargin%', 'Stock', 'COGS', 'Stock_COGS_Ratio']],
            use_container_width=True,
            hide_index=True
        )
        
        # Excel export
        st.download_button(
            label="📥 Excel'e Aktar",
            data=full_data.to_csv(index=False).encode('utf-8'),
            file_name=f'budget_forecast_{selected_year}.csv',
            mime='text/csv'
        )

except Exception as e:
    st.error(f"Bir hata oluştu: {str(e)}")
    st.exception(e)

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>2026 Satış Bütçe Tahmin Sistemi | Mevsimsellik + Trend + Momentum Analizi</p>
    </div>
""", unsafe_allow_html=True)
