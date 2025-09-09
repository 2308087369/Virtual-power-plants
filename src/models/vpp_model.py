"""
虚拟电厂优化模型
VPP Optimization Model

基于 oemof-solph 构建的虚拟电厂能源系统优化模型
"""

import os
import yaml
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# oemof-solph 核心导入
import oemof.solph as solph
from oemof.tools import logger


class VPPOptimizationModel:
    """虚拟电厂优化模型"""
    
    def __init__(self, time_index: pd.DatetimeIndex, config_path: Optional[str] = None):
        """
        初始化优化模型
        
        Args:
            time_index: 时间索引
            config_path: 配置文件路径
        """
        self.time_index = time_index
        self.periods = len(time_index)
        self.config = self._load_config(config_path)
        
        # 模型组件
        self.energy_system = None
        self.components = {}
        
        # 配置日志
        self._setup_logging()
        
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
            print(f"加载配置失败: {e}，使用默认配置")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'energy_resources': {
                'photovoltaic': {
                    'capacity_mw': 50,
                    'variable_cost_yuan_mwh': 5
                },
                'wind': {
                    'capacity_mw': 30,
                    'variable_cost_yuan_mwh': 8
                },
                'gas_turbine': {
                    'capacity_mw': 100,
                    'variable_cost_yuan_mwh': 600,
                    'min_output_ratio': 0.3
                },
                'battery_storage': {
                    'power_capacity_mw': 50,
                    'energy_capacity_mwh': 200,
                    'charge_efficiency': 0.95,
                    'discharge_efficiency': 0.95,
                    'self_discharge_rate': 0.001,
                    'initial_soc': 0.5,
                    'charge_cost_yuan_mwh': 10,
                    'discharge_cost_yuan_mwh': 15
                }
            },
            'adjustable_loads': {
                'chiller': {
                    'rated_power_mw': 20,
                    'min_power_ratio': 0.3,
                    'max_power_ratio': 1.0,
                    'efficiency': 0.85,
                    'operating_cost_yuan_mwh': 50
                },
                'heat_pump': {
                    'rated_power_mw': 15,
                    'min_power_ratio': 0.2,
                    'max_power_ratio': 1.0,
                    'cop': 3.5,
                    'operating_cost_yuan_mwh': 40
                }
            },
            'grid_connection': {
                'max_purchase_mw': 1000,
                'max_sale_mw': 500,
                'sale_price_ratio': 0.95
            }
        }
    
    def _setup_logging(self):
        """设置日志配置"""
        import logging
        
        # 设置根日志级别为INFO，避免DEBUG级别导致的性能问题
        logging.getLogger().setLevel(logging.INFO)
        
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'logs'
        )
        os.makedirs(log_dir, exist_ok=True)
        
        logger.define_logging(
            logpath=log_dir,
            logfile='vpp_optimization.log',
            screen_level=30,  # WARNING及以上
            file_level=20     # INFO及以上
        )
    
    def create_energy_system(self, load_data: pd.Series, pv_data: pd.Series, 
                           wind_data: pd.Series, price_data: pd.Series) -> solph.EnergySystem:
        """
        创建能源系统模型
        
        Args:
            load_data: 负荷需求数据
            pv_data: 光伏发电数据
            wind_data: 风电发电数据
            price_data: 电价数据
            
        Returns:
            构建完成的能源系统
        """
        print("正在创建虚拟电厂能源系统模型...")
        
        # 创建能源系统
        self.energy_system = solph.EnergySystem(
            timeindex=self.time_index,
            infer_last_interval=False
        )
        
        # 创建系统组件
        self._create_buses()
        self._create_load_demand(load_data)
        self._create_renewable_sources(pv_data, wind_data)
        self._create_conventional_generation()
        self._create_energy_storage()
        self._create_adjustable_loads()
        self._create_grid_connection(price_data)
        
        # 添加所有组件到能源系统
        all_components = []
        for component_list in self.components.values():
            if isinstance(component_list, list):
                all_components.extend(component_list)
            else:
                all_components.append(component_list)
        
        self.energy_system.add(*all_components)
        
        print(f"能源系统创建完成，包含 {len(all_components)} 个组件")
        return self.energy_system
    
    def _create_buses(self):
        """创建总线节点"""
        # 电力总线
        bus_electricity = solph.Bus(label="bus_electricity")
        self.components['bus_electricity'] = bus_electricity
    
    def _create_load_demand(self, load_data: pd.Series):
        """创建负荷需求"""
        load_demand = solph.components.Sink(
            label="load_demand",
            inputs={
                self.components['bus_electricity']: solph.Flow(
                    fix=load_data.values,
                    nominal_value=1
                )
            }
        )
        self.components['load_demand'] = load_demand
    
    def _create_renewable_sources(self, pv_data: pd.Series, wind_data: pd.Series):
        """创建可再生能源发电"""
        pv_config = self.config['energy_resources']['photovoltaic']
        wind_config = self.config['energy_resources']['wind']
        
        # 光伏发电
        if max(pv_data.values) > 0:
            pv_source = solph.components.Source(
                label="pv_source",
                outputs={
                    self.components['bus_electricity']: solph.Flow(
                        fix=pv_data.values / max(pv_data.values),
                        nominal_value=max(pv_data.values),
                        variable_costs=pv_config['variable_cost_yuan_mwh']
                    )
                }
            )
        else:
            # 如果光伏数据全为0，创建一个最小容量的源
            pv_source = solph.components.Source(
                label="pv_source",
                outputs={
                    self.components['bus_electricity']: solph.Flow(
                        fix=[0] * self.periods,
                        nominal_value=1,
                        variable_costs=pv_config['variable_cost_yuan_mwh']
                    )
                }
            )
        
        # 风力发电
        if max(wind_data.values) > 0:
            wind_source = solph.components.Source(
                label="wind_source",
                outputs={
                    self.components['bus_electricity']: solph.Flow(
                        fix=wind_data.values / max(wind_data.values),
                        nominal_value=max(wind_data.values),
                        variable_costs=wind_config['variable_cost_yuan_mwh']
                    )
                }
            )
        else:
            # 如果风电数据全为0，创建一个最小容量的源
            wind_source = solph.components.Source(
                label="wind_source",
                outputs={
                    self.components['bus_electricity']: solph.Flow(
                        fix=[0] * self.periods,
                        nominal_value=1,
                        variable_costs=wind_config['variable_cost_yuan_mwh']
                    )
                }
            )
        
        self.components['renewable_sources'] = [pv_source, wind_source]
    
    def _create_conventional_generation(self):
        """创建传统发电设备"""
        gas_config = self.config['energy_resources']['gas_turbine']
        
        # 燃气机组
        gas_turbine = solph.components.Source(
            label="gas_turbine",
            outputs={
                self.components['bus_electricity']: solph.Flow(
                    nominal_value=gas_config['capacity_mw'],
                    variable_costs=gas_config['variable_cost_yuan_mwh'],
                    min=gas_config['min_output_ratio']
                )
            }
        )
        
        self.components['conventional_generation'] = [gas_turbine]
    
    def _create_energy_storage(self):
        """创建储能系统"""
        battery_config = self.config['energy_resources']['battery_storage']
        
        # 获取辅助服务配置
        ancillary_config = battery_config.get('ancillary_services', {})
        freq_reg_config = ancillary_config.get('frequency_regulation', {})
        spin_reserve_config = ancillary_config.get('spinning_reserve', {})
        
        # 简化储能建模：暂时禁用辅助服务以解决约束冲突
        # TODO: 未来需要重新设计辅助服务与储能的耦合约束
        total_power_capacity = battery_config['power_capacity_mw']
        available_power_capacity = total_power_capacity
        
        print(f"储能配置 - 功率容量: {total_power_capacity} MW, 能量容量: {battery_config['energy_capacity_mwh']} MWh")
        
        # 计算综合充电成本（包含循环损耗）
        base_charge_cost = battery_config['charge_cost_yuan_mwh']
        cycle_degradation_cost = battery_config.get('cycle_degradation_cost_yuan_mwh', 0)
        total_charge_cost = base_charge_cost + cycle_degradation_cost
        
        # 储能系统（主要用于能量交易）
        battery_storage = solph.components.GenericStorage(
            label="battery_storage",
            inputs={
                self.components['bus_electricity']: solph.Flow(
                    nominal_value=available_power_capacity,
                    variable_costs=total_charge_cost,
                    max=1.0,  # 强制最大功率约束
                    min=0.0   # 强制最小功率约束
                )
            },
            outputs={
                self.components['bus_electricity']: solph.Flow(
                    nominal_value=available_power_capacity,
                    variable_costs=battery_config['discharge_cost_yuan_mwh'],
                    max=1.0,  # 强制最大功率约束
                    min=0.0   # 强制最小功率约束
                )
            },
            nominal_storage_capacity=battery_config['energy_capacity_mwh'],
            initial_storage_level=battery_config['initial_soc'],
            min_storage_level=battery_config.get('min_soc', 0.1),  # 更保守的最小SOC
            max_storage_level=battery_config.get('max_soc', 0.95),  # 更高的最大SOC
            inflow_conversion_factor=battery_config['charge_efficiency'],
            outflow_conversion_factor=battery_config['discharge_efficiency'],
            loss_rate=battery_config['self_discharge_rate'],
            balanced=True  # 确保储能期初期末状态相等
        )
        
        print(f"设置储能约束 - 充电功率: 0-{available_power_capacity} MW, 放电功率: 0-{available_power_capacity} MW")
        
        storage_components = [battery_storage]
        
        # 暂时禁用辅助服务组件以解决储能约束冲突问题
        # 辅助服务组件作为独立组件会绕过储能的SOC和容量约束
        # TODO: 未来需要实现辅助服务与储能的正确耦合约束
        print("注意：为解决储能约束问题，暂时禁用辅助服务组件")
        
        self.components['energy_storage'] = storage_components
    
    def _create_adjustable_loads(self):
        """创建可调负荷"""
        adjustable_loads_config = self.config.get('adjustable_loads', {})
        
        adjustable_loads = []
        
        # 冷机系统
        if 'chiller' in adjustable_loads_config:
            chiller_config = adjustable_loads_config['chiller']
            
            chiller_load = solph.components.Sink(
                label="chiller_load",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=chiller_config['rated_power_mw'],
                        variable_costs=chiller_config['operating_cost_yuan_mwh'],
                        min=chiller_config['min_power_ratio'],
                        max=chiller_config['max_power_ratio']
                    )
                }
            )
            adjustable_loads.append(chiller_load)
        
        # 热机系统
        if 'heat_pump' in adjustable_loads_config:
            heat_pump_config = adjustable_loads_config['heat_pump']
            
            heat_pump_load = solph.components.Sink(
                label="heat_pump_load",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=heat_pump_config['rated_power_mw'],
                        variable_costs=heat_pump_config['operating_cost_yuan_mwh'],
                        min=heat_pump_config['min_power_ratio'],
                        max=heat_pump_config['max_power_ratio']
                    )
                }
            )
            adjustable_loads.append(heat_pump_load)
        
        self.components['adjustable_loads'] = adjustable_loads
    
    def _create_grid_connection(self, price_data: pd.Series):
        """创建电网连接"""
        grid_config = self.config['grid_connection']
        
        # 电网购电
        grid_source = solph.components.Source(
            label="grid_source",
            outputs={
                self.components['bus_electricity']: solph.Flow(
                    variable_costs=price_data.values,
                    nominal_value=grid_config['max_purchase_mw']
                )
            }
        )
        
        # 电网售电
        grid_sink = solph.components.Sink(
            label="grid_sink",
            inputs={
                self.components['bus_electricity']: solph.Flow(
                    variable_costs=[-p * grid_config['sale_price_ratio'] 
                                  for p in price_data.values],
                    nominal_value=grid_config['max_sale_mw']
                )
            }
        )
        
        self.components['grid_connection'] = [grid_source, grid_sink]
    
    def get_component_by_label(self, label: str):
        """根据标签获取组件"""
        for component in self.energy_system.nodes:
            if component.label == label:
                return component
        return None
    
    def validate_system(self) -> bool:
        """验证能源系统的完整性"""
        if self.energy_system is None:
            print("错误：能源系统未创建")
            return False
        
        # 检查是否有组件
        if len(self.energy_system.nodes) == 0:
            print("错误：能源系统中没有组件")
            return False
        
        # 检查电力总线是否存在
        bus_electricity = self.get_component_by_label("bus_electricity")
        if bus_electricity is None:
            print("错误：缺少电力总线")
            return False
        
        print("能源系统验证通过")
        return True
    
    def get_system_summary(self) -> Dict:
        """获取系统概要信息"""
        if self.energy_system is None:
            return {"error": "能源系统未创建"}
        
        summary = {
            "total_components": len(self.energy_system.nodes),
            "time_periods": self.periods,
            "start_time": str(self.time_index[0]),
            "end_time": str(self.time_index[-1]),
            "components_by_type": {}
        }
        
        # 统计各类组件数量
        for node in self.energy_system.nodes:
            node_type = type(node).__name__
            if node_type not in summary["components_by_type"]:
                summary["components_by_type"][node_type] = 0
            summary["components_by_type"][node_type] += 1
        
        return summary


# 示例使用
if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    
    from data.data_generator import VPPDataGenerator
    
    # 创建数据生成器
    data_generator = VPPDataGenerator()
    load_data, pv_data, wind_data, price_data = data_generator.generate_all_data()
    
    # 创建优化模型
    model = VPPOptimizationModel(data_generator.time_index)
    energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
    
    # 验证系统
    if model.validate_system():
        summary = model.get_system_summary()
        print("\n系统概要:")
        for key, value in summary.items():
            print(f"{key}: {value}")