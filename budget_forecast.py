import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

class BudgetForecaster:
    def __init__(self, excel_path):
        """Excel'den veriyi yükle ve temizle"""
        # Raw olarak oku, header belirtme
        df_raw = pd.read_excel(excel_path, sheet_name='Sayfa1', header=None)
        
        # Header 1. satır (index 1)
        self.df = pd.read_excel(excel_path, sheet_name='Sayfa1', header=1)
        
        self.process_data()
        
    def process_data(self):
        """Veriyi yıl bazında ayrıştır ve temizle"""
        
        # 2024 verileri - DOĞRU KOLONLAR
        # J (TY Sales Value TRY2) = Gerçek satış değeri
        # H (TY Gross Profit TRY2) = Brüt kar
        # K (TY Gross Marjin TRY%) = Brüt marj %
        # I (TY Avg Store Stock Cost TRY2) = Stok
        df_2024 = self.df[['Month', 'MainGroupDesc', 
                           'TY Sales Value TRY2',          # Kolon J - Gerçek satış
                           'TY Gross Profit TRY2',         # Kolon H - Brüt kar  
                           'TY Gross Marjin TRY%',         # Kolon K - Brüt marj %
                           'TY Avg Store Stock Cost TRY2']].copy()  # Kolon I - Stok
        df_2024.columns = ['Month', 'MainGroup', 'Sales', 'GrossProfit', 'GrossMargin%', 'Stock']
        df_2024['Year'] = 2024
        
        # 2025 verileri - DOĞRU KOLONLAR
        # S (TY Sales Value TRY2.1) = Gerçek satış değeri
        # Q (TY Gross Profit TRY2.1) = Brüt kar
        # T (TY Gross Marjin TRY%.1) = Brüt marj %
        # R (TY Avg Store Stock Cost TRY2.1) = Stok
        df_2025 = self.df[['Month', 'MainGroupDesc',
                           'TY Sales Value TRY2.1',         # Kolon S - Gerçek satış
                           'TY Gross Profit TRY2.1',        # Kolon Q - Brüt kar
                           'TY Gross Marjin TRY%.1',        # Kolon T - Brüt marj %
                           'TY Avg Store Stock Cost TRY2.1']].copy()  # Kolon R - Stok
        df_2025.columns = ['Month', 'MainGroup', 'Sales', 'GrossProfit', 'GrossMargin%', 'Stock']
        df_2025['Year'] = 2025
        
        # Birleştir
        self.data = pd.concat([df_2024, df_2025], ignore_index=True)
        
        # Toplam satırlarını çıkar
        self.data = self.data[~self.data['Month'].astype(str).str.contains('Toplam', na=False)]
        
        # Month'u integer'a çevir
        self.data['Month'] = pd.to_numeric(self.data['Month'], errors='coerce')
        
        # MainGroup boş olanları çıkar
        self.data = self.data.dropna(subset=['MainGroup'])
        
        # NaN değerleri 0 yap
        self.data = self.data.fillna(0)
        
        # SMM hesapla (COGS = Sales - GrossProfit)
        self.data['COGS'] = self.data['Sales'] - self.data['GrossProfit']
        
        # Stok/COGS oranı hesapla (hız)
        self.data['Stock_COGS_Ratio'] = np.where(
            self.data['COGS'] > 0,
            self.data['Stock'] / self.data['COGS'],
            0
        )
        
    def calculate_seasonality(self):
        """Her ay için mevsimsellik indeksi hesapla"""
        
        # Grup ve ay bazında ortalama satış
        monthly_avg = self.data.groupby(['MainGroup', 'Month'])['Sales'].mean().reset_index()
        monthly_avg.columns = ['MainGroup', 'Month', 'AvgSales']
        
        # Her grup için yıllık ortalama
        yearly_avg = self.data.groupby('MainGroup')['Sales'].mean().reset_index()
        yearly_avg.columns = ['MainGroup', 'YearlyAvg']
        
        # Merge
        seasonality = monthly_avg.merge(yearly_avg, on='MainGroup')
        
        # Mevsimsellik indeksi = Aylık Ort / Yıllık Ort
        seasonality['SeasonalityIndex'] = np.where(
            seasonality['YearlyAvg'] > 0,
            seasonality['AvgSales'] / seasonality['YearlyAvg'],
            1
        )
        
        return seasonality[['MainGroup', 'Month', 'SeasonalityIndex']]
    
    def calculate_trend(self):
        """Her grup için trend hesapla (2024->2025 büyümesi)"""
        
        # 2024 toplamı
        total_2024 = self.data[self.data['Year'] == 2024].groupby('MainGroup')['Sales'].sum().reset_index()
        total_2024.columns = ['MainGroup', 'Sales_2024']
        
        # 2025 toplamı
        total_2025 = self.data[self.data['Year'] == 2025].groupby('MainGroup')['Sales'].sum().reset_index()
        total_2025.columns = ['MainGroup', 'Sales_2025']
        
        # Merge
        trend = total_2024.merge(total_2025, on='MainGroup')
        
        # Büyüme oranı hesapla
        trend['GrowthRate'] = np.where(
            trend['Sales_2024'] > 0,
            (trend['Sales_2025'] - trend['Sales_2024']) / trend['Sales_2024'],
            0
        )
        
        return trend[['MainGroup', 'GrowthRate']]
    
    def calculate_recent_momentum(self):
        """Son 3 ayın momentumunu hesapla"""
        
        # Son 3 ay (2025'in 10, 11, 12. ayları varsayalım - veri varsa)
        recent_months = self.data[
            (self.data['Year'] == 2025) & 
            (self.data['Month'].isin([10, 11, 12]))
        ]
        
        if len(recent_months) == 0:
            # Veri yoksa 2025'in tamamını al
            recent_months = self.data[self.data['Year'] == 2025]
        
        # Grup bazında ortalama
        momentum = recent_months.groupby('MainGroup')['Sales'].mean().reset_index()
        momentum.columns = ['MainGroup', 'RecentAvg']
        
        # Genel ortalama ile karşılaştır
        overall_avg = self.data[self.data['Year'] == 2025].groupby('MainGroup')['Sales'].mean().reset_index()
        overall_avg.columns = ['MainGroup', 'OverallAvg']
        
        momentum = momentum.merge(overall_avg, on='MainGroup')
        
        # Momentum skoru (son aylar / genel ortalama)
        momentum['MomentumScore'] = np.where(
            momentum['OverallAvg'] > 0,
            momentum['RecentAvg'] / momentum['OverallAvg'],
            1
        )
        
        return momentum[['MainGroup', 'MomentumScore']]
    
    def forecast_2026(self, growth_param=0.1, margin_improvement=0.0, stock_ratio_target=1.0, monthly_growth_targets=None, maingroup_growth_targets=None, stock_change_pct=None):
        """
        2026 tahminini yap
        
        Parameters:
        -----------
        growth_param: Genel büyüme hedefi (diğer hedefler yoksa kullanılır)
        margin_improvement: Brüt marj iyileşme hedefi (örn: 0.02 = 2 puan)
        stock_ratio_target: Hedef stok/SMM oranı (örn: 0.8) - stock_change_pct None ise
        monthly_growth_targets: Dict {month: growth_rate} - Her ay için özel hedef
        maingroup_growth_targets: Dict {maingroup: growth_rate} - Her ana grup için özel hedef
        stock_change_pct: Stok tutar değişim yüzdesi (örn: -0.05 = %5 azalış)
        """
        
        # Mevsimsellik hesapla
        seasonality = self.calculate_seasonality()
        
        # 2025 verilerini al (base olarak kullanacağız)
        base_2025 = self.data[self.data['Year'] == 2025].copy()
        
        # Mevsimselliği ekle
        forecast = base_2025.merge(seasonality, on=['MainGroup', 'Month'], how='left')
        forecast['SeasonalityIndex'] = forecast['SeasonalityIndex'].fillna(1.0)
        
        # Organik trend (2024->2025)
        total_2024 = self.data[self.data['Year'] == 2024]['Sales'].sum()
        total_2025 = self.data[self.data['Year'] == 2025]['Sales'].sum()
        organic_growth = (total_2025 - total_2024) / total_2024 if total_2024 > 0 else 0
        
        # AY BAZINDA BÜYÜME HEDEFLERİ
        if monthly_growth_targets is not None:
            forecast['MonthlyGrowthTarget'] = forecast['Month'].map(monthly_growth_targets)
            forecast['MonthlyGrowthTarget'] = forecast['MonthlyGrowthTarget'].fillna(growth_param)
        else:
            forecast['MonthlyGrowthTarget'] = growth_param
        
        # ANA GRUP BAZINDA BÜYÜME HEDEFLERİ
        if maingroup_growth_targets is not None:
            forecast['MainGroupGrowthTarget'] = forecast['MainGroup'].map(maingroup_growth_targets)
            forecast['MainGroupGrowthTarget'] = forecast['MainGroupGrowthTarget'].fillna(growth_param)
        else:
            forecast['MainGroupGrowthTarget'] = growth_param
        
        # KOMBINE BÜYÜME HEDEFI
        # Ay hedefi ve Ana Grup hedefinin ortalamasını al
        forecast['CombinedGrowthTarget'] = (forecast['MonthlyGrowthTarget'] + forecast['MainGroupGrowthTarget']) / 2
        
        # TAHMİN FORMÜLÜ
        # 2025 değeri × (1 + organik büyüme × 0.3) × (1 + kombine hedef) × mevsimsel düzeltme
        forecast['Sales_2026'] = (
            forecast['Sales'] *
            (1 + organic_growth * 0.3) *  # Organik trend hafif etki
            (1 + forecast['CombinedGrowthTarget']) *  # Ay + Ana Grup kombine hedef
            (0.85 + forecast['SeasonalityIndex'] * 0.15)  # Mevsimsellik hafif etki
        )
        
        # Gross Margin iyileşmesi
        forecast['GrossMargin%_2026'] = (forecast['GrossMargin%'] + margin_improvement).clip(0, 1)
        
        # GrossProfit ve COGS
        forecast['GrossProfit_2026'] = forecast['Sales_2026'] * forecast['GrossMargin%_2026']
        forecast['COGS_2026'] = forecast['Sales_2026'] - forecast['GrossProfit_2026']
        
        # STOK HESAPLAMA - İKİ YÖNTEM:
        if stock_change_pct is not None:
            # Yöntem 1: TUTAR BAZLI DEĞİŞİM
            # Her ana grup/ay için 2025 stok tutarını % değişim ile çarp
            # Örnek: %5 azalış (-0.05) → her grubun stoğu %5 azalır
            forecast['Stock_2026'] = forecast['Stock'] * (1 + stock_change_pct)
        else:
            # Yöntem 2: ORAN BAZLI HEDEF
            # 2026 COGS × hedef oran
            forecast['Stock_2026'] = forecast['COGS_2026'] * stock_ratio_target
        
        # Sonuç datasını hazırla
        result = forecast[['Month', 'MainGroup', 'Sales_2026', 'GrossProfit_2026', 
                          'GrossMargin%_2026', 'Stock_2026', 'COGS_2026']].copy()
        result.columns = ['Month', 'MainGroup', 'Sales', 'GrossProfit', 
                         'GrossMargin%', 'Stock', 'COGS']
        result['Year'] = 2026
        
        # Stok/COGS oranı
        result['Stock_COGS_Ratio'] = np.where(
            result['COGS'] > 0,
            result['Stock'] / result['COGS'],
            0
        )
        
        return result
    
    def get_full_data_with_forecast(self, growth_param=0.1, margin_improvement=0.0, stock_ratio_target=1.0, monthly_growth_targets=None, maingroup_growth_targets=None, stock_change_pct=None):
        """2024, 2025 ve 2026 tahminini birleştir"""
        
        forecast_2026 = self.forecast_2026(growth_param, margin_improvement, stock_ratio_target, monthly_growth_targets, maingroup_growth_targets, stock_change_pct)
        
        # 2024-2025 verisini düzenle
        historical = self.data[['Month', 'MainGroup', 'Sales', 'GrossProfit', 
                               'GrossMargin%', 'Stock', 'COGS', 'Stock_COGS_Ratio', 'Year']].copy()
        
        # Birleştir
        full_data = pd.concat([historical, forecast_2026], ignore_index=True)
        
        return full_data
    
    def get_summary_stats(self, data):
        """Özet istatistikler - Haftalık normalize edilmiş stok/SMM oranı dahil"""
        
        summary = {}
        
        # Aylık gün sayıları
        days_in_month = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                         7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
        
        for year in [2024, 2025, 2026]:
            year_data = data[data['Year'] == year].copy()
            
            # Haftalık normalize Stok/SMM hesapla
            # Her ay için: Stok / ((SMM/gün_sayısı)*7)
            year_data['Days'] = year_data['Month'].map(days_in_month)
            year_data['Stock_COGS_Weekly'] = np.where(
                year_data['COGS'] > 0,
                year_data['Stock'] / ((year_data['COGS'] / year_data['Days']) * 7),
                0
            )
            
            summary[year] = {
                'Total_Sales': year_data['Sales'].sum(),
                'Total_GrossProfit': year_data['GrossProfit'].sum(),
                'Avg_GrossMargin%': (year_data['GrossProfit'].sum() / year_data['Sales'].sum() * 100) if year_data['Sales'].sum() > 0 else 0,
                'Avg_Stock': year_data['Stock'].mean(),
                'Avg_Stock_COGS_Ratio': year_data['Stock_COGS_Ratio'].mean(),
                'Avg_Stock_COGS_Weekly': year_data['Stock_COGS_Weekly'].mean()
            }
        
        return summary
    
