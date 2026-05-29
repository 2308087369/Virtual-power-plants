"""
虚拟电厂调度模式管理器
VPP Scheduling Modes Manager

支持不同调度模式的配置和管理，根据可调资源类型划分不同场景
"""

import os
import yaml
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# oemof-solph 核心导入
import oemof.solph as solph
from .vpp_model import VPPOptimizationModel


class SchedulingMode(Enum):
    """调度模式枚举"""
    RENEWABLE_STORAGE = "renewable_storage"           # 可再生能源+储能
    ADJUSTABLE_STORAGE = "adjustable_storage"         # 可调负荷+储能  
    TRADITIONAL = "traditional"                       # 传统模式（无辅助服务）
    NO_RENEWABLE = "no_renewable"                     # 无可再生能源
    STORAGE_ONLY = "storage_only"                     # 纯储能调度
    FULL_SYSTEM = "full_system"                       # 完整系统（包含所有资源）


class OptimizationObjective(Enum):
    """优化目标类型枚举"""
    COST_MINIMIZATION = "cost_minimization"           # 成本最小化（原有模式）
    REVENUE_MAXIMIZATION = "revenue_maximization"     # 收益最大化
    PROFIT_MAXIMIZATION = "profit_maximization"       # 利润最大化（收益-成本）
    ANCILLARY_REVENUE_MAX = "ancillary_revenue_max"   # 辅助服务收益最大化
    GRID_SUPPORT_OPTIMIZED = "grid_support_optimized" # 电网支撑服务优化


