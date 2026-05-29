"""
可视化图表生成器
Plot Generator

生成虚拟电厂优化结果的增强型可视化仪表盘。
"""

import os
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import warnings

warnings.filterwarnings("ignore")


class PlotGenerator:
    """可视化图表生成器"""

    def __init__(self):
        """初始化图表生成器"""
        plt.rcParams["font.sans-serif"] = ["SimHei", "Arial Unicode MS", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        plt.rcParams["figure.figsize"] = (18, 14)

    def generate_all_plots(
        self,
        results_df: pd.DataFrame,
        economics: Dict,
        price_data: pd.Series,
        output_dir: str = "outputs/plots",
    ) -> str:
        """生成增强版仪表盘并保存到普通目录"""
        print("正在生成可视化图表...")
        os.makedirs(output_dir, exist_ok=True)
        fig = self._build_dashboard(results_df, economics, price_data)

        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        filename = f"vpp_optimization_results_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)

        fig.savefig(filepath, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"图表已保存为: {filepath}")
        return filepath

    def generate_plots_to_session(
        self,
        results_df: pd.DataFrame,
        economics: Dict,
        price_data: pd.Series,
        session_context,
        filename: str = "optimization_results.png",
    ) -> str:
        """生成增强版仪表盘并保存到会话目录"""
        print("正在生成可视化图表...")
        fig = self._build_dashboard(results_df, economics, price_data)
        plot_path = session_context.get_file_path("plots", filename)
        fig.savefig(plot_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"图表已保存为: {plot_path}")
        return str(plot_path)

    def _build_dashboard(self, results_df: pd.DataFrame, economics: Dict, price_data: pd.Series):
        """构建 4x2 增强仪表盘"""
        fig, axes = plt.subplots(4, 2, figsize=(18, 14))
        fig.suptitle("虚拟电厂调度优化增强分析", fontsize=16, fontweight="bold")

        self._plot_generation_profile(axes[0, 0], results_df)
        self._plot_load_balance(axes[0, 1], results_df)
        self._plot_battery_operation(axes[1, 0], results_df)
        self._plot_flexible_resources(axes[1, 1], results_df)
        self._plot_ancillary_services(axes[2, 0], results_df)
        self._plot_demand_response(axes[2, 1], results_df, price_data)
        self._plot_electricity_prices(axes[3, 0], price_data)
        self._plot_cost_structure(axes[3, 1], economics)

        plt.tight_layout()
        return fig
    
    def _plot_generation_profile(self, ax, results_df):
        """绘制发电资源出力曲线"""
        time_index = results_df.index
        
        if 'pv_generation_mw' in results_df.columns:
            ax.plot(time_index, results_df['pv_generation_mw'], 
                   label='光伏发电', linewidth=2, color='orange')
        
        if 'wind_generation_mw' in results_df.columns:
            ax.plot(time_index, results_df['wind_generation_mw'], 
                   label='风力发电', linewidth=2, color='skyblue')
        
        if 'gas_generation_mw' in results_df.columns:
            ax.plot(time_index, results_df['gas_generation_mw'], 
                   label='燃气机组', linewidth=2, color='red')
        
        ax.set_title('可再生能源及传统能源出力', fontweight='bold')
        ax.set_ylabel('功率 (MW)')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_load_balance(self, ax, results_df):
        """绘制负荷与供应平衡"""
        time_index = results_df.index
        
        if 'load_demand_mw' in results_df.columns:
            ax.plot(time_index, results_df['load_demand_mw'], 
                   label='负荷需求', linewidth=2, color='black')
        
        if 'total_supply_mw' in results_df.columns:
            ax.plot(time_index, results_df['total_supply_mw'], 
                   label='总供应', linewidth=2, color='green', linestyle='--')
        
        ax.set_title('负荷需求与供应平衡', fontweight='bold')
        ax.set_ylabel('功率 (MW)')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_battery_operation(self, ax, results_df):
        """绘制储能运行状态"""
        time_index = results_df.index
        
        if 'battery_charge_mw' in results_df.columns and 'battery_discharge_mw' in results_df.columns:
            ax.bar(time_index, results_df['battery_charge_mw'], 
                  label='充电', color='blue', alpha=0.7, width=0.8)
            ax.bar(time_index, results_df['battery_discharge_mw'], 
                  label='放电', color='orange', alpha=0.7, width=0.8)
        
        ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax.set_title('储能系统充放电策略', fontweight='bold')
        ax.set_ylabel('功率 (MW)')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_ancillary_services(self, ax, results_df):
        """绘制辅助服务"""
        time_index = results_df.index

        has_ancillary_data = any(col in results_df.columns for col in 
                               ['freq_reg_up_mw', 'freq_reg_down_mw', 
                                'spin_reserve_up_mw', 'spin_reserve_down_mw'])

        if has_ancillary_data:
            if 'freq_reg_up_mw' in results_df.columns:
                ax.plot(time_index, results_df['freq_reg_up_mw'], 
                       label='向上调频', linewidth=2, color='red', linestyle='--')
            
            if 'freq_reg_down_mw' in results_df.columns:
                ax.plot(time_index, results_df['freq_reg_down_mw'], 
                       label='向下调频', linewidth=2, color='blue', linestyle='--')
            
            # 绘制备用服务
            if 'spin_reserve_up_mw' in results_df.columns:
                ax.plot(time_index, results_df['spin_reserve_up_mw'], 
                       label='向上备用', linewidth=2, color='orange', linestyle='-.')
            
            if 'spin_reserve_down_mw' in results_df.columns:
                ax.plot(time_index, results_df['spin_reserve_down_mw'], 
                       label='向下备用', linewidth=2, color='green', linestyle='-.')
            ax.set_title('辅助服务提供策略', fontweight='bold')
        else:
            self._plot_grid_trading(ax, results_df)
            ax.set_title('电网交易策略', fontweight='bold')

        ax.set_ylabel('功率 (MW)')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_flexible_resources(self, ax, results_df):
        """绘制柔性资源运行状态"""
        time_index = results_df.index

        if 'chiller_load_mw' in results_df.columns:
            ax.plot(time_index, results_df['chiller_load_mw'], 
                   label='冷机负荷', linewidth=2, color='cyan')

        if 'heat_pump_load_mw' in results_df.columns:
            ax.plot(time_index, results_df['heat_pump_load_mw'], 
                   label='热机负荷', linewidth=2, color='orange')

        if 'ev_charging_power_mw' in results_df.columns:
            ax.plot(time_index, results_df['ev_charging_power_mw'],
                   label='EV充电', linewidth=2, color='navy')

        for col in results_df.columns:
            if col.startswith('interruptible_load_') and col.endswith('_mw'):
                ax.plot(time_index, results_df[col], linewidth=1.5, linestyle='--', label=col.replace('_mw', ''))

        for col in results_df.columns:
            if col.startswith('building_hvac_') and col.endswith('_mw'):
                ax.plot(time_index, results_df[col], linewidth=1.5, linestyle='-.', label=col.replace('_mw', ''))

        ax.set_title('柔性负荷资源运行状态', fontweight='bold')
        ax.set_ylabel('功率 (MW)')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_grid_trading(self, ax, results_df):
        """绘制电网交易"""
        time_index = results_df.index

        if 'grid_purchase_mw' in results_df.columns:
            ax.plot(time_index, results_df['grid_purchase_mw'], 
                   label='购电', linewidth=2, color='red')

        if 'grid_sale_mw' in results_df.columns:
            ax.plot(time_index, results_df['grid_sale_mw'], 
                   label='售电', linewidth=2, color='green')

        ax.set_title('电网交易策略', fontweight='bold')
        ax.set_ylabel('功率 (MW)')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_demand_response(self, ax, results_df, price_data):
        """绘制需求响应效果"""
        ax2 = ax.twinx()
        time_index = results_df.index

        if 'total_flexible_load_mw' in results_df.columns:
            ax.plot(time_index, results_df['total_flexible_load_mw'],
                    label='柔性负荷总功率', linewidth=2, color='teal')

        if 'grid_purchase_mw' in results_df.columns:
            ax.fill_between(
                time_index,
                0,
                results_df['grid_purchase_mw'],
                alpha=0.2,
                color='gray',
                label='购电量'
            )

        ax2.plot(price_data.index, price_data.values, color='purple', linestyle='--', linewidth=1.8, label='电价')
        ax.set_title('需求响应与电价联动', fontweight='bold')
        ax.set_ylabel('功率 (MW)')
        ax2.set_ylabel('电价 (元/MWh)')
        self._merge_legends(ax, ax2)
        ax.grid(True, alpha=0.3)

    def _plot_electricity_prices(self, ax, price_data):
        """绘制电价曲线"""
        ax.plot(price_data.index, price_data.values, 
               label='电价', linewidth=2, color='purple')
        ax.set_title('电力市场价格', fontweight='bold')
        ax.set_ylabel('价格 (元/MWh)')
        ax.set_xlabel('时间')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_cost_structure(self, ax, economics):
        """绘制成本结构"""
        labels = []
        values = []
        colors = ['orange', 'skyblue', 'red', 'purple', 'cyan', 'gray', 'gold', 'lightgreen']

        cost_items = [
            ('renewable_cost_yuan', '可再生能源'),
            ('gas_cost_yuan', '燃气发电'),
            ('battery_total_cost_yuan', '储能运行'),
            ('adjustable_loads_cost_yuan', '可调负荷'),
            ('ev_charging_cost_yuan', 'EV充电'),
            ('interruptible_load_compensation_yuan', '可中断负荷补偿'),
            ('building_hvac_cost_yuan', '楼宇空调'),
            ('grid_purchase_cost_yuan', '电网购电')
        ]

        ancillary_revenue = economics.get('ancillary_services_revenue_yuan', 0)
        if ancillary_revenue > 0:
            cost_items.append(('ancillary_services_revenue_yuan', '辅助服务收入'))
        dr_revenue = economics.get('demand_response_revenue_yuan', 0)
        if dr_revenue > 0:
            cost_items.append(('demand_response_revenue_yuan', '需求响应收入'))

        for key, label in cost_items:
            if key in ('ancillary_services_revenue_yuan', 'demand_response_revenue_yuan'):
                if key in economics and economics[key] > 0:
                    labels.append(f'{label} (-{economics[key]:.0f}元)')
                    values.append(economics[key] * 0.3)  # 显示为较小的正值，以区分收入和成本
            elif key in economics and economics[key] > 0:
                labels.append(label)
                values.append(economics[key])

        if values:
            wedges, texts, autotexts = ax.pie(values, labels=labels, 
                                            colors=colors[:len(values)],
                                            autopct='%1.1f%%', startangle=90)
            for autotext in autotexts:
                autotext.set_fontsize(9)
            ax.set_title('运行成本与收益结构', fontweight='bold')
        else:
            ax.text(0.5, 0.5, '无成本数据', ha='center', va='center', 
                   transform=ax.transAxes, fontsize=12)
            ax.set_title('运行成本与收益结构', fontweight='bold')

    def _merge_legends(self, ax, ax2):
        """合并双坐标轴图例"""
        handles_1, labels_1 = ax.get_legend_handles_labels()
        handles_2, labels_2 = ax2.get_legend_handles_labels()
        if handles_1 or handles_2:
            ax.legend(handles_1 + handles_2, labels_1 + labels_2, loc='upper left')


if __name__ == "__main__":
    print("可视化模块已创建完成")
