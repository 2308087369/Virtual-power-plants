"""
虚拟电厂优化模型
VPP Optimization Model

基于 oemof-solph 构建的虚拟电厂能源系统优化模型
"""

import os
import yaml
import logging
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
import warnings
warnings.filterwarnings('ignore')

# oemof-solph 核心导入
import oemof.solph as solph
import oemof.tools.logger as oemof_logger

# 获取模块级日志记录器
logger = logging.getLogger(__name__)


class VPPOptimizationModel:
    """
    虚拟电厂优化模型 (Virtual Power Plant Optimization Model)
    
    该类基于 oemof-solph 框架构建，用于模拟和优化虚拟电厂内的各种能源资源、
    负荷和储能系统的运行。支持多种调度模式和辅助服务（调频、旋转备用）。
    
    Attributes:
        time_index (pd.DatetimeIndex): 优化的时间索引
        periods (int): 优化时间段数量
        config (Dict): 系统配置字典
        energy_system (solph.EnergySystem): 构建的 oemof 能源系统对象
        components (Dict): 存储系统各组件的字典，便于后续引用
    """
    
    def __init__(self, time_index: pd.DatetimeIndex, config_path: Optional[str] = None):
        """
        初始化优化模型
        
        Args:
            time_index: 时间索引，定义了优化的时间跨度和频率
            config_path: 配置文件路径，如果不提供则使用默认路径
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
        """
        加载配置文件并与默认配置合并。
        
        采用递归合并策略，确保即使配置文件不完整，关键配置项也能通过默认值填充。
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            合并后的配置字典
        """
        default_config = self._get_default_config()
        
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'config', 'system_config.yaml'
            )
        
        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在: {config_path}，将完全使用默认配置")
            return default_config
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
            
            if user_config is None:
                logger.warning(f"配置文件为空: {config_path}，将使用默认配置")
                return default_config
                
            # 递归合并配置，确保所有必需的键都存在
            return self._merge_configs(default_config, user_config)
        except Exception as e:
            logger.error(f"加载配置失败: {e}，将使用默认配置")
            return default_config
    
    def _merge_configs(self, default: Dict, user: Dict) -> Dict:
        """
        递归合并两个字典配置。
        
        Args:
            default: 默认配置字典
            user: 用户提供的配置字典
            
        Returns:
            合并后的字典
        """
        if user is None:
            return default
            
        merged = default.copy()
        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        return merged
    
    def _get_default_config(self) -> Dict:
        """
        获取系统默认配置。
        
        包含光伏、风电、燃气轮机、储能系统、可调负荷和电网连接的基本参数。
        
        Returns:
            默认配置字典
        """
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
            'ev_charging_station': {
                'enabled': False,
                'num_chargers': 10,
                'charger_power_kw': 7,
                'fast_charger_power_kw': 30,
                'num_fast_chargers': 2,
                'operating_cost_yuan_mwh': 20,
                'average_utilization_ratio': 0.5,
                'min_service_ratio': 0.9,
                'demand_pattern': {
                    'morning_peak': [7, 9],
                    'evening_peak': [17, 21],
                    'avg_energy_demand_kwh': 30
                }
            },
            'interruptible_loads': {
                'industrial_plant_1': {
                    'enabled': False,
                    'rated_power_mw': 5,
                    'interruptible_ratio': 0.3,
                    'max_interruption_hours': 4,
                    'min_service_ratio': 0.8,
                    'interruption_levels': {
                        'level_1': {'capacity_mw': 1.0, 'compensation_yuan_mwh': 500},
                        'level_2': {'capacity_mw': 0.5, 'compensation_yuan_mwh': 300}
                    }
                }
            },
            'building_hvac': {
                'office_building_1': {
                    'enabled': False,
                    'rated_power_mw': 2,
                    'operating_cost_yuan_mwh': 45,
                    'thermal_mass_kwh_per_c': 500,
                    'temperature_range': [20, 26],
                    'target_temperature_c': 23,
                    'initial_temperature_c': 24,
                    'pre_cooling_hours': 2,
                    'outdoor_temp_pattern': [10] * 24,
                    'min_operating_ratio': 0.35
                }
            },
            'grid_connection': {
                'max_purchase_mw': 1000,
                'max_sale_mw': 500,
                'sale_price_ratio': 0.95
            }
        }
    
    def _setup_logging(self):
        """
        设置日志配置。
        
        整合 oemof 的日志系统和标准 Python 日志。
        """
        # 设置根日志级别为INFO，避免DEBUG级别导致的性能问题
        logging.getLogger().setLevel(logging.INFO)
        
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'logs'
        )
        os.makedirs(log_dir, exist_ok=True)
        
        oemof_logger.define_logging(
            logpath=log_dir,
            logfile='vpp_optimization.log',
            screen_level=logging.WARNING,  # 屏幕显示 WARNING 及以上
            file_level=logging.INFO        # 文件保存 INFO 及以上
        )
    
    def create_energy_system(self, load_data: pd.Series, pv_data: pd.Series, 
                           wind_data: pd.Series, price_data: pd.Series) -> solph.EnergySystem:
        """
        创建并构建能源系统模型。
        
        按顺序执行以下步骤：
        1. 创建电力总线
        2. 添加负荷需求
        3. 添加可再生能源 (PV, Wind)
        4. 添加常规机组 (Gas Turbine)
        5. 添加储能系统 (Battery) 及辅助服务组件
        6. 添加可调负荷 (Chiller, Heat Pump)
        7. 添加电网连接
        
        Args:
            load_data: 负荷需求时间序列 (MW)
            pv_data: 光伏发电出力序列 (MW)
            wind_data: 风电发电出力序列 (MW)
            price_data: 电价时间序列 (元/MWh)
            
        Returns:
            构建完成的 solph.EnergySystem 对象
        """
        logger.info("正在创建虚拟电厂能源系统模型...")
        
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
        
        logger.info(f"能源系统创建完成，包含 {len(all_components)} 个组件")
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
        
        # 储能基本配置
        total_power_capacity = battery_config['power_capacity_mw']
        
        logger.info(f"储能配置 - 功率容量: {total_power_capacity} MW, 能量容量: {battery_config['energy_capacity_mwh']} MWh")
        
        # 计算综合充电成本（包含循环损耗）
        base_charge_cost = battery_config['charge_cost_yuan_mwh']
        cycle_degradation_cost = battery_config.get('cycle_degradation_cost_yuan_mwh', 0)
        total_charge_cost = base_charge_cost + cycle_degradation_cost
        
        # 储能系统（主要用于能量交易）
        battery_storage = solph.components.GenericStorage(
            label="battery_storage",
            inputs={
                self.components['bus_electricity']: solph.Flow(
                    nominal_value=total_power_capacity,
                    variable_costs=total_charge_cost,
                    max=1.0,
                    min=0.0
                )
            },
            outputs={
                self.components['bus_electricity']: solph.Flow(
                    nominal_value=total_power_capacity,
                    variable_costs=battery_config['discharge_cost_yuan_mwh'],
                    max=1.0,
                    min=0.0
                )
            },
            nominal_storage_capacity=battery_config['energy_capacity_mwh'],
            initial_storage_level=battery_config['initial_soc'],
            min_storage_level=battery_config.get('min_soc', 0.1),
            max_storage_level=battery_config.get('max_soc', 0.95),
            inflow_conversion_factor=battery_config['charge_efficiency'],
            outflow_conversion_factor=battery_config['discharge_efficiency'],
            loss_rate=battery_config['self_discharge_rate'],
            balanced=True
        )
        
        storage_components = [battery_storage]
        
        # 创建辅助服务组件
        if freq_reg_config.get('enable', False):
            # 向上调频服务 (Source -> Bus)
            freq_reg_up = solph.components.Source(
                label="freq_reg_up_service",
                outputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=freq_reg_config.get('max_capacity_mw', total_power_capacity * 0.5),
                        variable_costs=0  # 收入在分析器中计算，此处设为0或负值表示收入
                    )
                }
            )
            # 向下调频服务 (Bus -> Sink)
            freq_reg_down = solph.components.Sink(
                label="freq_reg_down_service",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=freq_reg_config.get('max_capacity_mw', total_power_capacity * 0.5),
                        variable_costs=0
                    )
                }
            )
            storage_components.extend([freq_reg_up, freq_reg_down])
            logger.info(f"已启用调频辅助服务: 最大容量 {freq_reg_config.get('max_capacity_mw')} MW")
            
        if spin_reserve_config.get('enable', False):
            # 向上旋转备用 (Source -> Bus)
            spin_reserve_up = solph.components.Source(
                label="spin_reserve_up_service",
                outputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=spin_reserve_config.get('max_capacity_mw', total_power_capacity * 0.5),
                        variable_costs=0
                    )
                }
            )
            # 向下旋转备用 (Bus -> Sink)
            spin_reserve_down = solph.components.Sink(
                label="spin_reserve_down_service",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=spin_reserve_config.get('max_capacity_mw', total_power_capacity * 0.5),
                        variable_costs=0
                    )
                }
            )
            storage_components.extend([spin_reserve_up, spin_reserve_down])
            logger.info(f"已启用旋转备用辅助服务: 最大容量 {spin_reserve_config.get('max_capacity_mw')} MW")
            
        self.components['energy_storage'] = storage_components
    
    def _create_adjustable_loads(self):
        """创建可调负荷"""
        adjustable_loads_config = self.config.get('adjustable_loads', {})
        
        adjustable_loads = []
        
        # 冷机系统
        if 'chiller' in adjustable_loads_config:
            chiller_config = adjustable_loads_config['chiller']
            max_profile = self._apply_demand_response_profile(
                'chiller',
                np.full(self.periods, chiller_config.get('max_power_ratio', 1.0), dtype=float)
            )
            
            chiller_load = solph.components.Sink(
                label="chiller_load",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=chiller_config['rated_power_mw'],
                        variable_costs=chiller_config['operating_cost_yuan_mwh'],
                        min=chiller_config['min_power_ratio'],
                        max=max_profile
                    )
                }
            )
            adjustable_loads.append(chiller_load)
        
        # 热机系统
        if 'heat_pump' in adjustable_loads_config:
            heat_pump_config = adjustable_loads_config['heat_pump']
            max_profile = self._apply_demand_response_profile(
                'heat_pump',
                np.full(self.periods, heat_pump_config.get('max_power_ratio', 1.0), dtype=float)
            )
            
            heat_pump_load = solph.components.Sink(
                label="heat_pump_load",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=heat_pump_config['rated_power_mw'],
                        variable_costs=heat_pump_config['operating_cost_yuan_mwh'],
                        min=heat_pump_config['min_power_ratio'],
                        max=max_profile
                    )
                }
            )
            adjustable_loads.append(heat_pump_load)

        adjustable_loads.extend(self._create_ev_charging_station())
        adjustable_loads.extend(self._create_interruptible_loads())
        adjustable_loads.extend(self._create_building_hvac())
        
        self.components['adjustable_loads'] = adjustable_loads

    def _get_hour_mask(self, hour_ranges: List[List[int]]) -> np.ndarray:
        """根据小时区间生成掩码"""
        mask = np.zeros(self.periods, dtype=float)
        for start_hour, end_hour in hour_ranges:
            for idx, timestamp in enumerate(self.time_index):
                if start_hour <= timestamp.hour <= end_hour:
                    mask[idx] = 1.0
        return mask

    def _get_time_step_hours(self) -> float:
        """获取当前模型的时间步长（小时）"""
        if len(self.time_index) < 2:
            return 1.0
        return max((self.time_index[1] - self.time_index[0]).total_seconds() / 3600.0, 1e-6)

    def _get_peak_valley_masks(self) -> Tuple[np.ndarray, np.ndarray]:
        """获取峰谷时段掩码"""
        dr_config = self.config.get('price_based_dr', {})
        tariff = dr_config.get('tariff_structure', {})
        peak_hours = tariff.get('peak_hours', [8, 11, 18, 21])
        valley_hours = tariff.get('valley_hours', [0, 7])

        peak_ranges = []
        if len(peak_hours) >= 2:
            peak_ranges.append([peak_hours[0], peak_hours[1]])
        if len(peak_hours) >= 4:
            peak_ranges.append([peak_hours[2], peak_hours[3]])

        valley_ranges = [[valley_hours[0], valley_hours[1]]] if len(valley_hours) >= 2 else []
        return self._get_hour_mask(peak_ranges), self._get_hour_mask(valley_ranges)

    def _apply_demand_response_profile(self, load_name: str, base_profile: np.ndarray) -> np.ndarray:
        """对柔性负荷施加需求响应控制"""
        profile = np.array(base_profile, dtype=float)

        price_dr = self.config.get('price_based_dr', {})
        if price_dr.get('enabled', False):
            peak_mask, valley_mask = self._get_peak_valley_masks()
            peak_ratio = price_dr.get('flexible_load_peak_reduction_ratio', 0.8)
            valley_ratio = price_dr.get('flexible_load_valley_boost_ratio', 1.1)
            profile = np.where(peak_mask > 0, profile * peak_ratio, profile)
            profile = np.where(valley_mask > 0, np.minimum(profile * valley_ratio, 1.0), profile)

        incentive_dr = self.config.get('incentive_based_dr', {})
        dlc_config = incentive_dr.get('direct_load_control', {})
        controllable_loads = dlc_config.get('controllable_loads', [])
        if incentive_dr.get('enabled', False) and dlc_config.get('enabled', False) and load_name in controllable_loads:
            event_hours = incentive_dr.get('event_hours', [])
            max_power_ratio = dlc_config.get('max_power_ratio', 0.7)
            for idx, timestamp in enumerate(self.time_index):
                if timestamp.hour in event_hours:
                    profile[idx] = min(profile[idx], max_power_ratio)

        return np.clip(profile, 0.0, 1.0)

    def _create_ev_charging_station(self) -> List:
        """创建EV充电站模型"""
        ev_config = self.config.get('ev_charging_station', {})
        if not ev_config.get('enabled', False):
            return []

        num_fast = ev_config.get('num_fast_chargers', 0)
        num_total = ev_config.get('num_chargers', 0)
        num_slow = max(num_total - num_fast, 0)
        nominal_power_mw = (
            num_slow * ev_config.get('charger_power_kw', 7) +
            num_fast * ev_config.get('fast_charger_power_kw', 30)
        ) / 1000.0

        if nominal_power_mw <= 0:
            return []

        time_step_hours = self._get_time_step_hours()
        horizon_hours = self.periods * time_step_hours

        demand_pattern = ev_config.get('demand_pattern', {})
        hour_ranges = []
        for key in ('morning_peak', 'evening_peak'):
            if key in demand_pattern and len(demand_pattern[key]) >= 2:
                hour_ranges.append([demand_pattern[key][0], demand_pattern[key][1]])

        availability_profile = self._get_hour_mask(hour_ranges) if hour_ranges else np.ones(self.periods)
        availability_profile = self._apply_demand_response_profile('ev_charging_station', availability_profile)
        available_hours = max(float(availability_profile.sum() * time_step_hours), time_step_hours)

        avg_energy_kwh = demand_pattern.get('avg_energy_demand_kwh', 30)
        utilization_ratio = ev_config.get('average_utilization_ratio', 0.6)
        required_energy_mwh = (avg_energy_kwh * num_total * utilization_ratio) / 1000.0
        required_energy_mwh *= horizon_hours / 24.0
        service_ratio = ev_config.get('min_service_ratio', 0.9)
        service_hours = min((required_energy_mwh * service_ratio) / nominal_power_mw, available_hours)

        ev_load = solph.components.Sink(
            label="ev_charging_station",
            inputs={
                self.components['bus_electricity']: solph.Flow(
                    nominal_value=nominal_power_mw,
                    variable_costs=ev_config.get('operating_cost_yuan_mwh', 20),
                    min=0.0,
                    max=availability_profile,
                    full_load_time_min=max(service_hours, 0.0),
                    full_load_time_max=min((required_energy_mwh / nominal_power_mw) * 1.05, available_hours)
                )
            }
        )
        return [ev_load]

    def _create_interruptible_loads(self) -> List:
        """创建工业可中断负荷模型"""
        interruptible_config = self.config.get('interruptible_loads', {})
        components = []
        time_step_hours = self._get_time_step_hours()
        horizon_hours = self.periods * time_step_hours

        for load_name, load_config in interruptible_config.items():
            if not load_config.get('enabled', True):
                continue

            levels = load_config.get('interruption_levels', {})
            level_capacity = sum(level.get('capacity_mw', 0.0) for level in levels.values())
            fallback_capacity = load_config.get('rated_power_mw', 0.0) * load_config.get('interruptible_ratio', 0.0)
            interruptible_capacity = level_capacity if level_capacity > 0 else fallback_capacity
            if interruptible_capacity <= 0:
                continue

            max_interruption_hours = load_config.get('max_interruption_hours', 4)
            min_service_ratio = load_config.get('min_service_ratio', 0.8)
            service_hours = max(
                horizon_hours * min_service_ratio,
                horizon_hours - min(max_interruption_hours, horizon_hours)
            )
            max_profile = self._apply_demand_response_profile(f'interruptible_load_{load_name}', np.ones(self.periods))

            load_component = solph.components.Sink(
                label=f"interruptible_load_{load_name}",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=interruptible_capacity,
                        variable_costs=0,
                        min=0.0,
                        max=max_profile,
                        full_load_time_min=min(service_hours, float(max_profile.sum() * time_step_hours))
                    )
                }
            )
            components.append(load_component)

        return components

    def _create_building_hvac(self) -> List:
        """创建商业楼宇空调模型"""
        hvac_config = self.config.get('building_hvac', {})
        components = []
        time_step_hours = self._get_time_step_hours()
        horizon_hours = self.periods * time_step_hours

        for building_name, building in hvac_config.items():
            if not building.get('enabled', True):
                continue

            rated_power = building.get('rated_power_mw', 0.0)
            if rated_power <= 0:
                continue

            min_operating_ratio = building.get('min_operating_ratio', 0.35)
            full_load_time_min = horizon_hours * min_operating_ratio
            max_profile = self._apply_demand_response_profile(
                f'building_hvac_{building_name}',
                np.ones(self.periods)
            )

            pre_cooling_hours = int(building.get('pre_cooling_hours', 0))
            if pre_cooling_hours > 0:
                peak_mask, _ = self._get_peak_valley_masks()
                peak_indices = np.where(peak_mask > 0)[0]
                if len(peak_indices) > 0:
                    first_peak = peak_indices[0]
                    start_idx = max(first_peak - pre_cooling_hours, 0)
                    max_profile[start_idx:first_peak] = 1.0

            hvac_component = solph.components.Sink(
                label=f"building_hvac_{building_name}",
                inputs={
                    self.components['bus_electricity']: solph.Flow(
                        nominal_value=rated_power,
                        variable_costs=building.get('operating_cost_yuan_mwh', 45),
                        min=0.0,
                        max=max_profile,
                        full_load_time_min=min(full_load_time_min, float(max_profile.sum() * time_step_hours))
                    )
                }
            )
            components.append(hvac_component)

        return components
    
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
    
    def add_ancillary_service_constraints(self, model: solph.Model):
        """
        向优化模型添加辅助服务耦合约束
        
        包含：
        1. 功率耦合约束：储能放电/充电功率与辅助服务容量之和不得超过最大功率
        2. 能量耦合约束：储能当前电量必须足以支撑所提供的向上/向下辅助服务
        
        该方法利用 Pyomo 的约束机制，在 oemof-solph 构建的底层模型上添加
        跨组件的耦合约束，确保辅助服务的调用符合储能系统的物理限制。
        
        Args:
            model: 已构建的 oemof.solph.Model 对象
        """
        from pyomo import environ as pyo
        
        # 获取相关组件
        battery_storage = None
        freq_reg_up = None
        freq_reg_down = None
        spin_reserve_up = None
        spin_reserve_down = None
        
        # 从能源系统中查找组件
        # oemof 将所有组件存储在 energy_system.nodes 中
        battery_tank = None
        battery_charger = None
        battery_discharger = None

        for node in self.energy_system.nodes:
            if node.label == "battery_storage":
                battery_storage = node
            elif node.label == "battery_tank":
                battery_tank = node
            elif node.label == "battery_charger":
                battery_charger = node
            elif node.label == "battery_discharger":
                battery_discharger = node
            elif node.label == "freq_reg_up_service":
                freq_reg_up = node
            elif node.label == "freq_reg_down_service":
                freq_reg_down = node
            elif node.label == "spin_reserve_up_service":
                spin_reserve_up = node
            elif node.label == "spin_reserve_down_service":
                spin_reserve_down = node
                
        if not battery_storage and not battery_tank:
            logger.warning("未找到储能组件（battery_storage 或 battery_tank），跳过辅助服务约束添加")
            return

        # 获取储能参数，用于约束计算
        battery_config = self.config['energy_resources']['battery_storage']
        p_max = battery_config['power_capacity_mw']
        e_max = battery_config['energy_capacity_mwh']
        e_min = battery_config.get('min_soc', 0.1) * e_max
        
        # 获取时间步长（小时），用于电量预留计算
        if len(self.time_index) > 1:
            time_delta = self.time_index[1] - self.time_index[0]
            dt = time_delta.total_seconds() / 3600.0
        else:
            dt = 1.0  # 默认1小时
            
        # 1. 功率限制约束 (Power Limit Constraints)
        # 确保能量调度与辅助服务调度的总功率不超过设备额定功率
        def storage_power_up_limit_rule(m, t):
            # 向上功率约束：放电功率 + 向上调频 + 向上旋转备用 <= 最大功率
            if battery_storage:
                p_discharge = m.flow[battery_storage, self.components['bus_electricity'], t]
            else:
                p_discharge = m.flow[battery_discharger, self.components['bus_electricity'], t]

            r_up = 0
            if freq_reg_up:
                r_up += m.flow[freq_reg_up, self.components['bus_electricity'], t]
            if spin_reserve_up:
                r_up += m.flow[spin_reserve_up, self.components['bus_electricity'], t]
            
            return p_discharge + r_up <= p_max

        def storage_power_down_limit_rule(m, t):
            # 向下功率约束：充电功率 + 向下调频 + 向下旋转备用 <= 最大功率
            if battery_storage:
                p_charge = m.flow[self.components['bus_electricity'], battery_storage, t]
            else:
                p_charge = m.flow[self.components['bus_electricity'], battery_charger, t]

            r_down = 0
            if freq_reg_down:
                r_down += m.flow[self.components['bus_electricity'], freq_reg_down, t]
            if spin_reserve_down:
                r_down += m.flow[self.components['bus_electricity'], spin_reserve_down, t]
            
            return p_charge + r_down <= p_max

        # 2. 能量预留约束 (Energy Reserve Constraints)
        # 确保储能电量足以支撑辅助服务的调用
        def storage_energy_up_reserve_rule(m, t):
            # 向上能量约束：当前电量 - 向上服务所需能量 >= 最小电量
            target_storage = battery_storage if battery_storage else battery_tank
            e_current = m.GenericStorageBlock.storage_content[target_storage, t]
            
            r_up_energy = 0
            if freq_reg_up:
                r_up_energy += m.flow[freq_reg_up, self.components['bus_electricity'], t] * dt
            if spin_reserve_up:
                r_up_energy += m.flow[spin_reserve_up, self.components['bus_electricity'], t] * dt
            
            return e_current - r_up_energy >= e_min

        def storage_energy_down_reserve_rule(m, t):
            # 向下能量约束：当前电量 + 向下服务所需能量 <= 最大电量
            target_storage = battery_storage if battery_storage else battery_tank
            e_current = m.GenericStorageBlock.storage_content[target_storage, t]
            
            r_down_energy = 0
            if freq_reg_down:
                r_down_energy += m.flow[self.components['bus_electricity'], freq_reg_down, t] * dt
            if spin_reserve_down:
                r_down_energy += m.flow[self.components['bus_electricity'], spin_reserve_down, t] * dt
            
            return e_current + r_down_energy <= e_max

        # 将定义好的规则添加到 Pyomo 模型中
        model.storage_power_up_limit = pyo.Constraint(model.TIMESTEPS, rule=storage_power_up_limit_rule)
        model.storage_power_down_limit = pyo.Constraint(model.TIMESTEPS, rule=storage_power_down_limit_rule)
        model.storage_energy_up_reserve = pyo.Constraint(model.TIMESTEPS, rule=storage_energy_up_reserve_rule)
        model.storage_energy_down_reserve = pyo.Constraint(model.TIMESTEPS, rule=storage_energy_down_reserve_rule)
        
        logger.info("已成功添加辅助服务功率与能量耦合约束")

    def get_component_by_label(self, label: str):
        """根据标签获取组件"""
        for component in self.energy_system.nodes:
            if component.label == label:
                return component
        return None
    
    def validate_system(self) -> bool:
        """验证能源系统的完整性"""
        if self.energy_system is None:
            logger.error("错误：能源系统未创建")
            return False
        
        # 检查是否有组件
        if len(self.energy_system.nodes) == 0:
            logger.error("错误：能源系统中没有组件")
            return False
        
        # 检查电力总线是否存在
        bus_electricity = self.get_component_by_label("bus_electricity")
        if bus_electricity is None:
            logger.error("错误：缺少电力总线")
            return False
        
        logger.info("能源系统验证通过")
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