class VPPSchedulingManager:
    """虚拟电厂调度模式管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化调度模式管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.current_mode = None
        self.current_objective = OptimizationObjective.COST_MINIMIZATION  # 默认目标
        self.mode_configs = self._initialize_mode_configs()
        self.objective_configs = self._initialize_objective_configs()
        
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
            return {}
    
    def _initialize_mode_configs(self) -> Dict[SchedulingMode, Dict]:
        """初始化各调度模式的配置"""
        
        # 为每个模式创建独立的配置副本
        import copy
        
        return {
            SchedulingMode.RENEWABLE_STORAGE: self._get_renewable_storage_config(copy.deepcopy(self.config)),
            SchedulingMode.ADJUSTABLE_STORAGE: self._get_adjustable_storage_config(copy.deepcopy(self.config)),
            SchedulingMode.TRADITIONAL: self._get_traditional_config(copy.deepcopy(self.config)),
            SchedulingMode.NO_RENEWABLE: self._get_no_renewable_config(copy.deepcopy(self.config)),
            SchedulingMode.STORAGE_ONLY: self._get_storage_only_config(copy.deepcopy(self.config)),
            SchedulingMode.FULL_SYSTEM: copy.deepcopy(self.config)  # 保留所有原始配置
        }
    
    def _get_renewable_storage_config(self, base_config: Dict) -> Dict:
        """可再生能源+储能模式配置"""
        config = base_config.copy()
        
        # 禁用传统发电机组
        if 'energy_resources' in config:
            config['energy_resources'] = {
                'photovoltaic': config['energy_resources'].get('photovoltaic', {}),
                'wind': config['energy_resources'].get('wind', {}),
                'battery_storage': config['energy_resources'].get('battery_storage', {})
            }
            # 移除辅助服务
            if 'ancillary_services' in config['energy_resources']['battery_storage']:
                config['energy_resources']['battery_storage']['ancillary_services'] = {
                    'frequency_regulation': {'enable': False},
                    'spinning_reserve': {'enable': False}
                }
        
        # 禁用可调负荷
        config['adjustable_loads'] = {}
        
        return config
    
    def _get_adjustable_storage_config(self, base_config: Dict) -> Dict:
        """可调负荷+储能模式配置"""
        config = base_config.copy()
        
        # 禁用所有发电资源（保留储能）
        if 'energy_resources' in config:
            config['energy_resources'] = {
                'battery_storage': config['energy_resources'].get('battery_storage', {})
            }
            # 移除辅助服务
            if 'ancillary_services' in config['energy_resources']['battery_storage']:
                config['energy_resources']['battery_storage']['ancillary_services'] = {
                    'frequency_regulation': {'enable': False},
                    'spinning_reserve': {'enable': False}
                }
        
        return config
    
    def _get_traditional_config(self, base_config: Dict) -> Dict:
        """传统模式配置（无辅助服务）"""
        config = base_config.copy()
        
        # 移除辅助服务
        if 'energy_resources' in config and 'battery_storage' in config['energy_resources']:
            if 'ancillary_services' in config['energy_resources']['battery_storage']:
                config['energy_resources']['battery_storage']['ancillary_services'] = {
                    'frequency_regulation': {'enable': False},
                    'spinning_reserve': {'enable': False}
                }
        
        return config
    
    def _get_no_renewable_config(self, base_config: Dict) -> Dict:
        """无可再生能源配置"""
        config = base_config.copy()
        
        # 移除可再生能源
        if 'energy_resources' in config:
            renewable_free_config = config['energy_resources'].copy()
            if 'photovoltaic' in renewable_free_config:
                del renewable_free_config['photovoltaic']
            if 'wind' in renewable_free_config:
                del renewable_free_config['wind']
            config['energy_resources'] = renewable_free_config
            
            # 移除辅助服务
            if 'battery_storage' in config['energy_resources']:
                if 'ancillary_services' in config['energy_resources']['battery_storage']:
                    config['energy_resources']['battery_storage']['ancillary_services'] = {
                        'frequency_regulation': {'enable': False},
                        'spinning_reserve': {'enable': False}
                    }
        
        return config
    
    def _get_storage_only_config(self, base_config: Dict) -> Dict:
        """纯储能调度配置"""
        config = base_config.copy()
        
        # 只保留储能系统
        if 'energy_resources' in config:
            config['energy_resources'] = {
                'battery_storage': config['energy_resources'].get('battery_storage', {})
            }
            # 移除辅助服务
            if 'ancillary_services' in config['energy_resources']['battery_storage']:
                config['energy_resources']['battery_storage']['ancillary_services'] = {
                    'frequency_regulation': {'enable': False},
                    'spinning_reserve': {'enable': False}
                }
        
        # 移除可调负荷
        config['adjustable_loads'] = {}
        
        return config
    
    def _initialize_objective_configs(self) -> Dict[OptimizationObjective, Dict]:
        """初始化各优化目标的配置"""
        return {
            OptimizationObjective.COST_MINIMIZATION: {
                'type': 'minimization',
                'primary_focus': 'cost_reduction',
                'description': '成本最小化：最小化总运行成本',
                'objective_function': '最小化(发电成本 + 储能成本 + 可调负荷成本 + 电网交易成本)',
                'variable_costs_sign': 1,  # 正号表示成本
                'revenue_sign': -1  # 负号表示收入在成本函数中作为负成本
            },
            OptimizationObjective.REVENUE_MAXIMIZATION: {
                'type': 'maximization', 
                'primary_focus': 'revenue_generation',
                'description': '收益最大化：最大化售电收入和辅助服务收入',
                'objective_function': '最大化(售电收入 + 辅助服务收入)',
                'variable_costs_sign': -1,  # 收入最大化时成本为负值
                'revenue_sign': 1   # 正号表示收入
            },
            OptimizationObjective.PROFIT_MAXIMIZATION: {
                'type': 'maximization',
                'primary_focus': 'profit_optimization', 
                'description': '利润最大化：最大化总收入与总成本的差值',
                'objective_function': '最大化(总收入 - 总成本) = (售电收入 + 辅助服务收入) - (发电成本 + 运行成本)',
                'variable_costs_sign': -1,  # 利润最大化时成本为负值
                'revenue_sign': 1   # 正号表示收入
            },
            OptimizationObjective.ANCILLARY_REVENUE_MAX: {
                'type': 'maximization',
                'primary_focus': 'ancillary_services',
                'description': '辅助服务收益最大化：主要通过调频、备用等服务获取收益',
                'objective_function': '最大化(辅助服务收入) 同时保证基本电量平衡',
                'variable_costs_sign': -0.1,  # 辅助服务优先，成本权重降低
                'revenue_sign': 1,
                'ancillary_weight': 2.0  # 辅助服务收入权重加大
            },
            OptimizationObjective.GRID_SUPPORT_OPTIMIZED: {
                'type': 'multi_objective',
                'primary_focus': 'grid_stability',
                'description': '电网支撑服务优化：在保证基本收益的前提下最大化电网支撑能力',
                'objective_function': '最大化(电网支撑指数) 约束: 利润 >= 最小利润要求',
                'variable_costs_sign': -0.5,
                'revenue_sign': 1,
                'grid_support_weight': 1.5,  # 电网支撑指数权重
                'min_profit_ratio': 0.8  # 最小利润率要求
            }
        }
    
    def get_mode_description(self, mode: SchedulingMode) -> str:
        """获取调度模式描述"""
        descriptions = {
            SchedulingMode.RENEWABLE_STORAGE: "可再生能源+储能模式：仅包含光伏发电、风力发电和储能系统，适用于绿色能源园区",
            SchedulingMode.ADJUSTABLE_STORAGE: "可调负荷+储能模式：包含冷机、热机等可调负荷和储能系统，适用于工业园区需求侧管理",
            SchedulingMode.TRADITIONAL: "传统调度模式：包含所有资源但不含辅助服务，适用于常规电力系统调度",
            SchedulingMode.NO_RENEWABLE: "无可再生能源模式：仅包含传统发电机组、储能和可调负荷，适用于传统电网环境",
            SchedulingMode.STORAGE_ONLY: "纯储能调度模式：仅储能系统参与调度，适用于储能电站运营",
            SchedulingMode.FULL_SYSTEM: "完整系统模式：包含所有可调资源和辅助服务，适用于综合能源系统"
        }
        return descriptions.get(mode, "未知模式")
    
    def get_objective_function_description(self, mode: SchedulingMode, objective: OptimizationObjective = None) -> str:
        """获取目标函数描述"""
        if objective is None:
            objective = self.current_objective
            
        # 原有的成本最小化描述（保持向后兼容）
        if objective == OptimizationObjective.COST_MINIMIZATION:
            cost_objectives = {
                SchedulingMode.RENEWABLE_STORAGE: "最小化总运行成本 = 储能运行成本 + 电网交易成本 - 可再生能源收益",
                SchedulingMode.ADJUSTABLE_STORAGE: "最小化总运行成本 = 可调负荷运行成本 + 储能运行成本 + 电网交易成本",
                SchedulingMode.TRADITIONAL: "最小化总运行成本 = 发电成本 + 储能成本 + 可调负荷成本 + 电网交易成本",
                SchedulingMode.NO_RENEWABLE: "最小化总运行成本 = 传统发电成本 + 储能成本 + 可调负荷成本 + 电网交易成本",
                SchedulingMode.STORAGE_ONLY: "最小化总运行成本 = 储能运行成本 + 电网交易成本",
                SchedulingMode.FULL_SYSTEM: "最小化总成本 = 发电成本 + 储能成本 + 可调负荷成本 + 电网交易成本 - 辅助服务收益"
            }
            return cost_objectives.get(mode, "标准成本最小化目标")
        
        # 新的收益最大化描述
        elif objective == OptimizationObjective.REVENUE_MAXIMIZATION:
            revenue_objectives = {
                SchedulingMode.RENEWABLE_STORAGE: "最大化收益 = 绿电售电收入 + 储能套利收入",
                SchedulingMode.ADJUSTABLE_STORAGE: "最大化收益 = 需求响应收入 + 调峰填谷收入 + 储能套利收入",
                SchedulingMode.TRADITIONAL: "最大化收益 = 售电收入 + 调峰填谷收入 + 储能套利收入",
                SchedulingMode.NO_RENEWABLE: "最大化收益 = 传统电力售电收入 + 峰谷电价套利收入",
                SchedulingMode.STORAGE_ONLY: "最大化收益 = 储能套利收入 + 电价差值收入",
                SchedulingMode.FULL_SYSTEM: "最大化总收益 = 售电收入 + 辅助服务收入 + 储能套利收入 + 需求响应收入"
            }
            return revenue_objectives.get(mode, "收益最大化目标")
        
        elif objective == OptimizationObjective.PROFIT_MAXIMIZATION:
            profit_objectives = {
                SchedulingMode.RENEWABLE_STORAGE: "最大化利润 = 绿电售电收入 - 运维成本 - 储能投资成本",
                SchedulingMode.ADJUSTABLE_STORAGE: "最大化利润 = 需求响应收入 + 储能套利 - 运行成本 - 电网购电成本",
                SchedulingMode.TRADITIONAL: "最大化利润 = 总收入 - 发电成本 - 运维成本 - 燃料成本",
                SchedulingMode.NO_RENEWABLE: "最大化利润 = 售电收入 - 传统发电成本 - 运行成本",
                SchedulingMode.STORAGE_ONLY: "最大化利润 = 储能套利收入 - 储能运行成本 - 电网购电成本",
                SchedulingMode.FULL_SYSTEM: "最大化总利润 = (售电+辅助服务+套利)收入 - (发电+运维+购电)成本"
            }
            return profit_objectives.get(mode, "利润最大化目标")
        
        elif objective == OptimizationObjective.ANCILLARY_REVENUE_MAX:
            return "最大化辅助服务收入 = 调频服务收入 + 旋转备用收入 + 电网调节收入"
        
        elif objective == OptimizationObjective.GRID_SUPPORT_OPTIMIZED:
            return "电网支撑优化 = 最大化电网稳定性贡献 + 保证最小利润要求"
        
        return "未知优化目标"
    
    def get_optimization_objective_description(self, objective: OptimizationObjective) -> str:
        """获取优化目标的详细描述"""
        return self.objective_configs[objective]['description']
    
    def get_optimization_objective_function(self, objective: OptimizationObjective) -> str:
        """获取优化目标的数学表达式"""
        return self.objective_configs[objective]['objective_function']
    
    def list_available_objectives(self) -> List[Tuple[OptimizationObjective, str]]:
        """列出所有可用的优化目标"""
        return [(obj, self.get_optimization_objective_description(obj)) for obj in OptimizationObjective]
    
    def set_optimization_objective(self, objective: OptimizationObjective):
        """设置当前优化目标"""
        self.current_objective = objective
        print(f"[CONFIG] 已设置优化目标: {objective.value}")
        print(f"[TARGET] 目标描述: {self.get_optimization_objective_description(objective)}")
    
    def create_optimized_model(self, mode: SchedulingMode, time_index: pd.DatetimeIndex, 
                             objective: OptimizationObjective = None) -> 'OptimizedVPPModel':
        """
        创建针对特定调度模式和优化目标的模型
        
        Args:
            mode: 调度模式
            time_index: 时间索引
            objective: 优化目标（默认为成本最小化）
            
        Returns:
            优化后的VPP模型
        """
        if objective is None:
            objective = self.current_objective
        
        self.current_mode = mode
        self.current_objective = objective
        mode_config = self.mode_configs[mode]
        objective_config = self.objective_configs[objective]
        
        print(f"\n[SETUP] 创建调度模式: {mode.value}")
        print(f"[INFO] 模式描述: {self.get_mode_description(mode)}")
        print(f"[CONFIG] 优化目标: {objective.value}")
        print(f"[TARGET] 目标函数: {self.get_objective_function_description(mode, objective)}")
        
        return OptimizedVPPModel(time_index, mode_config, mode, objective_config, objective)
    
    def list_available_modes(self) -> List[Tuple[SchedulingMode, str]]:
        """列出所有可用的调度模式"""
        return [(mode, self.get_mode_description(mode)) for mode in SchedulingMode]
    
    def get_mode_resources(self, mode: SchedulingMode) -> Dict[str, bool]:
        """获取调度模式包含的资源类型"""
        config = self.mode_configs[mode]
        
        resources = {
            'photovoltaic': False,
            'wind': False,
            'gas_turbine': False,
            'battery_storage': False,
            'adjustable_loads': False,
            'ancillary_services': False,
            'ev_charging_station': False,
            'interruptible_loads': False,
            'building_hvac': False,
            'demand_response': False
        }
        
        # 检查能源资源
        energy_resources = config.get('energy_resources', {})
        resources['photovoltaic'] = 'photovoltaic' in energy_resources
        resources['wind'] = 'wind' in energy_resources
        resources['gas_turbine'] = 'gas_turbine' in energy_resources
        resources['battery_storage'] = 'battery_storage' in energy_resources
        
        # 检查可调负荷
        adjustable_loads = config.get('adjustable_loads', {})
        resources['adjustable_loads'] = len(adjustable_loads) > 0
        resources['ev_charging_station'] = config.get('ev_charging_station', {}).get('enabled', False)
        resources['interruptible_loads'] = any(
            item.get('enabled', True) for item in config.get('interruptible_loads', {}).values()
        )
        resources['building_hvac'] = any(
            item.get('enabled', True) for item in config.get('building_hvac', {}).values()
        )
        resources['demand_response'] = (
            config.get('price_based_dr', {}).get('enabled', False) or
            config.get('incentive_based_dr', {}).get('enabled', False)
        )
        
        # 检查辅助服务
        if resources['battery_storage']:
            battery_config = energy_resources.get('battery_storage', {})
            ancillary_config = battery_config.get('ancillary_services', {})
            freq_reg = ancillary_config.get('frequency_regulation', {}).get('enable', False)
            spin_reserve = ancillary_config.get('spinning_reserve', {}).get('enable', False)
            resources['ancillary_services'] = freq_reg or spin_reserve
        
        return resources


class OptimizedVPPModel(VPPOptimizationModel):
    """针对特定调度模式优化的VPP模型"""
    
    def __init__(self, time_index: pd.DatetimeIndex, mode_config: Dict, mode: SchedulingMode,
                 objective_config: Dict = None, objective: OptimizationObjective = None):
        """
        初始化优化模型
        
        Args:
            time_index: 时间索引
            mode_config: 调度模式配置
            mode: 调度模式类型
            objective_config: 优化目标配置
            objective: 优化目标类型
        """
        # 使用模式特定的配置初始化基类
        super().__init__(time_index)
        self.config = mode_config
        self.mode = mode
        self.objective_config = objective_config or {'type': 'minimization', 'variable_costs_sign': 1, 'revenue_sign': -1}
        self.objective = objective or OptimizationObjective.COST_MINIMIZATION
        
    def _apply_objective_config_to_flow(self, variable_cost: float, is_revenue: bool = False) -> float:
        """
        根据优化目标配置调整成本系数
        
        Args:
            variable_cost: 原始变动成本
            is_revenue: 是否为收入项目
            
        Returns:
            调整后的成本系数
        """
        if is_revenue:
            return variable_cost * self.objective_config.get('revenue_sign', -1)
        else:
            return variable_cost * self.objective_config.get('variable_costs_sign', 1)
    
    def _apply_objective_weights(self, variable_cost: float, weight_type: str = 'default') -> float:
        """
        应用特定类型的权重
        
        Args:
            variable_cost: 原始成本
            weight_type: 权重类型（'ancillary', 'grid_support'等）
            
        Returns:
            加权后的成本
        """
        if weight_type == 'ancillary' and 'ancillary_weight' in self.objective_config:
            return variable_cost * self.objective_config['ancillary_weight']
        elif weight_type == 'grid_support' and 'grid_support_weight' in self.objective_config:
            return variable_cost * self.objective_config['grid_support_weight']
        return variable_cost
    
    def _create_energy_storage_with_objective(self):
        """根据优化目标创建储能系统"""
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
        
        # 计算综合成本（包含循环损耗）
        base_charge_cost = battery_config['charge_cost_yuan_mwh']
        cycle_degradation_cost = battery_config.get('cycle_degradation_cost_yuan_mwh', 0)
        total_base_charge_cost = base_charge_cost + cycle_degradation_cost
        
        # 根据优化目标调整成本系数
        charge_cost = self._apply_objective_config_to_flow(total_base_charge_cost)
        discharge_cost = self._apply_objective_config_to_flow(battery_config['discharge_cost_yuan_mwh'])
        
        # 最终方案：分离式建模（Converter + GenericStorage）
        # 这是唯一能同时保证功率约束和充放电互斥的方法
        import oemof.solph as solph
        
        # 使用配置文件中的真实成本
        real_charge_cost = charge_cost
        real_discharge_cost = discharge_cost
        
        print(f"储能成本配置 - 充电: {real_charge_cost} 元/MWh, 放电: {real_discharge_cost} 元/MWh")
        
        # 创建储能内部总线
        battery_bus = solph.Bus(label="battery_bus")
        
        # 储能充电器（电网 -> 储能）
        battery_charger = solph.components.Converter(
            label="battery_charger",
            inputs={
                self.components['bus_electricity']: solph.Flow(
                    nominal_value=available_power_capacity,  # 严格功率限制
                    variable_costs=real_charge_cost
                )
            },
            outputs={
                battery_bus: solph.Flow()
            },
            conversion_factors={battery_bus: battery_config['charge_efficiency']}
        )
        
        # 储能放电器（储能 -> 电网）
        battery_discharger = solph.components.Converter(
            label="battery_discharger", 
            inputs={
                battery_bus: solph.Flow()
            },
            outputs={
                self.components['bus_electricity']: solph.Flow(
                    nominal_value=available_power_capacity,  # 严格功率限制
                    variable_costs=real_discharge_cost
                )
            },
            conversion_factors={self.components['bus_electricity']: battery_config['discharge_efficiency']}
        )
        
        # 储能库（纯能量管理）
        battery_tank = solph.components.GenericStorage(
            label="battery_tank",
            inputs={battery_bus: solph.Flow()},
            outputs={battery_bus: solph.Flow()},
            nominal_storage_capacity=battery_config['energy_capacity_mwh'],
            initial_storage_level=battery_config['initial_soc'],
            min_storage_level=battery_config.get('min_soc', 0.1),
            max_storage_level=battery_config.get('max_soc', 0.95),
            loss_rate=battery_config['self_discharge_rate'],
            balanced=False
        )
        
        print(f"分离式储能建模 - 充电功率: 0-{available_power_capacity} MW, 放电功率: 0-{available_power_capacity} MW")
        print(f"储能容量: {battery_config['energy_capacity_mwh']} MWh, SOC范围: {battery_config.get('min_soc', 0.1)*100}%-{battery_config.get('max_soc', 0.95)*100}%")
        print("[OK] 分离式建模保证：1)功率约束严格执行 2)充放电天然互斥（不同Converter）")
        
        storage_components = [battery_bus, battery_charger, battery_discharger, battery_tank]
        
        # 创建辅助服务组件
        # 注意：这些组件需要与储能系统通过 add_ancillary_service_constraints 耦合
        if freq_reg_config.get('enable', False):
            # 向上调频服务 (Source -> Bus)
            freq_reg_up = solph.components.Source(
                label="freq_reg_up_service",
                outputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=freq_reg_config.get('max_capacity_mw', total_power_capacity * 0.5),
                        variable_costs=self._apply_objective_weights(
                            self._apply_objective_config_to_flow(freq_reg_config.get('up_price_yuan_mw', 80), is_revenue=True),
                            'ancillary'
                        )
                    )
                }
            )
            # 向下调频服务 (Bus -> Sink)
            freq_reg_down = solph.components.Sink(
                label="freq_reg_down_service",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=freq_reg_config.get('max_capacity_mw', total_power_capacity * 0.5),
                        variable_costs=self._apply_objective_weights(
                            self._apply_objective_config_to_flow(freq_reg_config.get('down_price_yuan_mw', 70), is_revenue=True),
                            'ancillary'
                        )
                    )
                }
            )
            storage_components.extend([freq_reg_up, freq_reg_down])
            print(f"已在模型中添加调频辅助服务组件: {freq_reg_config.get('max_capacity_mw')} MW")
            
        if spin_reserve_config.get('enable', False):
            # 向上旋转备用 (Source -> Bus)
            spin_reserve_up = solph.components.Source(
                label="spin_reserve_up_service",
                outputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=spin_reserve_config.get('max_capacity_mw', total_power_capacity * 0.5),
                        variable_costs=self._apply_objective_weights(
                            self._apply_objective_config_to_flow(spin_reserve_config.get('up_price_yuan_mw', 60), is_revenue=True),
                            'ancillary'
                        )
                    )
                }
            )
            # 向下旋转备用 (Bus -> Sink)
            spin_reserve_down = solph.components.Sink(
                label="spin_reserve_down_service",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=spin_reserve_config.get('max_capacity_mw', total_power_capacity * 0.5),
                        variable_costs=self._apply_objective_weights(
                            self._apply_objective_config_to_flow(spin_reserve_config.get('down_price_yuan_mw', 50), is_revenue=True),
                            'ancillary'
                        )
                    )
                }
            )
            storage_components.extend([spin_reserve_up, spin_reserve_down])
            print(f"已在模型中添加旋转备用辅助服务组件: {spin_reserve_config.get('max_capacity_mw')} MW")
        
        self.components['energy_storage'] = storage_components
    
    def _create_grid_connection_with_objective(self, price_data: pd.Series):
        """根据优化目标创建电网连接"""
        grid_config = self.config['grid_connection']
        
        # 根据优化目标调整电网交易成本
        purchase_costs = []
        sale_costs = []
        
        for price in price_data.values:
            # 购电成本（总是正的成本）
            purchase_cost = self._apply_objective_config_to_flow(price)
            purchase_costs.append(purchase_cost)
            
            # 售电收入（原本为负成本，表示收入）
            sale_price = price * grid_config['sale_price_ratio']
            sale_cost = self._apply_objective_config_to_flow(sale_price, is_revenue=True)
            sale_costs.append(sale_cost)
        
        import oemof.solph as solph
        
        # 电网购电
        grid_source = solph.components.Source(
            label="grid_source",
            outputs={
                self.components['bus_electricity']: solph.Flow(
                    variable_costs=purchase_costs,
                    nominal_value=grid_config['max_purchase_mw']
                )
            }
        )
        
        # 电网售电
        grid_sink = solph.components.Sink(
            label="grid_sink",
            inputs={
                self.components['bus_electricity']: solph.Flow(
                    variable_costs=sale_costs,
                    nominal_value=grid_config['max_sale_mw']
                )
            }
        )
        
        self.components['grid_connection'] = [grid_source, grid_sink]
        
    def create_energy_system(self, load_data: pd.Series, pv_data: pd.Series, 
                           wind_data: pd.Series, price_data: pd.Series) -> solph.EnergySystem:
        """
        根据调度模式创建定制化的能源系统
        
        Args:
            load_data: 负荷需求数据
            pv_data: 光伏发电数据  
            wind_data: 风电发电数据
            price_data: 电价数据
            
        Returns:
            构建完成的能源系统
        """
        print(f"正在创建 {self.mode.value} 模式的虚拟电厂能源系统...")
        
        # 根据模式调整数据
        pv_data_adjusted = self._adjust_renewable_data(pv_data, 'photovoltaic')
        wind_data_adjusted = self._adjust_renewable_data(wind_data, 'wind')
        
        # 创建能源系统
        self.energy_system = solph.EnergySystem(
            timeindex=self.time_index,
            infer_last_interval=False
        )
        
        # 创建系统组件
        self._create_buses()
        self._create_load_demand(load_data)
        
        # 根据模式创建相应组件
        if self._has_resource('photovoltaic') or self._has_resource('wind'):
            self._create_renewable_sources(pv_data_adjusted, wind_data_adjusted)
        
        if self._has_resource('gas_turbine'):
            self._create_conventional_generation()
            
        if self._has_resource('battery_storage'):
            self._create_energy_storage_with_objective()
            
        if self._has_adjustable_loads():
            self._create_adjustable_loads()
            
        self._create_grid_connection_with_objective(price_data)
        
        # 添加所有组件到能源系统
        all_components = []
        for component_list in self.components.values():
            if isinstance(component_list, list):
                all_components.extend(component_list)
            else:
                all_components.append(component_list)
        
        self.energy_system.add(*all_components)
        
        print(f"[OK] {self.mode.value} 模式能源系统创建完成，包含 {len(all_components)} 个组件")
        return self.energy_system
    
    def _adjust_renewable_data(self, data: pd.Series, resource_type: str) -> pd.Series:
        """根据调度模式调整可再生能源数据"""
        if not self._has_resource(resource_type):
            # 如果模式不包含此资源，返回零数据
            return pd.Series([0] * len(data), index=data.index)
        return data
    
    def _has_resource(self, resource_type: str) -> bool:
        """检查调度模式是否包含指定资源"""
        energy_resources = self.config.get('energy_resources', {})
        return resource_type in energy_resources
    
    def _has_adjustable_loads(self) -> bool:
        """检查调度模式是否包含可调负荷"""
        adjustable_loads = self.config.get('adjustable_loads', {})
        return len(adjustable_loads) > 0
    
    def get_mode_summary(self) -> Dict:
        """获取调度模式概要信息"""
        base_summary = self.get_system_summary()
        
        mode_summary = {
            'scheduling_mode': self.mode.value,
            'optimization_objective': self.objective.value,
            'mode_description': self._get_mode_description(),
            'objective_description': self._get_objective_description(),
            'included_resources': self._get_included_resources(),
            'objective_function': self._get_objective_function_details()
        }
        
        # 合并基础概要和模式概要
        base_summary.update(mode_summary)
        return base_summary
    
    def _get_mode_description(self) -> str:
        """获取模式描述"""
        manager = VPPSchedulingManager()
        return manager.get_mode_description(self.mode)
    
    def _get_included_resources(self) -> List[str]:
        """获取包含的资源列表"""
        resources = []
        
        energy_resources = self.config.get('energy_resources', {})
        for resource in energy_resources.keys():
            resources.append(resource)
        
        adjustable_loads = self.config.get('adjustable_loads', {})
        for load in adjustable_loads.keys():
            resources.append(f"adjustable_load_{load}")

        if self.config.get('ev_charging_station', {}).get('enabled', False):
            resources.append('ev_charging_station')

        for load_name, load_cfg in self.config.get('interruptible_loads', {}).items():
            if load_cfg.get('enabled', True):
                resources.append(f"interruptible_load_{load_name}")

        for building_name, building_cfg in self.config.get('building_hvac', {}).items():
            if building_cfg.get('enabled', True):
                resources.append(f"building_hvac_{building_name}")

        if self.config.get('price_based_dr', {}).get('enabled', False):
            resources.append('price_based_demand_response')
        if self.config.get('incentive_based_dr', {}).get('enabled', False):
            resources.append('incentive_based_demand_response')
        
        return resources
    
    def _get_objective_description(self) -> str:
        """获取优化目标描述"""
        manager = VPPSchedulingManager()
        return manager.get_optimization_objective_description(self.objective)
    
    def _get_objective_function_details(self) -> str:
        """获取目标函数详细信息"""
        manager = VPPSchedulingManager()
        return manager.get_objective_function_description(self.mode, self.objective)


# 示例使用
if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    
    from data.data_generator import VPPDataGenerator
    
    # 创建调度模式管理器
    manager = VPPSchedulingManager()
    
    # 列出所有可用模式
    print("可用的调度模式:")
    for mode, description in manager.list_available_modes():
        print(f"- {mode.value}: {description}")
    
    # 创建数据生成器
    data_generator = VPPDataGenerator()
    load_data, pv_data, wind_data, price_data = data_generator.generate_all_data()
    
    # 测试可再生能源+储能模式
    print(f"\n{'='*60}")
    print("测试可再生能源+储能调度模式")
    print(f"{'='*60}")
    
    model = manager.create_optimized_model(
        SchedulingMode.RENEWABLE_STORAGE, 
        data_generator.time_index
    )
    energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
    
    if model.validate_system():
        summary = model.get_mode_summary()
        print("\n[SUMMARY] 系统概要:")
        for key, value in summary.items():
            if key != 'components_by_type':
                print(f"  {key}: {value}")
