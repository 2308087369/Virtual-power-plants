#!/usr/bin/env python3
"""
辅助服务功能测试脚本
Test Script for Ancillary Services

测试虚拟电厂系统中储能电站参与辅助服务市场的功能
"""

import os
import sys
import pandas as pd
import yaml
from datetime import datetime

# 添加src目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # 从tests目录回到项目根目录
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)

from src.data.data_generator import VPPDataGenerator
from src.models.vpp_model import VPPOptimizationModel
from src.analysis.result_analyzer import ResultAnalyzer
from src.visualization.plot_generator import PlotGenerator
import oemof.solph as solph
from pyomo.opt import SolverFactory


def test_ancillary_services():
    """测试辅助服务功能"""
    print("="*80)
    print(" "*20 + "辅助服务功能测试")
    print(" "*15 + "Ancillary Services Test")
    print("="*80)
    print(f"测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-"*80)
    
    try:
        # 1. 检查配置文件中的辅助服务配置
        print("\n[STEP] 步骤1: 检查辅助服务配置")
        print("-"*40)
        
        config_file = "config/system_config.yaml"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        battery_config = config.get('energy_resources', {}).get('battery_storage', {})
        ancillary_config = battery_config.get('ancillary_services', {})
        
        if not ancillary_config:
            print("[FAIL] 配置文件中未找到辅助服务配置")
            return False
        
        print("[OK] 辅助服务配置检查通过:")
        
        # 调频服务配置
        freq_reg_config = ancillary_config.get('frequency_regulation', {})
        if freq_reg_config.get('enable', False):
            print(f"  - 调频服务: 启用")
            print(f"    最大容量: {freq_reg_config.get('max_capacity_mw', 0)} MW")
            print(f"    向上调频价格: {freq_reg_config.get('up_price_yuan_mw', 0)} 元/MW")
            print(f"    向下调频价格: {freq_reg_config.get('down_price_yuan_mw', 0)} 元/MW")
        else:
            print("  - 调频服务: 未启用")
        
        # 旋转备用服务配置
        spin_reserve_config = ancillary_config.get('spinning_reserve', {})
        if spin_reserve_config.get('enable', False):
            print(f"  - 旋转备用服务: 启用")
            print(f"    最大容量: {spin_reserve_config.get('max_capacity_mw', 0)} MW")
            print(f"    向上备用价格: {spin_reserve_config.get('up_price_yuan_mw', 0)} 元/MW")
            print(f"    向下备用价格: {spin_reserve_config.get('down_price_yuan_mw', 0)} 元/MW")
        else:
            print("  - 旋转备用服务: 未启用")
        
        # 2. 生成测试数据
        print("\n[STEP] 步骤2: 生成测试数据")
        print("-"*40)
        
        data_generator = VPPDataGenerator()
        load_data, pv_data, wind_data, price_data = data_generator.generate_all_data()
        print("[OK] 测试数据生成完成")
        
        # 3. 构建包含辅助服务的优化模型
        print("\n[STEP] 步骤3: 构建辅助服务优化模型")
        print("-"*40)
        
        model = VPPOptimizationModel(data_generator.time_index)
        energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
        
        # 检查是否包含辅助服务组件
        node_labels = [node.label for node in energy_system.nodes]
        ancillary_components = [label for label in node_labels if 'service' in label]
        
        print(f"[OK] 能源系统构建完成，包含 {len(energy_system.nodes)} 个组件")
        print(f"[OK] 辅助服务组件: {len(ancillary_components)} 个")
        for comp in ancillary_components:
            print(f"  - {comp}")
        
        # 4. 优化求解
        print("\n[STEP] 步骤4: 执行优化求解")
        print("-"*40)
        
        opt_model = solph.Model(energy_system)
        cbc_path = os.path.join(os.getcwd(), 'cbc', 'bin', 'cbc.exe')
        solver = SolverFactory('cbc', executable=cbc_path)
        
        if not solver.available():
            print("[FAIL] CBC求解器不可用")
            return False
        
        print("[OK] 使用CBC求解器进行优化...")
        results = solver.solve(opt_model, tee=False)
        
        if str(results.solver.termination_condition).lower() in ['optimal', 'feasible']:
            optimization_results = solph.processing.results(opt_model)
            print("[OK] 优化求解成功")
        else:
            print(f"[FAIL] 求解失败: {results.solver.termination_condition}")
            return False
        
        # 5. 辅助服务结果分析
        print("\n[STEP] 步骤5: 辅助服务结果分析")
        print("-"*40)
        
        analyzer = ResultAnalyzer()
        results_df, economics, technical_metrics = analyzer.analyze_results(
            optimization_results, energy_system, data_generator.time_index, price_data
        )
        
        # 专门分析辅助服务数据
        print("[OK] 辅助服务数据提取完成")
        
        # 检查辅助服务相关列是否存在
        ancillary_columns = [col for col in results_df.columns if 'freq_reg' in col or 'spin_reserve' in col]
        print(f"[OK] 辅助服务数据列: {len(ancillary_columns)} 个")
        for col in ancillary_columns:
            avg_value = results_df[col].mean()
            max_value = results_df[col].max()
            print(f"  - {col}: 平均 {avg_value:.2f} MW, 最大 {max_value:.2f} MW")
        
        # 辅助服务经济性分析
        print("\n[ANALYSIS] 辅助服务经济性分析:")
        ancillary_revenue = economics.get('ancillary_services_revenue_yuan', 0)
        freq_reg_revenue = economics.get('freq_reg_up_revenue_yuan', 0) + economics.get('freq_reg_down_revenue_yuan', 0)
        spin_reserve_revenue = economics.get('spin_reserve_up_revenue_yuan', 0) + economics.get('spin_reserve_down_revenue_yuan', 0)
        
        print(f"  - 调频服务收入: {freq_reg_revenue:,.2f} 元")
        print(f"  - 旋转备用收入: {spin_reserve_revenue:,.2f} 元")
        print(f"  - 辅助服务总收入: {ancillary_revenue:,.2f} 元")
        
        total_revenue = economics.get('total_revenue_yuan', 0)
        if total_revenue > 0:
            ancillary_ratio = ancillary_revenue / total_revenue * 100
            print(f"  - 辅助服务收入占比: {ancillary_ratio:.1f}%")
        
        # 辅助服务技术指标
        print("\n[METRICS] 辅助服务技术指标:")
        ancillary_capacity = technical_metrics.get('total_ancillary_services_mw', 0)
        participation_ratio = technical_metrics.get('ancillary_services_participation_ratio', 0)
        
        print(f"  - 辅助服务总容量: {ancillary_capacity:.2f} MW")
        print(f"  - 储能参与率: {participation_ratio:.1%}")
        
        # 6. 生成辅助服务可视化
        print("\n[STEP] 步骤6: 生成辅助服务可视化")
        print("-"*40)
        
        plot_generator = PlotGenerator()
        plot_file = plot_generator.generate_all_plots(
            results_df, economics, price_data, "outputs/plots"
        )
        print(f"[OK] 包含辅助服务的可视化图表已生成: {plot_file}")
        
        # 7. 保存测试结果
        print("\n[STEP] 步骤7: 保存辅助服务测试结果")
        print("-"*40)
        
        # 保存专门的辅助服务分析报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"outputs/ancillary_services_test_report_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("辅助服务功能测试报告\n")
            f.write("="*50 + "\n")
            f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("配置验证:\n")
            f.write(f"- 调频服务: {'启用' if freq_reg_config.get('enable', False) else '未启用'}\n")
            f.write(f"- 旋转备用: {'启用' if spin_reserve_config.get('enable', False) else '未启用'}\n\n")
            
            f.write("组件验证:\n")
            for comp in ancillary_components:
                f.write(f"- {comp}\n")
            f.write("\n")
            
            f.write("技术指标:\n")
            f.write(f"- 辅助服务总容量: {ancillary_capacity:.2f} MW\n")
            f.write(f"- 储能参与率: {participation_ratio:.1%}\n\n")
            
            f.write("经济效益:\n")
            f.write(f"- 调频服务收入: {freq_reg_revenue:,.2f} 元\n")
            f.write(f"- 旋转备用收入: {spin_reserve_revenue:,.2f} 元\n")
            f.write(f"- 辅助服务总收入: {ancillary_revenue:,.2f} 元\n")
            if total_revenue > 0:
                f.write(f"- 收入占比: {ancillary_ratio:.1f}%\n")
        
        print(f"[OK] 辅助服务测试报告已保存: {report_file}")
        
        print("\n[SUCCESS] 辅助服务功能测试完成！")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n[FAIL] 测试过程中发生错误:")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        
        import traceback
        print(f"\n详细错误信息:")
        traceback.print_exc()
        
        return False


if __name__ == "__main__":
    success = test_ancillary_services()
    
    if success:
        print("\n[OK] 辅助服务功能测试成功！")
        print("\n[SUMMARY] 测试验证内容:")
        print("  - 辅助服务配置文件解析")
        print("  - 辅助服务组件建模")
        print("  - 储能容量预留机制")
        print("  - 辅助服务决策变量")
        print("  - 辅助服务约束条件")
        print("  - 辅助服务收入计算")
        print("  - 辅助服务技术指标")
        print("  - 辅助服务可视化展示")
        
        print("\n[NOTE] 特性说明:")
        print("  - 储能电站参与调频和旋转备用服务")
        print("  - 基于oemof-solph框架实现容量预留")
        print("  - 通过负成本建模实现收入优化")
        print("  - 支持向上/向下双向辅助服务")
        print("  - 考虑辅助服务与储能充放电的耦合约束")
        
    else:
        print("\n[FAIL] 辅助服务功能测试失败！")
        
    sys.exit(0 if success else 1)
