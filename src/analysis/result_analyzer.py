"""
结果分析器
Result Analyzer

对虚拟电厂优化结果进行经济性和技术性能分析
"""

import os
import yaml
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')

import oemof.solph as solph
from oemof.solph import processing, views


class ResultAnalyzer:
    """优化结果分析器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化结果分析器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.optimization_results = None
        self.energy_system = None
        self.time_index = None
        self.results_df = None
        self.economics = None
        self.technical_metrics = None
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """加载配置文件"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'config', 'system_config.yaml'
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"加载配置失败: {e}")
            return {}
    
    def analyze_results(self, optimization_results: Dict, energy_system: solph.EnergySystem,
                       time_index: pd.DatetimeIndex, price_data: pd.Series) -> Tuple[pd.DataFrame, Dict, Dict]:
        """
        分析优化结果
        
        Args:
            optimization_results: oemof求解结果
            energy_system: 能源系统对象
            time_index: 时间索引
            price_data: 电价数据
            
        Returns:
            (结果数据框, 经济性分析, 技术指标)
        """
        print("\n正在分析优化结果...")
        
        self.optimization_results = optimization_results
        self.energy_system = energy_system
        self.time_index = time_index
        
        # 提取时间序列结果
        self.results_df = self._extract_time_series_results()
        
        # 计算经济性指标
        self.economics = self._calculate_economics(price_data)
        
        # 计算技术性能指标
        self.technical_metrics = self._calculate_technical_metrics()
        
        print("结果分析完成！")
        return self.results_df, self.economics, self.technical_metrics
    
    def _extract_time_series_results(self) -> pd.DataFrame:
        """提取时间序列结果"""
        print("正在提取时间序列数据...")
        
        # 创建结果数据框
        results_df = pd.DataFrame(index=self.time_index)
        
        # 获取各组件的结果
        component_results = {}
        
        # 遍历所有节点，提取结果
        for node in self.energy_system.nodes:
            try:
                node_results = views.node(self.optimization_results, node)
                component_results[node.label] = node_results
            except Exception as e:
                print(f"提取节点 {node.label} 结果时出错: {e}")
                continue
        
        # 提取负荷需求
        if 'load_demand' in component_results:
            load_sequences = component_results['load_demand']['sequences']
            if not load_sequences.empty:
                results_df['load_demand_mw'] = load_sequences.iloc[:, 0].values
        
        # 提取光伏发电
        if 'pv_source' in component_results:
            pv_sequences = component_results['pv_source']['sequences']
            if not pv_sequences.empty:
                results_df['pv_generation_mw'] = pv_sequences.iloc[:, 0].values
        
        # 提取风力发电
        if 'wind_source' in component_results:
            wind_sequences = component_results['wind_source']['sequences']
            if not wind_sequences.empty:
                results_df['wind_generation_mw'] = wind_sequences.iloc[:, 0].values
        
        # 提取燃气机组
        if 'gas_turbine' in component_results:
            gas_sequences = component_results['gas_turbine']['sequences']
            if not gas_sequences.empty:
                results_df['gas_generation_mw'] = gas_sequences.iloc[:, 0].values
        
        # 提取储能系统（支持统一储能和分离式储能）
        battery_charge_mw = None
        battery_discharge_mw = None
        battery_soc = None
        
        # 方式1：统一的battery_storage组件
        if 'battery_storage' in component_results:
            battery_sequences = component_results['battery_storage']['sequences']
            if not battery_sequences.empty:
                # 储能有多列：充电(输入)、放电(输出)、储能状态
                if battery_sequences.shape[1] >= 2:
                    battery_charge = battery_sequences.iloc[:, 0].values  # 充电
                    battery_discharge = battery_sequences.iloc[:, 1].values  # 放电
                    
                    battery_charge_mw = -battery_charge  # 充电为负值
                    battery_discharge_mw = battery_discharge  # 放电为正值
                
                # 储能状态（如果有的话）
                if battery_sequences.shape[1] >= 3:
                    battery_soc = battery_sequences.iloc[:, 2].values
        
        # 方式2：分离式储能组件（battery_charger + battery_discharger + battery_tank）
        if battery_charge_mw is None and battery_discharge_mw is None:
            # 提取充电器数据
            if 'battery_charger' in component_results:
                charger_sequences = component_results['battery_charger']['sequences']
                if not charger_sequences.empty and charger_sequences.shape[1] >= 1:
                    battery_charge_mw = -charger_sequences.iloc[:, 0].values  # 充电为负值
            
            # 提取放电器数据  
            if 'battery_discharger' in component_results:
                discharger_sequences = component_results['battery_discharger']['sequences']
                if not discharger_sequences.empty and discharger_sequences.shape[1] >= 1:
                    battery_discharge_mw = discharger_sequences.iloc[:, 0].values  # 放电为正值
            
            # 提取储能状态
            if 'battery_tank' in component_results:
                tank_sequences = component_results['battery_tank']['sequences']
                if not tank_sequences.empty and tank_sequences.shape[1] >= 1:
                    battery_soc = tank_sequences.iloc[:, 0].values  # SOC状态
        
        # 统一设置储能数据列
        if battery_charge_mw is not None:
            results_df['battery_charge_mw'] = battery_charge_mw
        if battery_discharge_mw is not None:
            results_df['battery_discharge_mw'] = battery_discharge_mw
        if battery_charge_mw is not None and battery_discharge_mw is not None:
            results_df['battery_net_mw'] = battery_discharge_mw + battery_charge_mw  # 注意：charge已经是负值
        if battery_soc is not None:
            results_df['battery_soc'] = battery_soc
        
        # 提取电网交互
        if 'grid_source' in component_results:
            grid_purchase_sequences = component_results['grid_source']['sequences']
            if not grid_purchase_sequences.empty:
                results_df['grid_purchase_mw'] = grid_purchase_sequences.iloc[:, 0].values
        
        if 'grid_sink' in component_results:
            grid_sale_sequences = component_results['grid_sink']['sequences']
            if not grid_sale_sequences.empty:
                results_df['grid_sale_mw'] = grid_sale_sequences.iloc[:, 0].values
        
        # 提取可调负荷
        if 'chiller_load' in component_results:
            chiller_sequences = component_results['chiller_load']['sequences']
            if not chiller_sequences.empty:
                results_df['chiller_load_mw'] = chiller_sequences.iloc[:, 0].values
        
        if 'heat_pump_load' in component_results:
            heat_pump_sequences = component_results['heat_pump_load']['sequences']
            if not heat_pump_sequences.empty:
                results_df['heat_pump_load_mw'] = heat_pump_sequences.iloc[:, 0].values
        
        # 提取辅助服务
        if 'freq_reg_up_service' in component_results:
            freq_reg_up_sequences = component_results['freq_reg_up_service']['sequences']
            if not freq_reg_up_sequences.empty:
                results_df['freq_reg_up_mw'] = freq_reg_up_sequences.iloc[:, 0].values
        
        if 'freq_reg_down_service' in component_results:
            freq_reg_down_sequences = component_results['freq_reg_down_service']['sequences']
            if not freq_reg_down_sequences.empty:
                results_df['freq_reg_down_mw'] = freq_reg_down_sequences.iloc[:, 0].values
        
        if 'spin_reserve_up_service' in component_results:
            spin_reserve_up_sequences = component_results['spin_reserve_up_service']['sequences']
            if not spin_reserve_up_sequences.empty:
                results_df['spin_reserve_up_mw'] = spin_reserve_up_sequences.iloc[:, 0].values
        
        if 'spin_reserve_down_service' in component_results:
            spin_reserve_down_sequences = component_results['spin_reserve_down_service']['sequences']
            if not spin_reserve_down_sequences.empty:
                results_df['spin_reserve_down_mw'] = spin_reserve_down_sequences.iloc[:, 0].values
        
        # 计算衍生指标
        self._calculate_derived_metrics(results_df)
        
        return results_df
    
    def _calculate_derived_metrics(self, results_df: pd.DataFrame):
        """计算衍生指标"""
        # 填充缺失值
        for col in results_df.columns:
            if results_df[col].isna().all():
                results_df[col] = 0.0
            else:
                results_df[col] = results_df[col].fillna(0.0)
        
        # 计算总发电量
        generation_cols = [col for col in results_df.columns if 'generation' in col]
        if generation_cols:
            results_df['total_renewable_mw'] = results_df[generation_cols].sum(axis=1)
        else:
            results_df['total_renewable_mw'] = 0.0
        
        # 计算净电网交互
        if 'grid_purchase_mw' in results_df.columns and 'grid_sale_mw' in results_df.columns:
            results_df['grid_net_mw'] = results_df['grid_purchase_mw'] - results_df['grid_sale_mw']
        elif 'grid_purchase_mw' in results_df.columns:
            results_df['grid_net_mw'] = results_df['grid_purchase_mw']
        elif 'grid_sale_mw' in results_df.columns:
            results_df['grid_net_mw'] = -results_df['grid_sale_mw']
        else:
            results_df['grid_net_mw'] = 0.0
        
        # 计算总供应
        supply_cols = generation_cols + ['gas_generation_mw', 'battery_net_mw', 'grid_net_mw']
        available_supply_cols = [col for col in supply_cols if col in results_df.columns]
        
        if available_supply_cols:
            results_df['total_supply_mw'] = results_df[available_supply_cols].sum(axis=1)
        else:
            results_df['total_supply_mw'] = 0.0
        
        # 计算功率平衡
        if 'load_demand_mw' in results_df.columns:
            results_df['power_balance_mw'] = results_df['total_supply_mw'] - results_df['load_demand_mw']
        else:
            results_df['power_balance_mw'] = results_df['total_supply_mw']
    
    def _calculate_economics(self, price_data: pd.Series) -> Dict[str, float]:
        """计算经济性指标"""
        print("正在计算经济性指标...")
        
        if self.results_df is None:
            return {}
        
        economics = {}
        
        # 获取成本参数
        energy_config = self.config.get('energy_resources', {})
        
        # 可再生能源成本
        pv_cost_rate = energy_config.get('photovoltaic', {}).get('variable_cost_yuan_mwh', 5)
        wind_cost_rate = energy_config.get('wind', {}).get('variable_cost_yuan_mwh', 8)
        
        pv_energy = self.results_df.get('pv_generation_mw', pd.Series(0, index=self.time_index)).sum()
        wind_energy = self.results_df.get('wind_generation_mw', pd.Series(0, index=self.time_index)).sum()
        
        economics['pv_cost_yuan'] = pv_energy * pv_cost_rate
        economics['wind_cost_yuan'] = wind_energy * wind_cost_rate
        economics['renewable_cost_yuan'] = economics['pv_cost_yuan'] + economics['wind_cost_yuan']
        
        # 传统发电成本
        gas_cost_rate = energy_config.get('gas_turbine', {}).get('variable_cost_yuan_mwh', 600)
        gas_energy = self.results_df.get('gas_generation_mw', pd.Series(0, index=self.time_index)).sum()
        economics['gas_cost_yuan'] = gas_energy * gas_cost_rate
        
        # 储能成本（包含循环损耗）
        battery_config = energy_config.get('battery_storage', {})
        charge_cost_rate = battery_config.get('charge_cost_yuan_mwh', 8)
        discharge_cost_rate = battery_config.get('discharge_cost_yuan_mwh', 12)
        cycle_degradation_cost_rate = battery_config.get('cycle_degradation_cost_yuan_mwh', 15)
        
        battery_charge_energy = abs(self.results_df.get('battery_charge_mw', pd.Series(0, index=self.time_index))).sum()
        battery_discharge_energy = self.results_df.get('battery_discharge_mw', pd.Series(0, index=self.time_index)).sum()
        
        # 基本运行成本
        economics['battery_charge_cost_yuan'] = battery_charge_energy * charge_cost_rate
        economics['battery_discharge_cost_yuan'] = battery_discharge_energy * discharge_cost_rate
        
        # 循环损耗成本（基于充电量计算）
        economics['battery_cycle_degradation_cost_yuan'] = battery_charge_energy * cycle_degradation_cost_rate
        
        # 检查深度放电惩罚
        battery_soc = self.results_df.get('battery_soc', pd.Series(0.5, index=self.time_index))
        deep_discharge_penalty_rate = battery_config.get('deep_discharge_penalty_yuan_mwh', 50)
        deep_discharge_hours = (battery_soc < 0.2).sum()  # SOC低于20%的小时数
        economics['battery_deep_discharge_penalty_yuan'] = deep_discharge_hours * deep_discharge_penalty_rate
        
        # 总储能成本
        economics['battery_total_cost_yuan'] = (
            economics['battery_charge_cost_yuan'] + 
            economics['battery_discharge_cost_yuan'] + 
            economics['battery_cycle_degradation_cost_yuan'] +
            economics['battery_deep_discharge_penalty_yuan']
        )
        
        # 可调负荷成本
        adjustable_loads_config = self.config.get('adjustable_loads', {})
        
        # 冷机成本
        chiller_cost_rate = adjustable_loads_config.get('chiller', {}).get('operating_cost_yuan_mwh', 50)
        chiller_energy = self.results_df.get('chiller_load_mw', pd.Series(0, index=self.time_index)).sum()
        economics['chiller_cost_yuan'] = chiller_energy * chiller_cost_rate
        
        # 热机成本
        heat_pump_cost_rate = adjustable_loads_config.get('heat_pump', {}).get('operating_cost_yuan_mwh', 40)
        heat_pump_energy = self.results_df.get('heat_pump_load_mw', pd.Series(0, index=self.time_index)).sum()
        economics['heat_pump_cost_yuan'] = heat_pump_energy * heat_pump_cost_rate
        
        economics['adjustable_loads_cost_yuan'] = economics['chiller_cost_yuan'] + economics['heat_pump_cost_yuan']
        
        # 辅助服务收入
        battery_config = self.config.get('energy_resources', {}).get('battery_storage', {})
        ancillary_config = battery_config.get('ancillary_services', {})
        
        # 调频服务收入
        freq_reg_config = ancillary_config.get('frequency_regulation', {})
        if freq_reg_config.get('enable', False):
            freq_reg_up_capacity = self.results_df.get('freq_reg_up_mw', pd.Series(0, index=self.time_index)).sum()
            freq_reg_down_capacity = self.results_df.get('freq_reg_down_mw', pd.Series(0, index=self.time_index)).sum()
            
            freq_reg_up_price = freq_reg_config.get('up_price_yuan_mw', 80)
            freq_reg_down_price = freq_reg_config.get('down_price_yuan_mw', 70)
            
            economics['freq_reg_up_revenue_yuan'] = freq_reg_up_capacity * freq_reg_up_price
            economics['freq_reg_down_revenue_yuan'] = freq_reg_down_capacity * freq_reg_down_price
        else:
            economics['freq_reg_up_revenue_yuan'] = 0
            economics['freq_reg_down_revenue_yuan'] = 0
        
        # 备用服务收入
        spin_reserve_config = ancillary_config.get('spinning_reserve', {})
        if spin_reserve_config.get('enable', False):
            spin_reserve_up_capacity = self.results_df.get('spin_reserve_up_mw', pd.Series(0, index=self.time_index)).sum()
            spin_reserve_down_capacity = self.results_df.get('spin_reserve_down_mw', pd.Series(0, index=self.time_index)).sum()
            
            spin_reserve_up_price = spin_reserve_config.get('up_price_yuan_mw', 60)
            spin_reserve_down_price = spin_reserve_config.get('down_price_yuan_mw', 50)
            
            economics['spin_reserve_up_revenue_yuan'] = spin_reserve_up_capacity * spin_reserve_up_price
            economics['spin_reserve_down_revenue_yuan'] = spin_reserve_down_capacity * spin_reserve_down_price
        else:
            economics['spin_reserve_up_revenue_yuan'] = 0
            economics['spin_reserve_down_revenue_yuan'] = 0
        
        # 辅助服务总收入
        economics['ancillary_services_revenue_yuan'] = (
            economics['freq_reg_up_revenue_yuan'] + economics['freq_reg_down_revenue_yuan'] +
            economics['spin_reserve_up_revenue_yuan'] + economics['spin_reserve_down_revenue_yuan']
        )
        
        # 电网交易
        grid_purchase_energy = self.results_df.get('grid_purchase_mw', pd.Series(0, index=self.time_index))
        grid_sale_energy = self.results_df.get('grid_sale_mw', pd.Series(0, index=self.time_index))
        
        # 确保价格数据长度匹配
        if len(price_data) != len(grid_purchase_energy):
            print(f"警告：电价数据长度({len(price_data)})与结果数据长度({len(grid_purchase_energy)})不匹配")
            # 使用平均电价
            avg_price = price_data.mean()
            economics['grid_purchase_cost_yuan'] = grid_purchase_energy.sum() * avg_price
            economics['grid_sale_revenue_yuan'] = grid_sale_energy.sum() * avg_price * 0.95
        else:
            economics['grid_purchase_cost_yuan'] = (grid_purchase_energy * price_data).sum()
            economics['grid_sale_revenue_yuan'] = (grid_sale_energy * price_data * 0.95).sum()
        
        # 总成本和收益
        economics['total_generation_cost_yuan'] = (
            economics['renewable_cost_yuan'] + 
            economics['gas_cost_yuan'] + 
            economics['battery_total_cost_yuan'] +
            economics['adjustable_loads_cost_yuan']
        )
        
        economics['total_cost_yuan'] = (
            economics['total_generation_cost_yuan'] + 
            economics['grid_purchase_cost_yuan']
        )
        
        economics['total_revenue_yuan'] = economics['grid_sale_revenue_yuan'] + economics['ancillary_services_revenue_yuan']
        economics['net_cost_yuan'] = economics['total_cost_yuan'] - economics['total_revenue_yuan']
        
        # 平均指标
        total_demand = self.results_df.get('load_demand_mw', pd.Series(0, index=self.time_index)).sum()
        if total_demand > 0:
            economics['average_cost_yuan_per_mwh'] = economics['net_cost_yuan'] / total_demand
        else:
            economics['average_cost_yuan_per_mwh'] = 0
        
        economics['average_electricity_price_yuan_mwh'] = price_data.mean()
        
        return economics
    
    def _calculate_technical_metrics(self) -> Dict[str, Any]:
        """计算技术性能指标"""
        print("正在计算技术性能指标...")
        
        if self.results_df is None:
            return {}
        
        metrics = {}
        
        # 负荷特性
        load_demand = self.results_df.get('load_demand_mw', pd.Series(0, index=self.time_index))
        metrics['load_peak_mw'] = load_demand.max()
        metrics['load_valley_mw'] = load_demand.min()
        metrics['load_average_mw'] = load_demand.mean()
        metrics['load_total_mwh'] = load_demand.sum()
        metrics['load_factor'] = metrics['load_average_mw'] / metrics['load_peak_mw'] if metrics['load_peak_mw'] > 0 else 0
        
        # 可再生能源指标
        pv_generation = self.results_df.get('pv_generation_mw', pd.Series(0, index=self.time_index))
        wind_generation = self.results_df.get('wind_generation_mw', pd.Series(0, index=self.time_index))
        total_renewable = pv_generation + wind_generation
        
        metrics['pv_generation_mwh'] = pv_generation.sum()
        metrics['wind_generation_mwh'] = wind_generation.sum()
        metrics['total_renewable_mwh'] = total_renewable.sum()
        
        # 可再生能源渗透率
        total_generation = (
            total_renewable.sum() + 
            self.results_df.get('gas_generation_mw', pd.Series(0, index=self.time_index)).sum()
        )
        
        if total_generation > 0:
            metrics['renewable_penetration_ratio'] = metrics['total_renewable_mwh'] / total_generation
        else:
            metrics['renewable_penetration_ratio'] = 0
        
        # 储能系统指标
        battery_charge = abs(self.results_df.get('battery_charge_mw', pd.Series(0, index=self.time_index)))
        battery_discharge = self.results_df.get('battery_discharge_mw', pd.Series(0, index=self.time_index))
        
        metrics['battery_charge_mwh'] = battery_charge.sum()
        metrics['battery_discharge_mwh'] = battery_discharge.sum()
        
        if metrics['battery_charge_mwh'] > 0:
            metrics['battery_round_trip_efficiency'] = metrics['battery_discharge_mwh'] / metrics['battery_charge_mwh']
        else:
            metrics['battery_round_trip_efficiency'] = 0
        
        # 电网交互指标
        grid_purchase = self.results_df.get('grid_purchase_mw', pd.Series(0, index=self.time_index))
        grid_sale = self.results_df.get('grid_sale_mw', pd.Series(0, index=self.time_index))
        
        metrics['grid_purchase_mwh'] = grid_purchase.sum()
        metrics['grid_sale_mwh'] = grid_sale.sum()
        metrics['net_grid_purchase_mwh'] = metrics['grid_purchase_mwh'] - metrics['grid_sale_mwh']
        
        # 可调负荷指标
        chiller_load = self.results_df.get('chiller_load_mw', pd.Series(0, index=self.time_index))
        heat_pump_load = self.results_df.get('heat_pump_load_mw', pd.Series(0, index=self.time_index))
        
        metrics['chiller_consumption_mwh'] = chiller_load.sum()
        metrics['heat_pump_consumption_mwh'] = heat_pump_load.sum()
        metrics['total_adjustable_loads_mwh'] = metrics['chiller_consumption_mwh'] + metrics['heat_pump_consumption_mwh']
        
        # 可调负荷参与率
        if metrics['load_total_mwh'] > 0:
            metrics['adjustable_load_ratio'] = metrics['total_adjustable_loads_mwh'] / metrics['load_total_mwh']
        else:
            metrics['adjustable_load_ratio'] = 0
        
        # 辅助服务指标
        freq_reg_up_capacity = self.results_df.get('freq_reg_up_mw', pd.Series(0, index=self.time_index))
        freq_reg_down_capacity = self.results_df.get('freq_reg_down_mw', pd.Series(0, index=self.time_index))
        spin_reserve_up_capacity = self.results_df.get('spin_reserve_up_mw', pd.Series(0, index=self.time_index))
        spin_reserve_down_capacity = self.results_df.get('spin_reserve_down_mw', pd.Series(0, index=self.time_index))
        
        metrics['freq_reg_up_avg_mw'] = freq_reg_up_capacity.mean()
        metrics['freq_reg_down_avg_mw'] = freq_reg_down_capacity.mean()
        metrics['spin_reserve_up_avg_mw'] = spin_reserve_up_capacity.mean()
        metrics['spin_reserve_down_avg_mw'] = spin_reserve_down_capacity.mean()
        
        # 辅助服务总容量
        metrics['total_ancillary_services_mw'] = (
            metrics['freq_reg_up_avg_mw'] + metrics['freq_reg_down_avg_mw'] +
            metrics['spin_reserve_up_avg_mw'] + metrics['spin_reserve_down_avg_mw']
        )
        
        # 辅助服务参与率（相对于储能容量）
        battery_config = self.config.get('energy_resources', {}).get('battery_storage', {})
        battery_capacity = battery_config.get('power_capacity_mw', 50)
        if battery_capacity > 0:
            metrics['ancillary_services_participation_ratio'] = metrics['total_ancillary_services_mw'] / battery_capacity
        else:
            metrics['ancillary_services_participation_ratio'] = 0
        
        # 自给自足率
        if metrics['load_total_mwh'] > 0:
            self_supply = metrics['total_renewable_mwh'] + self.results_df.get('gas_generation_mw', pd.Series(0, index=self.time_index)).sum()
            metrics['self_sufficiency_ratio'] = min(self_supply / metrics['load_total_mwh'], 1.0)
        else:
            metrics['self_sufficiency_ratio'] = 0
        
        # 功率平衡指标
        power_balance = self.results_df.get('power_balance_mw', pd.Series(0, index=self.time_index))
        metrics['max_power_imbalance_mw'] = abs(power_balance).max()
        metrics['average_power_imbalance_mw'] = abs(power_balance).mean()
        
        # 系统灵活性指标
        total_supply = self.results_df.get('total_supply_mw', pd.Series(0, index=self.time_index))
        if len(total_supply) > 1:
            supply_variability = total_supply.std()
            load_variability = load_demand.std()
            if load_variability > 0:
                metrics['supply_flexibility_index'] = supply_variability / load_variability
            else:
                metrics['supply_flexibility_index'] = 0
        else:
            metrics['supply_flexibility_index'] = 0
        
        return metrics
    
    def generate_summary_report(self) -> str:
        """生成汇总报告"""
        if self.results_df is None or self.economics is None or self.technical_metrics is None:
            return "错误：尚未完成结果分析"
        
        report_lines = []
        report_lines.append("="*80)
        report_lines.append(" " * 25 + "虚拟电厂调度优化结果报告")
        report_lines.append("="*80)
        
        # 基本信息
        report_lines.append("\n【基本信息】")
        report_lines.append(f"优化时间段: {len(self.results_df)} 小时")
        report_lines.append(f"优化开始时间: {self.time_index[0]}")
        report_lines.append(f"优化结束时间: {self.time_index[-1]}")
        
        # 负荷特性
        report_lines.append("\n【负荷特性】")
        report_lines.append(f"总负荷需求: {self.technical_metrics['load_total_mwh']:.2f} MWh")
        report_lines.append(f"负荷峰值: {self.technical_metrics['load_peak_mw']:.2f} MW")
        report_lines.append(f"负荷谷值: {self.technical_metrics['load_valley_mw']:.2f} MW")
        report_lines.append(f"负荷率: {self.technical_metrics['load_factor']:.3f}")
        
        # 发电结构
        report_lines.append("\n【发电结构】")
        report_lines.append(f"光伏发电量: {self.technical_metrics['pv_generation_mwh']:.2f} MWh")
        report_lines.append(f"风力发电量: {self.technical_metrics['wind_generation_mwh']:.2f} MWh")
        report_lines.append(f"可再生能源总量: {self.technical_metrics['total_renewable_mwh']:.2f} MWh")
        report_lines.append(f"可再生能源渗透率: {self.technical_metrics['renewable_penetration_ratio']:.1%}")
        
        # 储能系统
        report_lines.append("\n【储能系统】")
        report_lines.append(f"储能充电量: {self.technical_metrics['battery_charge_mwh']:.2f} MWh")
        report_lines.append(f"储能放电量: {self.technical_metrics['battery_discharge_mwh']:.2f} MWh")
        report_lines.append(f"储能往返效率: {self.technical_metrics['battery_round_trip_efficiency']:.1%}")
        
        # 电网交互
        report_lines.append("\n【电网交互】")
        report_lines.append(f"电网购电量: {self.technical_metrics['grid_purchase_mwh']:.2f} MWh")
        report_lines.append(f"电网售电量: {self.technical_metrics['grid_sale_mwh']:.2f} MWh")
        report_lines.append(f"净购电量: {self.technical_metrics['net_grid_purchase_mwh']:.2f} MWh")
        
        # 可调负荷
        if 'chiller_consumption_mwh' in self.technical_metrics or 'heat_pump_consumption_mwh' in self.technical_metrics:
            report_lines.append("\n【可调负荷】")
            if 'chiller_consumption_mwh' in self.technical_metrics:
                report_lines.append(f"冷机用电量: {self.technical_metrics['chiller_consumption_mwh']:.2f} MWh")
            if 'heat_pump_consumption_mwh' in self.technical_metrics:
                report_lines.append(f"热机用电量: {self.technical_metrics['heat_pump_consumption_mwh']:.2f} MWh")
            if 'total_adjustable_loads_mwh' in self.technical_metrics:
                report_lines.append(f"可调负荷总量: {self.technical_metrics['total_adjustable_loads_mwh']:.2f} MWh")
            if 'adjustable_load_ratio' in self.technical_metrics:
                report_lines.append(f"可调负荷参与率: {self.technical_metrics['adjustable_load_ratio']:.1%}")
        
        # 辅助服务
        if 'total_ancillary_services_mw' in self.technical_metrics and self.technical_metrics['total_ancillary_services_mw'] > 0:
            report_lines.append("\n【辅助服务】")
            if 'freq_reg_up_avg_mw' in self.technical_metrics:
                report_lines.append(f"向上调频平均容量: {self.technical_metrics['freq_reg_up_avg_mw']:.2f} MW")
            if 'freq_reg_down_avg_mw' in self.technical_metrics:
                report_lines.append(f"向下调频平均容量: {self.technical_metrics['freq_reg_down_avg_mw']:.2f} MW")
            if 'spin_reserve_up_avg_mw' in self.technical_metrics:
                report_lines.append(f"向上备用平均容量: {self.technical_metrics['spin_reserve_up_avg_mw']:.2f} MW")
            if 'spin_reserve_down_avg_mw' in self.technical_metrics:
                report_lines.append(f"向下备用平均容量: {self.technical_metrics['spin_reserve_down_avg_mw']:.2f} MW")
            if 'total_ancillary_services_mw' in self.technical_metrics:
                report_lines.append(f"辅助服务总容量: {self.technical_metrics['total_ancillary_services_mw']:.2f} MW")
            if 'ancillary_services_participation_ratio' in self.technical_metrics:
                report_lines.append(f"辅助服务参与率: {self.technical_metrics['ancillary_services_participation_ratio']:.1%}")
        
        # 经济性分析
        report_lines.append("\n【经济性分析】")
        report_lines.append(f"总运行成本: {self.economics['total_cost_yuan']:,.2f} 元")
        if 'ancillary_services_revenue_yuan' in self.economics and self.economics['ancillary_services_revenue_yuan'] > 0:
            report_lines.append(f"辅助服务收入: {self.economics['ancillary_services_revenue_yuan']:,.2f} 元")
        report_lines.append(f"总售电收入: {self.economics['total_revenue_yuan']:,.2f} 元")
        report_lines.append(f"净运行成本: {self.economics['net_cost_yuan']:,.2f} 元")
        report_lines.append(f"平均电价: {self.economics['average_electricity_price_yuan_mwh']:.2f} 元/MWh")
        report_lines.append(f"平均供电成本: {self.economics['average_cost_yuan_per_mwh']:.2f} 元/MWh")
        
        # 系统性能
        report_lines.append("\n【系统性能】")
        report_lines.append(f"自给自足率: {self.technical_metrics['self_sufficiency_ratio']:.1%}")
        report_lines.append(f"最大功率不平衡: {self.technical_metrics['max_power_imbalance_mw']:.6f} MW")
        report_lines.append(f"平均功率不平衡: {self.technical_metrics['average_power_imbalance_mw']:.6f} MW")
        
        report_lines.append("\n" + "="*80)
        
        return "\n".join(report_lines)
    
    def save_results(self, output_dir: str = "outputs") -> Dict[str, str]:
        """
        保存分析结果
        
        Args:
            output_dir: 输出目录
            
        Returns:
            保存的文件路径字典
        """
        if self.results_df is None:
            print("错误：没有可保存的结果")
            return {}
        
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        saved_files = {}
        
        # 保存时间序列结果
        results_file = os.path.join(output_dir, f"optimization_results_{timestamp}.csv")
        self.results_df.to_csv(results_file, index=True, encoding='utf-8-sig')
        saved_files['results'] = results_file
        
        # 保存经济性分析
        if self.economics:
            economics_file = os.path.join(output_dir, f"economics_analysis_{timestamp}.csv")
            economics_df = pd.DataFrame(list(self.economics.items()), columns=['指标', '数值'])
            economics_df.to_csv(economics_file, index=False, encoding='utf-8-sig')
            saved_files['economics'] = economics_file
        
        # 保存技术指标
        if self.technical_metrics:
            metrics_file = os.path.join(output_dir, f"technical_metrics_{timestamp}.csv")
            metrics_df = pd.DataFrame(list(self.technical_metrics.items()), columns=['指标', '数值'])
            metrics_df.to_csv(metrics_file, index=False, encoding='utf-8-sig')
            saved_files['metrics'] = metrics_file
        
        # 保存汇总报告
        report_file = os.path.join(output_dir, f"summary_report_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_summary_report())
        saved_files['report'] = report_file
        
        print(f"分析结果已保存到 {output_dir} 目录")
        return saved_files
    
    def save_results_to_session(self, session_context) -> Dict[str, str]:
        """
        保存分析结果到会话目录
        
        Args:
            session_context: 会话上下文
            
        Returns:
            保存的文件路径字典
        """
        if self.results_df is None:
            print("错误：没有可保存的结果")
            return {}
        
        saved_files = {}
        
        # 保存时间序列结果
        results_path = session_context.save_file(
            'optimization_results', 'optimization_results.csv', self.results_df
        )
        saved_files['results'] = str(results_path)
        
        # 保存经济性分析
        if self.economics:
            economics_df = pd.DataFrame(list(self.economics.items()), columns=['指标', '数值'])
            economics_path = session_context.save_file(
                'economics_analysis', 'economics_analysis.csv', economics_df
            )
            saved_files['economics'] = str(economics_path)
        
        # 保存技术指标
        if self.technical_metrics:
            metrics_df = pd.DataFrame(list(self.technical_metrics.items()), columns=['指标', '数值'])
            metrics_path = session_context.save_file(
                'technical_metrics', 'technical_metrics.csv', metrics_df
            )
            saved_files['metrics'] = str(metrics_path)
        
        # 保存汇总报告
        report_content = self.generate_summary_report()
        report_path = session_context.save_file(
            'summary_report', 'summary_report.txt', report_content
        )
        saved_files['report'] = str(report_path)
        
        return saved_files


# 示例使用
if __name__ == "__main__":
    print("结果分析器模块已创建完成")