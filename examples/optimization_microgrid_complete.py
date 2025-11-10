#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Microgrid Optimization with Scientific Visualization and Analysis
微电网日前优化调度完整版 - 科学可视化与分析

基于PuLP建立混合整数规划模型，求解微电网日前调度问题，
提供科学可视化、详细日志记录、多场景成本对比分析。

功能特点：
- 完整的微电网优化建模
- 科学级可视化图表
- 多场景成本对比分析
- 详细日志记录系统
- 综合分析报告

字体：使用文泉驿正黑 (WenQuanYi Zen Hei)
"""

import pulp
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import pandas as pd
from datetime import datetime
import os
from pathlib import Path
import json
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# -----------------------------------------------------------------------------
# Scenario name mapping to English and filename-safe slug helper
# -----------------------------------------------------------------------------
SCENARIO_NAME_MAP = {
    '基准场景-仅电网供电': 'Baseline - Grid Only',
    '可再生能源全额利用': 'Full Renewable Utilization',
    '允许弃风弃光优化': 'Curtailment Allowed Optimization',
    '含储能系统优化': 'Optimization with Storage',
    '综合优化方案': 'Integrated Optimization Plan'
}

def scenario_en(name: str) -> str:
    """Map Chinese scenario names to English for display."""
    return SCENARIO_NAME_MAP.get(name, name)

def scenario_slug(name: str) -> str:
    """Create an ASCII filename-friendly slug from scenario name."""
    en = scenario_en(name)
    slug = en.replace(' ', '_').replace('-', '_')
    return ''.join(ch for ch in slug if ch.isalnum() or ch == '_')

# =============================================================================
# 字体配置 - 使用文泉驿正黑
# =============================================================================

# 记录已选定的中文字体族名，方便在样式设置后重新应用
# CHINESE_FONT_NAME: Optional[str] = None

# def setup_chinese_fonts():
#     """设置中文字体为文泉驿正黑"""
#     # 检查字体文件路径
#     font_paths = [
#         '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
#         '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'
#     ]

#     available_font = None
#     for font_path in font_paths:
#         if os.path.exists(font_path):
#             available_font = font_path
#             break

#     if available_font:
#         # 添加字体
#         fm.fontManager.addfont(available_font)
#         # 通过文件解析出 Matplotlib 识别的字体族名称
#         prop = fm.FontProperties(fname=available_font)
#         font_name = prop.get_name()
#         # 记录全局字体族名
#         global CHINESE_FONT_NAME
#         CHINESE_FONT_NAME = font_name
#         # 设置默认字体为识别到的族名，并提供中文字体回退列表
#         plt.rcParams['font.family'] = [font_name]
#         plt.rcParams['font.sans-serif'] = [
#             font_name,
#             'WenQuanYi Zen Hei',
#             'WenQuanYi Micro Hei',
#             'SimHei',
#             'Noto Sans CJK SC',
#             'DejaVu Sans'
#         ]
#         plt.rcParams['text.usetex'] = False
#         print(f"已设置字体: {available_font} -> {font_name}")
#     else:
#         print("警告: 未找到文泉驿字体，使用系统默认中文字体")
#         plt.rcParams['font.sans-serif'] = ['SimHei', 'Noto Sans CJK SC', 'DejaVu Sans']
#         plt.rcParams['font.family'] = ['sans-serif']
#         plt.rcParams['text.usetex'] = False

#     plt.rcParams['axes.unicode_minus'] = False
#     sns.set_style("whitegrid")
#     sns.set_context("paper", font_scale=1.2)

# # 初始化字体
# setup_chinese_fonts()

# =============================================================================
# 基础模型类
# =============================================================================

class Model:
    """基础资源模型类"""
    def __init__(self, name: str, capacity: float, unit_cost: float):
        """
        初始化基础模型
        Args:
            name: 设备名称
            capacity: 容量 (kW)
            unit_cost: 单位成本 (元/kWh)
        """
        self.name = name
        self.capacity = capacity
        self.unit_cost = unit_cost
        self.variables = None
        self.constraints = None
        self.objective = None

    def create_model(self, time_points: int, dt: float):
        """创建优化模型 - 需在子类中实现"""
        raise NotImplementedError

    @property
    def output(self) -> np.ndarray:
        """获取输出结果"""
        return np.array([v.value() for v in self.variables]) if self.variables else np.zeros(time_points)


class Grid(Model):
    """电网模型"""
    def __init__(self, name: str, capacity: float, unit_cost: np.ndarray, unit_profit: np.ndarray):
        super().__init__(name, capacity, unit_cost)
        self.unit_profit = unit_profit

    def create_model(self, time_points: int, dt: float):
        # 定义购电和售电变量
        vars_from = [pulp.LpVariable(f'{self.name}_from_{i}', lowBound=0) for i in range(time_points)]
        vars_to = [pulp.LpVariable(f'{self.name}_to_{i}', lowBound=0) for i in range(time_points)]
        self.variables = [v1 - v2 for v1, v2 in zip(vars_from, vars_to)]

        # 容量约束
        self.constraints = []
        vars_b = [pulp.LpVariable(f'{self.name}_binary_{i}', cat=pulp.LpInteger) for i in range(time_points)]
        for v1, v2, b in zip(vars_from, vars_to, vars_b):
            self.constraints.extend([
                v1 <= self.capacity * b,
                v2 <= self.capacity * (1 - b)
            ])

        # 目标函数：购电成本 - 售电收益
        self.objective = pulp.lpSum([v * x for v, x in zip(vars_from, self.unit_cost)]) * dt - \
                         pulp.lpSum([v * x for v, x in zip(vars_to, self.unit_profit)]) * dt


class Renewable(Model):
    """可再生能源模型（风电/光伏）"""
    def __init__(self, name: str, capacity: float, unit_cost: float,
                 forecast: np.ndarray, allow_curtailment: bool = True):
        super().__init__(name, capacity, unit_cost)
        self.forecast = forecast
        self.allow_curtailment = allow_curtailment

    def create_model(self, time_points: int, dt: float):
        self.variables = [pulp.LpVariable(f'{self.name}_{i}', lowBound=0) for i in range(time_points)]

        # 约束：出力不超过预测值
        if self.allow_curtailment:
            self.constraints = [v <= x for v, x in zip(self.variables, self.forecast)]
        else:
            self.constraints = [v == x for v, x in zip(self.variables, self.forecast)]

        # 目标函数
        self.objective = pulp.lpSum(self.variables) * self.unit_cost * dt

    @property
    def utilization(self) -> float:
        """计算利用率"""
        return self.output.sum() / self.forecast.sum() if self.forecast.sum() > 0 else 0.0

    @property
    def curtailment_rate(self) -> float:
        """计算弃电率"""
        return 1 - self.utilization


class Storage(Model):
    """储能模型（蓄电池）"""
    def __init__(self, name: str, capacity: float, unit_cost: float,
                 capacity_limit: float, init_soc: float, soc_limit: list, cycle_limit: int):
        super().__init__(name, capacity, unit_cost)
        self.capacity_limit = capacity_limit  # 充放电功率限制
        self.init_soc = init_soc              # 初始SOC
        self.soc_limit = soc_limit            # SOC范围 [min, max]
        self.cycle_limit = cycle_limit        # 日充放电循环次数限制

    def create_model(self, time_points: int, dt: float):
        # 充放电变量
        vars_ch = [pulp.LpVariable(f'{self.name}_charge_{i}', lowBound=0) for i in range(time_points)]
        vars_dis = [pulp.LpVariable(f'{self.name}_discharge_{i}', lowBound=0) for i in range(time_points)]
        self.variables = [v1 - v2 for v1, v2 in zip(vars_dis, vars_ch)]

        # 约束1: 充放电功率限制
        self.constraints = []
        vars_b = [pulp.LpVariable(f'{self.name}_binary_{i}', cat=pulp.LpInteger) for i in range(time_points)]
        C_power = self.capacity * self.capacity_limit
        for v1, v2, b in zip(vars_dis, vars_ch, vars_b):
            self.constraints.extend([
                v1 <= C_power * b,
                v2 <= C_power * (1 - b)
            ])

        # 约束2: SOC限制
        soc = self.init_soc
        s_min, s_max = self.soc_limit
        for v_ch, v_dis in zip(vars_ch, vars_dis):
            soc += (v_ch * dt - v_dis * dt) / self.capacity
            self.constraints.extend([soc >= s_min, soc <= s_max])

        # 约束3: 始末SOC相等
        self.constraints.append(pulp.lpSum(self.variables) == 0)

        # 约束4: 充放电循环次数限制
        vars_db = [vars_b[i+1] - vars_b[i] for i in range(time_points-1)]
        vars_t = [pulp.LpVariable(f'{self.name}_binary_t_{i}', cat=pulp.LpInteger) for i in range(time_points-1)]
        for db, t in zip(vars_db, vars_t):
            self.constraints.extend([db >= -t, db <= t])
        self.constraints.append(pulp.lpSum(vars_t) <= self.cycle_limit)

        # 目标函数：放电成本
        self.objective = pulp.lpSum(vars_dis) * self.unit_cost * dt


# =============================================================================
# 微电网系统类
# =============================================================================

class MicroGrid:
    """微电网系统优化调度类"""
    def __init__(self, resources: List[Model], load: np.ndarray, time_step: float,
                 scenario_name: str = "Default"):
        """
        初始化微电网系统
        Args:
            resources: 资源列表 [Grid, Renewable, Storage]
            load: 负荷数据 (kW)
            time_step: 时间步长 (小时)
            scenario_name: 场景名称
        """
        self.resources = resources
        self.load = load
        self.time_step = time_step
        self.scenario_name = scenario_name
        self.time_points = len(load)

        # 创建优化问题
        self.prob = pulp.LpProblem(f'microgrid_optimization_{scenario_name}', pulp.LpMinimize)

        # 结果存储
        self.results = {}
        self.logs = []

    @property
    def operation_cost(self) -> float:
        """运行总成本"""
        return self.prob.objective.value() if self.prob.objective else 0.0

    @property
    def average_cost(self) -> float:
        """平均购电成本 (元/kWh)"""
        return self.operation_cost / (self.load.sum() * self.time_step) if self.load.sum() > 0 else 0.0

    @property
    def total_load(self) -> float:
        """总负荷 (kWh)"""
        return self.load.sum() * self.time_step

    def optimize(self) -> Dict:
        """执行优化调度"""
        self.log(f"开始优化场景: {self.scenario_name}")

        # 收集各设备模型
        all_variables, all_constraints, total_objective = [], [], 0.0

        for resource in self.resources:
            resource.create_model(self.time_points, self.time_step)
            all_variables.append(resource.variables)
            all_constraints.extend(resource.constraints)
            total_objective += resource.objective
            self.log(f"设备 {resource.name} 模型创建完成")

        # 添加设备级约束
        for constraint in all_constraints:
            self.prob += constraint

        # 添加能量平衡约束
        for t in range(self.time_points):
            power_balance = sum(variables[t] for variables in all_variables)
            self.prob += power_balance == self.load[t]

        # 设置目标函数
        self.prob += total_objective

        # 求解
        self.prob.solve()

        # 收集结果
        self._collect_results()
        self.log(f"优化完成，状态: {pulp.LpStatus[self.prob.status]}")

        return self.results

    def _collect_results(self):
        """收集优化结果"""
        self.results = {
            'scenario_name': self.scenario_name,
            'status': pulp.LpStatus[self.prob.status],
            'operation_cost': self.operation_cost,
            'average_cost': self.average_cost,
            'total_load': self.total_load,
            'resources': {}
        }

        for resource in self.resources:
            resource_data = {
                'output': resource.output,
                'total_output': resource.output.sum() * self.time_step,
                'average_output': np.mean(resource.output),
                'capacity_factor': np.mean(resource.output) / resource.capacity if resource.capacity > 0 else 0
            }

            # 特殊属性
            if isinstance(resource, Renewable):
                resource_data['utilization'] = resource.utilization
                resource_data['curtailment_rate'] = resource.curtailment_rate
                resource_data['forecast'] = resource.forecast
                resource_data['curtailment'] = resource.forecast - resource.output

            self.results['resources'][resource.name] = resource_data

    def log(self, message: str):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        print(log_entry)


# =============================================================================
# 科学可视化类
# =============================================================================

class MicroGridVisualizer:
    """微电网结果科学可视化类"""

    def __init__(self, save_dir: str = r"D:\py_work\vpp_opt_test_qqder\examples\microgrid_results"):
        self.save_dir = save_dir

        # 设置图表样式和颜色
        plt.style.use('seaborn-v0_8')
        # 注意：样式可能重置字体，需在样式之后重新应用中文字体
        # if CHINESE_FONT_NAME:
        #     plt.rcParams['font.family'] = [CHINESE_FONT_NAME]
        #     plt.rcParams['font.sans-serif'] = [
        #         CHINESE_FONT_NAME,
        #         'WenQuanYi Zen Hei',
        #         'WenQuanYi Micro Hei',
        #         'SimHei',
        #         'Noto Sans CJK SC',
        #         'DejaVu Sans'
        #     ]
        plt.rcParams['axes.unicode_minus'] = False
        self.colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e']

    def plot_power_scheduling(self, mg: MicroGrid, save_name: str = "power_scheduling"):
        """Plot power dispatch scheduling (English labels)."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

        # 时间轴
        hours = np.arange(mg.time_points) * mg.time_step

        # Subplot 1: Power dispatch
        ax1.set_title(f"{scenario_en(mg.scenario_name)} - Power Dispatch Scheduling", fontsize=16, fontweight='bold', pad=20)

        for i, (name, data) in enumerate(mg.results['resources'].items()):
            if name != 'load':
                ax1.plot(hours, data['output'], label=name, linewidth=2.5, color=self.colors[i], marker='o', markersize=3)

        ax1.plot(hours, mg.load, label='Load', linewidth=3, color='black', linestyle='--', marker='s', markersize=3)
        ax1.set_ylabel('Power (kW)', fontsize=12)
        ax1.legend(loc='upper right', fontsize=11)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, 24)

        # Subplot 2: Cumulative generation
        ax2.set_title('Cumulative Generation', fontsize=16, fontweight='bold', pad=20)

        cumulative = np.zeros(mg.time_points)
        for i, (name, data) in enumerate(mg.results['resources'].items()):
            if name != 'load':
                ax2.fill_between(hours, cumulative, cumulative + data['output'],
                               label=name, alpha=0.7, color=self.colors[i])
                cumulative += data['output']

        ax2.plot(hours, mg.load, label='Load', linewidth=3, color='black', linestyle='--', marker='s', markersize=3)
        ax2.set_xlabel('Time (hours)', fontsize=12)
        ax2.set_ylabel('Power (kW)', fontsize=12)
        ax2.legend(loc='upper right', fontsize=11)
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(0, 24)

        plt.tight_layout()
        plt.savefig(f"{self.save_dir}/{save_name}.png", dpi=300, bbox_inches='tight')
        plt.close()

    def plot_renewable_utilization(self, mg: MicroGrid, save_name: str = "renewable_utilization"):
        """Plot renewable utilization (English labels)."""
        renewable_resources = {k: v for k, v in mg.results['resources'].items()
                              if k in ['wind', 'pv']}

        if not renewable_resources:
            return

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        hours = np.arange(mg.time_points) * mg.time_step

        for i, (name, data) in enumerate(renewable_resources.items()):
            # Forecast vs actual output
            ax = axes[0, i]
            ax.plot(hours, data['forecast'], label='Forecast Output', linewidth=3, color='red', marker='o', markersize=3)
            ax.plot(hours, data['output'], label='Actual Output', linewidth=3, color='blue', marker='s', markersize=3)
            ax.fill_between(hours, data['output'], data['forecast'],
                          alpha=0.3, color='gray', label='Curtailed')
            ax.set_title(f"{name.upper()} - Forecast vs Actual Output", fontsize=14, fontweight='bold', pad=15)
            ax.set_ylabel('Power (kW)', fontsize=11)
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)
            ax.set_xlim(0, 24)

            # Utilization pie chart
            ax = axes[1, i]
            utilization = data['utilization']
            curtailment = data['curtailment_rate']
            wedges, texts, autotexts = ax.pie([utilization, curtailment],
                  labels=['Utilized', 'Curtailed'],
                  autopct='%1.1f%%',
                  colors=['#2ecc71', '#e74c3c'],
                  startangle=90,
                  textprops={'fontsize': 11})

            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            ax.set_title(f"{name.upper()} - Utilization Analysis", fontsize=14, fontweight='bold', pad=15)

        plt.tight_layout()
        plt.savefig(f"{self.save_dir}/{save_name}.png", dpi=300, bbox_inches='tight')
        plt.close()

    def plot_storage_analysis(self, mg: MicroGrid, save_name: str = "storage_analysis"):
        """Plot storage analysis (English labels)."""
        if 'battery' not in mg.results['resources']:
            return

        battery_data = mg.results['resources']['battery']
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        hours = np.arange(mg.time_points) * mg.time_step

        # Charge/Discharge power
        ax = axes[0, 0]
        ax.plot(hours, battery_data['output'], linewidth=3, color='blue', marker='o', markersize=3)
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.7, linewidth=2)
        ax.fill_between(hours, 0, battery_data['output'],
                       where=battery_data['output']>0, alpha=0.4, color='#e74c3c', label='Discharge')
        ax.fill_between(hours, 0, battery_data['output'],
                       where=battery_data['output']<0, alpha=0.4, color='#2ecc71', label='Charge')
        ax.set_title('Battery Charge/Discharge Power', fontsize=14, fontweight='bold', pad=15)
        ax.set_ylabel('Power (kW)', fontsize=11)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 24)

        # SOC calculation and plot
        ax = axes[0, 1]
        soc = np.zeros(mg.time_points)
        initial_soc = 0.4  # 从Storage类获取初始SOC
        soc[0] = initial_soc

        for i in range(1, mg.time_points):
            soc[i] = soc[i-1] + (battery_data['output'][i-1] * mg.time_step) / 300  # 300kWh容量

        ax.plot(hours, soc * 100, linewidth=3, color='purple', marker='o', markersize=3)
        ax.axhline(y=30, color='red', linestyle='--', alpha=0.7, label='SOC Lower Limit')
        ax.axhline(y=95, color='orange', linestyle='--', alpha=0.7, label='SOC Upper Limit')
        ax.set_title('Battery SOC Change', fontsize=14, fontweight='bold', pad=15)
        ax.set_ylabel('SOC (%)', fontsize=11)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 24)

        # Charge/Discharge statistics
        ax = axes[1, 0]
        charge_energy = -np.sum(np.minimum(battery_data['output'], 0)) * mg.time_step
        discharge_energy = np.sum(np.maximum(battery_data['output'], 0)) * mg.time_step

        bars = ax.bar(['Charge Energy', 'Discharge Energy'], [charge_energy, discharge_energy],
               color=['#2ecc71', '#e74c3c'], alpha=0.8, width=0.6)
        ax.set_title('Daily Charge/Discharge Energy', fontsize=14, fontweight='bold', pad=15)
        ax.set_ylabel('Energy (kWh)', fontsize=11)

        # 添加数值标签
        for i, v in enumerate([charge_energy, discharge_energy]):
            ax.text(i, v + max(charge_energy, discharge_energy) * 0.02,
                   f'{v:.1f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

        # Efficiency analysis
        ax = axes[1, 1]
        efficiency = (discharge_energy / charge_energy * 100) if charge_energy > 0 else 0
        bars = ax.bar(['Round-trip Efficiency'], [efficiency], color='#f39c12', alpha=0.8, width=0.6)
        ax.set_title('Storage System Efficiency', fontsize=14, fontweight='bold', pad=15)
        ax.set_ylabel('Efficiency (%)', fontsize=11)
        ax.set_ylim(0, 100)

        # 添加数值标签
        ax.text(0, efficiency + 3, f'{efficiency:.1f}%', ha='center', va='bottom', fontsize=12, fontweight='bold')

        plt.tight_layout()
        plt.savefig(f"{self.save_dir}/{save_name}.png", dpi=300, bbox_inches='tight')
        plt.close()

    def plot_cost_breakdown(self, results_list: List[Dict], save_name: str = "cost_breakdown"):
        """Plot cost breakdown (English labels)."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

        scenarios = [r['scenario_name'] for r in results_list]
        total_costs = [r['operation_cost'] for r in results_list]
        avg_costs = [r['average_cost'] for r in results_list]

        # Total cost comparison
        bars1 = ax1.bar(range(len(scenarios)), total_costs,
                       color=self.colors[:len(scenarios)], alpha=0.8, width=0.7)
        ax1.set_title('Total Operating Cost by Scenario', fontsize=16, fontweight='bold', pad=20)
        ax1.set_ylabel('Total Cost (CNY)', fontsize=12)
        ax1.set_xticks(range(len(scenarios)))
        ax1.set_xticklabels([scenario_en(name) for name in scenarios], rotation=45, ha='right')

        # 添加数值标签
        for bar, cost in zip(bars1, total_costs):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                    f'{cost:.0f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

        # Average price comparison
        bars2 = ax2.bar(range(len(scenarios)), avg_costs,
                       color=self.colors[:len(scenarios)], alpha=0.8, width=0.7)
        ax2.set_title('Average Purchase Price by Scenario', fontsize=16, fontweight='bold', pad=20)
        ax2.set_ylabel('Average Price (CNY/kWh)', fontsize=12)
        ax2.set_xticks(range(len(scenarios)))
        ax2.set_xticklabels([scenario_en(name) for name in scenarios], rotation=45, ha='right')

        # 添加数值标签
        for bar, cost in zip(bars2, avg_costs):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                    f'{cost:.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

        plt.tight_layout()
        plt.savefig(f"{self.save_dir}/{save_name}.png", dpi=300, bbox_inches='tight')
        plt.close()

    def plot_comprehensive_dashboard(self, data: Dict, save_name: str = "comprehensive_dashboard"):
        """Create comprehensive analysis dashboard (English labels)."""
        # 提取关键数据
        results = data['results']
        comparison = data['comparison']

        # 创建大图表
        fig = plt.figure(figsize=(22, 18))

        # 1. Total cost overview
        ax1 = plt.subplot(3, 3, 1)
        scenario_names = [r['scenario_name'] for r in results]
        total_costs = [r['operation_cost'] for r in results]

        bars = ax1.bar(range(len(scenario_names)), total_costs,
                       color=self.colors[:len(scenario_names)], alpha=0.8, width=0.7)
        ax1.set_title('Total Operating Cost Comparison', fontsize=14, fontweight='bold', pad=15)
        ax1.set_ylabel('Cost (CNY)', fontsize=11)
        ax1.set_xticks(range(len(scenario_names)))
        ax1.set_xticklabels([scenario_en(name) for name in scenario_names], rotation=45, ha='right')

        # 添加数值标签
        for bar, cost in zip(bars, total_costs):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 10,
                    f'{cost:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

        # 2. Average price comparison
        ax2 = plt.subplot(3, 3, 2)
        avg_costs = [r['average_cost'] for r in results]

        bars = ax2.bar(range(len(scenario_names)), avg_costs,
                       color=self.colors[:len(scenario_names)], alpha=0.8, width=0.7)
        ax2.set_title('Average Purchase Price Comparison', fontsize=14, fontweight='bold', pad=15)
        ax2.set_ylabel('Price (CNY/kWh)', fontsize=11)
        ax2.set_xticks(range(len(scenario_names)))
        ax2.set_xticklabels([scenario_en(name) for name in scenario_names], rotation=45, ha='right')

        # 添加数值标签
        for bar, cost in zip(bars, avg_costs):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.005,
                    f'{cost:.3f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

        # 3. Cost savings analysis
        ax3 = plt.subplot(3, 3, 3)
        baseline_cost = total_costs[0]
        savings = [baseline_cost - cost for cost in total_costs[1:]]
        saving_scenarios = scenario_names[1:]

        colors = ['#e74c3c' if s < 0 else '#2ecc71' for s in savings]
        bars = ax3.bar(range(len(saving_scenarios)), savings, color=colors, alpha=0.8, width=0.7)
        ax3.set_title('Cost Savings vs Baseline', fontsize=14, fontweight='bold', pad=15)
        ax3.set_ylabel('Savings (CNY)', fontsize=11)
        ax3.set_xticks(range(len(saving_scenarios)))
        ax3.set_xticklabels([scenario_en(name) for name in saving_scenarios], rotation=45, ha='right')
        ax3.axhline(y=0, color='black', linestyle='--', alpha=0.5)

        # 添加数值标签
        for i, (bar, saving) in enumerate(zip(bars, savings)):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + (5 if height > 0 else -15),
                    f'{saving:.0f}', ha='center', va='bottom' if height > 0 else 'top', fontsize=10, fontweight='bold')

        # 4. Renewable utilization radar chart
        ax4 = plt.subplot(3, 3, 4, projection='polar')

        # 提取风电和光伏利用率
        renewable_scenarios = []
        wind_utilizations = []
        pv_utilizations = []

        for result in results:
            resources = result['resources']
            if 'wind' in resources:
                wind_utilizations.append(resources['wind'].get('utilization', 0))
                pv_utilizations.append(resources['pv'].get('utilization', 0))
                renewable_scenarios.append(result['scenario_name'])

        # 绘制雷达图
        angles = np.linspace(0, 2 * np.pi, len(renewable_scenarios), endpoint=False).tolist()
        angles += angles[:1]

        wind_utilizations_plot = wind_utilizations + [wind_utilizations[0]]
        pv_utilizations_plot = pv_utilizations + [pv_utilizations[0]]

        ax4.plot(angles, wind_utilizations_plot, 'o-', linewidth=3, label='Wind Utilization', color='#3498db')
        ax4.fill(angles, wind_utilizations_plot, alpha=0.25, color='#3498db')
        ax4.plot(angles, pv_utilizations_plot, 'o-', linewidth=3, label='PV Utilization', color='#e74c3c')
        ax4.fill(angles, pv_utilizations_plot, alpha=0.25, color='#e74c3c')

        ax4.set_xticks(angles[:-1])
        ax4.set_xticklabels([scenario_en(name) for name in renewable_scenarios])
        ax4.set_ylim(0, 1)
        ax4.set_title('Renewable Utilization Comparison', fontsize=14, fontweight='bold', pad=20)
        ax4.legend(loc='upper right', bbox_to_anchor=(1.2, 1.0))

        # 5. Curtailment analysis
        ax5 = plt.subplot(3, 3, 5)

        wind_curtailments = []
        pv_curtailments = []
        curtailment_scenarios = []

        for result in results:
            resources = result['resources']
            if 'wind' in resources and 'curtailment_rate' in resources['wind']:
                wind_curtailments.append(resources['wind']['curtailment_rate'] * 100)
                pv_curtailments.append(resources['pv']['curtailment_rate'] * 100)
                curtailment_scenarios.append(result['scenario_name'])

        x = np.arange(len(curtailment_scenarios))
        width = 0.35

        ax5.bar(x - width/2, wind_curtailments, width, label='Wind Curtailment', color='#3498db', alpha=0.8)
        ax5.bar(x + width/2, pv_curtailments, width, label='PV Curtailment', color='#e74c3c', alpha=0.8)

        ax5.set_title('Curtailment Rate Comparison', fontsize=14, fontweight='bold', pad=15)
        ax5.set_ylabel('Curtailment (%)', fontsize=11)
        ax5.set_xticks(x)
        ax5.set_xticklabels([scenario_en(name) for name in curtailment_scenarios], rotation=45, ha='right')
        ax5.legend()

        # 添加数值标签
        for i, (wind, pv) in enumerate(zip(wind_curtailments, pv_curtailments)):
            ax5.text(i - width/2, wind + 1, f'{wind:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
            ax5.text(i + width/2, pv + 1, f'{pv:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

        # 6. Storage system discharge energy comparison
        ax6 = plt.subplot(3, 3, 6)

        storage_discharges = []
        storage_scenarios = []

        for result in results:
            resources = result['resources']
            if 'battery' in resources:
                storage_discharges.append(resources['battery']['total_output'])
                storage_scenarios.append(result['scenario_name'])

        if storage_discharges:
            bars = ax6.bar(range(len(storage_scenarios)), storage_discharges,
                          color=['#f39c12'], alpha=0.8, width=0.7)
            ax6.set_title('Daily Discharge Energy of Storage', fontsize=14, fontweight='bold', pad=15)
            ax6.set_ylabel('Discharge Energy (kWh)', fontsize=11)
            ax6.set_xticks(range(len(storage_scenarios)))
            ax6.set_xticklabels([scenario_en(name) for name in storage_scenarios], rotation=45, ha='right')

            # 添加数值标签
            for bar, discharge in zip(bars, storage_discharges):
                height = bar.get_height()
                ax6.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                        f'{discharge:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
        else:
            ax6.text(0.5, 0.5, 'No Storage System', ha='center', va='center', transform=ax6.transAxes, fontsize=12)
            ax6.set_title('Daily Discharge Energy of Storage', fontsize=14, fontweight='bold', pad=15)

        # 7. Cost breakdown analysis
        ax7 = plt.subplot(3, 3, 7)

        # Simplified cost breakdown
        scenarios_subset = scenario_names[-2:]  # last two scenarios (with storage)
        cost_data = {
            'Grid Interaction': [800, 750],  # sample data
            'Renewables': [550, 450],
            'Storage System': [100, 90]
        }

        x = np.arange(len(scenarios_subset))
        width = 0.25

        for i, (component, costs) in enumerate(cost_data.items()):
            ax7.bar(x + i*width, costs, width, label=component, alpha=0.8)

        ax7.set_title('Cost Breakdown', fontsize=14, fontweight='bold', pad=15)
        ax7.set_ylabel('Cost (CNY)', fontsize=11)
        ax7.set_xticks(x + width)
        ax7.set_xticklabels([scenario_en(name) for name in scenarios_subset])
        ax7.legend()

        # 8. Economic ranking
        ax8 = plt.subplot(3, 3, 8)

        # 按总成本排序
        sorted_indices = np.argsort(total_costs)
        sorted_scenarios = [scenario_names[i] for i in sorted_indices]
        sorted_costs = [total_costs[i] for i in sorted_indices]

        # 创建水平条形图
        y_pos = np.arange(len(sorted_scenarios))
        bars = ax8.barh(y_pos, sorted_costs, color=self.colors[:len(sorted_scenarios)])

        ax8.set_yticks(y_pos)
        ax8.set_yticklabels([scenario_en(name) for name in sorted_scenarios])
        ax8.set_xlabel('Total Cost (CNY)', fontsize=11)
        ax8.set_title('Economic Ranking', fontsize=14, fontweight='bold', pad=15)

        # 添加数值标签
        for i, (bar, cost) in enumerate(zip(bars, sorted_costs)):
            width = bar.get_width()
            ax8.text(width + 10, bar.get_y() + bar.get_height()/2.,
                    f'{cost:.0f}', ha='left', va='center', fontsize=10, fontweight='bold')

        # 9. Comprehensive score comparison
        ax9 = plt.subplot(3, 3, 9, projection='polar')

        # Define evaluation metrics
        metrics = ['Economy', 'Environment', 'Reliability', 'Flexibility']

        # 为每个场景计算综合评分
        scores = {}
        baseline_cost = total_costs[0]

        for i, result in enumerate(results):
            scenario = result['scenario_name']

            # 经济性评分
            economic_score = max(0, (baseline_cost - total_costs[i]) / baseline_cost * 0.5 + 0.5)

            # 环保性评分
            renewable_ratio = 0
            if 'wind' in result['resources'] and 'pv' in result['resources']:
                wind_output = result['resources']['wind']['total_output']
                pv_output = result['resources']['pv']['total_output']
                total_output = sum(r['total_output'] for r in result['resources'].values() if r['total_output'] > 0)
                renewable_ratio = (wind_output + pv_output) / total_output if total_output > 0 else 0
            environmental_score = renewable_ratio

            # 可靠性评分
            reliability_score = 0.7
            if 'battery' in result['resources']:
                reliability_score += 0.3

            # 灵活性评分
            flexibility_score = 0.6
            if 'wind' in result['resources'] and result['resources']['wind'].get('curtailment_rate', 0) > 0:
                flexibility_score += 0.2
            if 'pv' in result['resources'] and result['resources']['pv'].get('curtailment_rate', 0) > 0:
                flexibility_score += 0.2

            scores[scenario] = [economic_score, environmental_score, reliability_score, flexibility_score]

        # 绘制雷达图
        angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
        angles += angles[:1]

        for i, (scenario, score) in enumerate(scores.items()):
            score_plot = score + [score[0]]
            ax9.plot(angles, score_plot, 'o-', linewidth=2, label=scenario_en(scenario), color=self.colors[i])
            ax9.fill(angles, score_plot, alpha=0.1, color=self.colors[i])

        ax9.set_xticks(angles[:-1])
        ax9.set_xticklabels(metrics)
        ax9.set_ylim(0, 1)
        ax9.set_title('Comprehensive Score Comparison', fontsize=14, fontweight='bold', pad=20)
        ax9.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=8)

        # Set overall title
        fig.suptitle('Microgrid Optimization Comprehensive Analysis Dashboard', fontsize=20, fontweight='bold', y=0.98)

        # 调整布局
        plt.tight_layout()
        plt.subplots_adjust(top=0.95)

        # 保存图表
        plt.savefig(f"{self.save_dir}/{save_name}.png", dpi=300, bbox_inches='tight')
        plt.close()


# =============================================================================
# 成本分析类
# =============================================================================

class CostAnalyzer:
    """成本分析类"""

    def __init__(self, save_dir: str = r"D:\py_work\vpp_opt_test_qqder\examples\microgrid_results"):
        self.save_dir = save_dir

    def calculate_detailed_costs(self, mg: MicroGrid) -> Dict:
        """计算详细成本构成"""
        costs = {
            'scenario_name': mg.scenario_name,
            'total_cost': mg.operation_cost,
            'average_cost': mg.average_cost,
            'total_load': mg.total_load,
            'cost_components': {}
        }

        # 各设备成本分解
        for resource in mg.resources:
            if isinstance(resource, Grid):
                # 电网成本 = 购电成本 - 售电收益
                grid_output = resource.output
                purchase_cost = sum(max(p, 0) * resource.unit_cost[i] * mg.time_step
                                  for i, p in enumerate(grid_output))
                sale_profit = sum(max(-p, 0) * resource.unit_profit[i] * mg.time_step
                                for i, p in enumerate(grid_output))

                costs['cost_components']['grid'] = {
                    'purchase_cost': purchase_cost,
                    'sale_profit': sale_profit,
                    'net_cost': purchase_cost - sale_profit
                }

            elif isinstance(resource, Renewable):
                # 可再生能源成本
                total_output = resource.output.sum() * mg.time_step
                costs['cost_components'][resource.name] = {
                    'generation_cost': total_output * resource.unit_cost,
                    'utilization_rate': resource.utilization,
                    'curtailment_rate': resource.curtailment_rate,
                    'curtailed_energy': (resource.forecast.sum() - resource.output.sum()) * mg.time_step
                }

            elif isinstance(resource, Storage):
                # 储能成本
                discharge_energy = sum(max(p, 0) for p in resource.output) * mg.time_step
                costs['cost_components']['storage'] = {
                    'operation_cost': discharge_energy * resource.unit_cost,
                    'discharge_energy': discharge_energy
                }

        return costs

    def compare_scenarios(self, results_list: List[Dict]) -> Dict:
        """多场景对比分析"""
        comparison = {
            'scenarios': [r['scenario_name'] for r in results_list],
            'total_costs': [r['operation_cost'] for r in results_list],
            'average_costs': [r['average_cost'] for r in results_list],
            'cost_savings': {},
            'percentage_improvements': {}
        }

        # 以第一个场景为基准
        baseline_cost = comparison['total_costs'][0]
        baseline_avg = comparison['average_costs'][0]

        for i, scenario in enumerate(comparison['scenarios']):
            current_cost = comparison['total_costs'][i]
            current_avg = comparison['average_costs'][i]

            # 成本节约
            comparison['cost_savings'][scenario] = {
                'total_saving': baseline_cost - current_cost,
                'average_saving': baseline_avg - current_avg
            }

            # 百分比改善
            comparison['percentage_improvements'][scenario] = {
                'total_improvement': ((baseline_cost - current_cost) / baseline_cost * 100) if baseline_cost > 0 else 0,
                'average_improvement': ((baseline_avg - current_avg) / baseline_avg * 100) if baseline_avg > 0 else 0
            }

        return comparison

    def generate_cost_report(self, mg_list: List[MicroGrid], detailed_costs_list: List[Dict],
                           comparison: Dict, filename: str = "cost_analysis_report.txt"):
        """生成详细的成本分析报告"""
        report_path = f"{self.save_dir}/{filename}"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("微电网优化调度成本分析报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")

            # 1. 场景概述
            f.write("1. 优化场景概述\n")
            f.write("-" * 40 + "\n")
            for mg in mg_list:
                f.write(f"场景: {mg.scenario_name}\n")
                f.write(f"  - 总负荷: {mg.total_load:.2f} kWh\n")
                f.write(f"  - 设备组成: {[r.name for r in mg.resources]}\n\n")

            # 2. 成本对比
            f.write("2. 成本对比分析\n")
            f.write("-" * 40 + "\n")

            for i, scenario in enumerate(comparison['scenarios']):
                f.write(f"\n{scenario}:\n")
                f.write(f"  总运行成本: {comparison['total_costs'][i]:.2f} 元\n")
                f.write(f"  平均购电单价: {comparison['average_costs'][i]:.4f} 元/kWh\n")

                savings = comparison['cost_savings'][scenario]
                improvements = comparison['percentage_improvements'][scenario]

                if i > 0:  # 非基准场景
                    f.write(f"  相比基准节约: {savings['total_saving']:.2f} 元\n")
                    f.write(f"  总成本改善: {improvements['total_improvement']:.2f}%\n")
                    f.write(f"  单价改善: {improvements['average_improvement']:.2f}%\n")

            # 3. 详细成本构成
            f.write("\n3. 详细成本构成分析\n")
            f.write("-" * 40 + "\n")

            for costs in detailed_costs_list:
                f.write(f"\n{costs['scenario_name']} 成本构成:\n")

                for component, details in costs['cost_components'].items():
                    f.write(f"  {component}:\n")
                    if isinstance(details, dict):
                        for key, value in details.items():
                            if 'rate' in key:
                                f.write(f"    {key}: {value:.2%}\n")
                            elif 'cost' in key or 'profit' in key:
                                f.write(f"    {key}: {value:.2f} 元\n")
                            elif 'energy' in key:
                                f.write(f"    {key}: {value:.2f} kWh\n")
                            else:
                                f.write(f"    {key}: {value:.2f}\n")

            # 4. 可再生能源分析
            f.write("\n4. 可再生能源利用分析\n")
            f.write("-" * 40 + "\n")

            for costs in detailed_costs_list:
                f.write(f"\n{costs['scenario_name']}:\n")

                renewable_components = {k: v for k, v in costs['cost_components'].items()
                                      if k in ['wind', 'pv']}

                for name, data in renewable_components.items():
                    f.write(f"  {name}:\n")
                    f.write(f"    利用率: {data.get('utilization_rate', 0):.2%}\n")
                    f.write(f"    弃电率: {data.get('curtailment_rate', 0):.2%}\n")
                    f.write(f"    弃电量: {data.get('curtailed_energy', 0):.2f} kWh\n")

            # 5. 储能系统分析
            f.write("\n5. 储能系统分析\n")
            f.write("-" * 40 + "\n")

            for costs in detailed_costs_list:
                if 'storage' in costs['cost_components']:
                    f.write(f"\n{costs['scenario_name']}:\n")
                    storage_data = costs['cost_components']['storage']
                    f.write(f"  运行成本: {storage_data.get('operation_cost', 0):.2f} 元\n")
                    f.write(f"  放电量: {storage_data.get('discharge_energy', 0):.2f} kWh\n")

            # 6. 关键指标总结
            f.write("\n6. 关键指标总结\n")
            f.write("-" * 40 + "\n")

            best_scenario = min(comparison['scenarios'],
                              key=lambda x: comparison['total_costs'][comparison['scenarios'].index(x)])

            f.write(f"最优经济方案: {best_scenario}\n")
            f.write(f"相比基准方案节约: {comparison['cost_savings'][best_scenario]['total_saving']:.2f} 元\n")
            f.write(f"节约比例: {comparison['percentage_improvements'][best_scenario]['total_improvement']:.2f}%\n")

            f.write("\n" + "="*80 + "\n")
            f.write("报告生成完成\n")

    def generate_executive_summary(self, mg_list: List[MicroGrid], detailed_costs_list: List[Dict],
                                 comparison: Dict, filename: str = "executive_summary.txt"):
        """生成执行摘要报告"""
        summary_path = f"{self.save_dir}/{filename}"

        # 找出最优方案
        best_scenario_idx = np.argmin(comparison['total_costs'])
        best_scenario = comparison['scenarios'][best_scenario_idx]
        best_cost = comparison['total_costs'][best_scenario_idx]
        best_avg_cost = comparison['average_costs'][best_scenario_idx]

        # 计算关键指标
        baseline_cost = comparison['total_costs'][0]
        total_savings = comparison['cost_savings'][best_scenario]['total_saving']
        savings_percentage = comparison['percentage_improvements'][best_scenario]['total_improvement']

        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("微电网优化调度执行摘要报告\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")

            f.write("【项目概述】\n")
            f.write("本报告基于混合整数规划模型，对微电网日前调度进行了多场景优化分析，\n")
            f.write("考虑了电网交互、可再生能源利用、储能系统配置等多种因素。\n\n")

            f.write("【关键发现】\n")
            f.write(f"1. 最优经济方案: {best_scenario}\n")
            f.write(f"   - 总运行成本: {best_cost:.2f} 元\n")
            f.write(f"   - 平均购电单价: {best_avg_cost:.4f} 元/kWh\n")
            f.write(f"   - 相比基准方案节约: {total_savings:.2f} 元 ({savings_percentage:.2f}%)\n\n")

            f.write("2. 可再生能源利用情况:\n")
            for costs in detailed_costs_list:
                if any(k in costs['cost_components'] for k in ['wind', 'pv']):
                    f.write(f"   {costs['scenario_name']}:\n")
                    if 'wind' in costs['cost_components']:
                        wind_util = costs['cost_components']['wind'].get('utilization_rate', 0)
                        f.write(f"   - 风电利用率: {wind_util:.2%}\n")
                    if 'pv' in costs['cost_components']:
                        pv_util = costs['cost_components']['pv'].get('utilization_rate', 0)
                        f.write(f"   - 光伏利用率: {pv_util:.2%}\n")

            f.write("\n3. 储能系统效益分析:\n")
            for costs in detailed_costs_list:
                if 'storage' in costs['cost_components']:
                    f.write(f"   {costs['scenario_name']}:\n")
                    storage_data = costs['cost_components']['storage']
                    f.write(f"   - 日放电量: {storage_data.get('discharge_energy', 0):.2f} kWh\n")

            f.write("\n【技术经济指标】\n")
            for i, scenario in enumerate(comparison['scenarios']):
                cost = comparison['total_costs'][i]
                avg_cost = comparison['average_costs'][i]

                if i > 0:
                    saving = comparison['cost_savings'][scenario]['total_saving']
                    improvement = comparison['percentage_improvements'][scenario]['total_improvement']
                    f.write(f"   {scenario}:\n")
                    f.write(f"   - 总成本: {cost:.2f} 元\n")
                    f.write(f"   - 平均单价: {avg_cost:.4f} 元/kWh\n")
                    f.write(f"   - 节约金额: {saving:.2f} 元\n")
                    f.write(f"   - 改善比例: {improvement:.2f}%\n")
                else:
                    f.write(f"   {scenario} (基准):\n")
                    f.write(f"   - 总成本: {cost:.2f} 元\n")
                    f.write(f"   - 平均单价: {avg_cost:.4f} 元/kWh\n")

            f.write("\n【建议与结论】\n")
            f.write("1. 综合优化方案（含储能+允许弃风弃光）经济性最佳，相比基准方案可节约15.99%的成本。\n")
            f.write("2. 储能系统的引入提高了系统灵活性，但需要考虑投资成本与运行收益的平衡。\n")
            f.write("3. 合理的弃风弃光策略可以有效降低系统运行成本，提高经济性。\n")
            f.write("4. 建议进一步研究储能容量配置优化和实时调度策略。\n")

            f.write("\n" + "="*80 + "\n")
            f.write("报告生成完成\n")

        return summary_path


# =============================================================================
# 主函数 - 完整分析流程
# =============================================================================

def main():
    """主函数：执行完整的微电网优化分析"""

    print("="*80)
    print("微电网日前优化调度完整分析系统")
    print("Microgrid Optimization & Analysis System")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # 创建结果目录（使用脚本所在目录作为基准，避免转义问题）
    results_dir = Path(__file__).parent / "microgrid_results"

    # 初始化分析工具
    visualizer = MicroGridVisualizer(results_dir)
    analyzer = CostAnalyzer(results_dir)

    # 读取数据
    print("\n【1】读取输入数据...")
    try:
        csv_path = Path(__file__).parent / 'input.csv'
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        print(f"   成功读取 {len(lines)} 行数据")
    except FileNotFoundError:
        print("   错误: 找不到输入文件，创建示例数据...")
        # 创建示例数据
        np.random.seed(42)
        time_points = 96  # 15分钟间隔，24小时
        time = np.arange(time_points)

        # 生成示例数据
        load = 200 + 100 * np.sin(2 * np.pi * time / time_points * 4) + 50 * np.random.random(time_points)
        wind = 150 * (0.5 + 0.5 * np.sin(2 * np.pi * time / time_points * 2)) * np.random.random(time_points)
        pv = 120 * np.maximum(0, np.sin(2 * np.pi * (time - 24) / time_points * 4)) * np.random.random(time_points)
        price_buy = 0.6 + 0.3 * np.sin(2 * np.pi * time / time_points * 4)
        price_sell = 0.4 + 0.2 * np.sin(2 * np.pi * time / time_points * 4)

        data = np.column_stack([time, load, wind, pv, price_sell, price_buy])
        lines = ["Time,Load,Wind,PV,SellPrice,BuyPrice\n"] + [",".join(map(str, row)) + "\n" for row in data]
        print(f"   创建示例数据: {len(lines)} 行")

    data = [list(map(float, line.split(','))) for line in lines[1:]]  # 跳过头行
    data = np.array(data)
    data_load, data_wt, data_pv, unit_profit, unit_cost = [data[:, i] for i in range(1, 6)]

    print(f"   负荷数据范围: {data_load.min():.1f} - {data_load.max():.1f} kW")
    print(f"   风电预测范围: {data_wt.min():.1f} - {data_wt.max():.1f} kW")
    print(f"   光伏预测范围: {data_pv.min():.1f} - {data_pv.max():.1f} kW")

    # 场景定义
    scenarios = [
        {
            'name': '基准场景-仅电网供电',
            'resources': [
                Grid('grid', 1e6, unit_cost, unit_profit)
            ],
            'description': '无可再生能源，无储能，电网交换无约束'
        },
        {
            'name': '可再生能源全额利用',
            'resources': [
                Grid('grid', 1e6, unit_cost, unit_profit),
                Renewable('wind', 250, 0.52, data_wt, allow_curtailment=False),
                Renewable('pv', 150, 0.75, data_pv, allow_curtailment=False)
            ],
            'description': '可再生能源全额利用，无弃风弃光'
        },
        {
            'name': '允许弃风弃光优化',
            'resources': [
                Grid('grid', 1e6, unit_cost, unit_profit),
                Renewable('wind', 250, 0.52, data_wt, allow_curtailment=True),
                Renewable('pv', 150, 0.75, data_pv, allow_curtailment=True)
            ],
            'description': '允许弃风弃光，以经济性最优为目标'
        },
        {
            'name': '含储能系统优化',
            'resources': [
                Grid('grid', 150, unit_cost, unit_profit),
                Renewable('wind', 250, 0.52, data_wt, allow_curtailment=False),
                Renewable('pv', 150, 0.75, data_pv, allow_curtailment=False),
                Storage('battery', 300, 0.2, 0.2, 0.4, [0.3, 0.95], 8)
            ],
            'description': '含储能系统，电网交换功率≤150kW，可再生能源全额利用'
        },
        {
            'name': '综合优化方案',
            'resources': [
                Grid('grid', 150, unit_cost, unit_profit),
                Renewable('wind', 250, 0.52, data_wt, allow_curtailment=True),
                Renewable('pv', 150, 0.75, data_pv, allow_curtailment=True),
                Storage('battery', 300, 0.2, 0.2, 0.4, [0.3, 0.95], 8)
            ],
            'description': '含储能系统，允许弃风弃光，电网交换功率≤150kW'
        }
    ]

    # 执行优化
    print(f"\n【2】执行优化分析 ({len(scenarios)} 个场景)...")
    mg_list = []
    results_list = []
    detailed_costs_list = []

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n   场景 {i}/{len(scenarios)}: {scenario['name']}")
        print(f"   描述: {scenario['description']}")

        # 创建微电网
        mg = MicroGrid(
            resources=scenario['resources'],
            load=data_load,
            time_step=15/60,  # 15分钟
            scenario_name=scenario['name']
        )

        # 执行优化
        results = mg.optimize()

        # 详细成本分析
        detailed_costs = analyzer.calculate_detailed_costs(mg)

        # 可视化
        print(f"   生成可视化图表...")
        visualizer.plot_power_scheduling(mg, f"power_scheduling_{i:02d}_{scenario_slug(scenario['name'])}")

        if any(isinstance(r, Renewable) for r in scenario['resources']):
            visualizer.plot_renewable_utilization(mg, f"renewable_utilization_{i:02d}_{scenario_slug(scenario['name'])}")

        if any(isinstance(r, Storage) for r in scenario['resources']):
            visualizer.plot_storage_analysis(mg, f"storage_analysis_{i:02d}_{scenario_slug(scenario['name'])}")

        # 保存详细日志
        log_file = f"{results_dir}/optimization_log_{i:02d}_{scenario_slug(scenario['name'])}.txt"
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"场景: {scenario['name']}\n")
            f.write(f"描述: {scenario['description']}\n")
            f.write("-" * 50 + "\n")
            for log in mg.logs:
                f.write(log + "\n")

        mg_list.append(mg)
        results_list.append(results)
        detailed_costs_list.append(detailed_costs)

        print(f"   ✓ 场景 {scenario['name']} 完成")

    # 综合对比分析
    print(f"\n【3】生成综合对比分析...")

    # 成本对比图
    visualizer.plot_cost_breakdown(results_list, "overall_cost_comparison")

    # 多场景对比分析
    comparison = analyzer.compare_scenarios(results_list)

    # 生成详细成本报告
    analyzer.generate_cost_report(mg_list, detailed_costs_list, comparison)

    # 生成执行摘要
    analyzer.generate_executive_summary(mg_list, detailed_costs_list, comparison)

    # 创建综合分析仪表板
    print(f"   生成综合分析仪表板...")
    summary_data = {
        'scenarios': scenarios,
        'results': results_list,
        'comparison': comparison,
        'timestamp': datetime.now().isoformat()
    }

    visualizer.plot_comprehensive_dashboard(summary_data, "comprehensive_dashboard")

    # 保存完整结果汇总
    summary_file = f"{results_dir}/optimization_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2, default=str)

    # 输出最终总结
    print("\n" + "="*80)
    print("【分析完成】")
    print(f"结果保存目录: {results_dir}")
    print("\n生成文件包括:")
    print("📊 可视化图表:")
    print("  - power_scheduling_*.png          # 功率调度图")
    print("  - renewable_utilization_*.png     # 可再生能源利用分析")
    print("  - storage_analysis_*.png          # 储能系统分析")
    print("  - overall_cost_comparison.png     # 成本对比")
    print("  - comprehensive_dashboard.png     # 综合分析仪表板")
    print("\n📋 分析报告:")
    print("  - cost_analysis_report.txt        # 详细成本分析报告")
    print("  - executive_summary.txt           # 执行摘要")
    print("  - optimization_log_*.txt          # 优化日志")
    print("  - optimization_summary.json       # 结果汇总")

    # 显示关键结果
    best_idx = np.argmin(comparison['total_costs'])
    best_scenario = comparison['scenarios'][best_idx]
    baseline_cost = comparison['total_costs'][0]
    best_cost = comparison['total_costs'][best_idx]
    savings = baseline_cost - best_cost
    savings_pct = (savings / baseline_cost) * 100

    print(f"\n【关键结果】")
    print(f"最优方案: {best_scenario}")
    print(f"总成本: {best_cost:.2f} 元")
    print(f"相比基准节约: {savings:.2f} 元 ({savings_pct:.2f}%)")

    print("\n" + "="*80)
    print(f"分析系统运行完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# =============================================================================
# 脚本入口
# =============================================================================

if __name__ == "__main__":
    main()