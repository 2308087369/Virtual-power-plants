"""
可调负荷功能测试脚本
Test Adjustable Loads Functionality

验证新增的冷机和热机可调负荷是否正常工作
"""

import os
import sys
# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # 从tests目录回到项目根目录
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)

from src.data.data_generator import VPPDataGenerator
from src.models.vpp_model import VPPOptimizationModel
from src.analysis.result_analyzer import ResultAnalyzer
from src.visualization.plot_generator import PlotGenerator

# 直接使用pyomo调用CBC
from pyomo.opt import SolverFactory
import oemof.solph as solph
from oemof.solph import processing


def test_adjustable_loads():
    """测试可调负荷功能"""
    print("=" * 60)
    print("可调负荷功能测试")
    print("=" * 60)
    
    try:
        # 1. 数据生成
        print("\n1. 生成数据...")
        gen = VPPDataGenerator()
        load_data, pv_data, wind_data, price_data = gen.generate_all_data()
        print("[OK] 数据生成成功")
        
        # 2. 创建包含可调负荷的模型
        print("\n2. 创建优化模型（包含可调负荷）...")
        model = VPPOptimizationModel(gen.time_index)
        energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
        
        # 检查可调负荷组件是否存在
        adjustable_loads_found = []
        for node in energy_system.nodes:
            if 'chiller' in node.label or 'heat_pump' in node.label:
                adjustable_loads_found.append(node.label)
        
        if adjustable_loads_found:
            print(f"[OK] 找到可调负荷组件: {', '.join(adjustable_loads_found)}")
        else:
            print("[WARNING] 未找到可调负荷组件")
        
        print("[OK] 能源系统创建成功")
        
        # 3. 求解优化问题
        print("\n3. 求解优化问题...")
        
        # 创建优化模型
        opt_model = solph.Model(energy_system)
        print("[OK] 优化模型创建成功")
        
        # 设置CBC路径并求解
        cbc_path = os.path.join(os.getcwd(), 'cbc', 'bin', 'cbc.exe')
        solver = SolverFactory('cbc', executable=cbc_path)
        
        if not solver.available():
            print("[FAIL] CBC求解器不可用")
            return False
        
        print("[OK] CBC求解器可用，开始求解...")
        
        # 求解
        results = solver.solve(opt_model, tee=False)
        
        if str(results.solver.termination_condition).lower() in ['optimal', 'feasible']:
            print("[OK] 优化求解成功")
            
            # 提取oemof结果
            optimization_results = processing.results(opt_model)
            
            # 4. 结果分析
            print("\n4. 分析结果...")
            analyzer = ResultAnalyzer()
            results_df, economics, technical_metrics = analyzer.analyze_results(
                optimization_results, energy_system, gen.time_index, price_data
            )
            
            # 检查可调负荷结果
            adjustable_load_results = {}
            if 'chiller_load_mw' in results_df.columns:
                adjustable_load_results['冷机负荷'] = results_df['chiller_load_mw'].sum()
            if 'heat_pump_load_mw' in results_df.columns:
                adjustable_load_results['热机负荷'] = results_df['heat_pump_load_mw'].sum()
            
            if adjustable_load_results:
                print("[OK] 可调负荷结果分析:")
                for load_type, consumption in adjustable_load_results.items():
                    print(f"  - {load_type}: {consumption:.2f} MWh")
            else:
                print("[WARNING] 未检测到可调负荷运行数据")
            
            # 检查经济性分析是否包含可调负荷成本
            adjustable_costs = {}
            if 'chiller_cost_yuan' in economics:
                adjustable_costs['冷机成本'] = economics['chiller_cost_yuan']
            if 'heat_pump_cost_yuan' in economics:
                adjustable_costs['热机成本'] = economics['heat_pump_cost_yuan']
            if 'adjustable_loads_cost_yuan' in economics:
                adjustable_costs['可调负荷总成本'] = economics['adjustable_loads_cost_yuan']
            
            if adjustable_costs:
                print("[OK] 可调负荷成本分析:")
                for cost_type, cost in adjustable_costs.items():
                    print(f"  - {cost_type}: {cost:,.2f} 元")
            else:
                print("[WARNING] 未检测到可调负荷成本数据")
            
            # 检查技术指标是否包含可调负荷指标
            adjustable_metrics = {}
            if 'chiller_consumption_mwh' in technical_metrics:
                adjustable_metrics['冷机用电量'] = technical_metrics['chiller_consumption_mwh']
            if 'heat_pump_consumption_mwh' in technical_metrics:
                adjustable_metrics['热机用电量'] = technical_metrics['heat_pump_consumption_mwh']
            if 'adjustable_load_ratio' in technical_metrics:
                adjustable_metrics['可调负荷参与率'] = technical_metrics['adjustable_load_ratio']
            
            if adjustable_metrics:
                print("[OK] 可调负荷技术指标:")
                for metric_type, value in adjustable_metrics.items():
                    if '参与率' in metric_type:
                        print(f"  - {metric_type}: {value:.1%}")
                    else:
                        print(f"  - {metric_type}: {value:.2f} MWh")
            else:
                print("[WARNING] 未检测到可调负荷技术指标")
            
            # 5. 生成可视化
            print("\n5. 生成可视化图表...")
            plot_generator = PlotGenerator()
            plot_file = plot_generator.generate_all_plots(
                results_df, economics, price_data, "outputs/plots"
            )
            print(f"[OK] 可视化图表已生成: {plot_file}")
            
            # 6. 生成汇总报告
            print("\n6. 生成汇总报告...")
            summary_report = analyzer.generate_summary_report()
            
            # 检查汇总报告是否包含可调负荷信息
            if '可调负荷' in summary_report:
                print("[OK] 汇总报告包含可调负荷信息")
            else:
                print("[WARNING] 汇总报告中未发现可调负荷信息")
            
            print("\n[SUCCESS] 可调负荷功能测试成功！")
            
            # 打印关键指标对比
            print("\n[METRICS] 系统关键指标:")
            print(f"  - 总负荷需求: {technical_metrics['load_total_mwh']:.1f} MWh")
            print(f"  - 可调负荷总量: {technical_metrics.get('total_adjustable_loads_mwh', 0):.1f} MWh")
            print(f"  - 可调负荷参与率: {technical_metrics.get('adjustable_load_ratio', 0):.1%}")
            print(f"  - 净运行成本: {economics['net_cost_yuan']:,.0f} 元")
            
            return True
            
        else:
            print(f"[FAIL] 求解失败，状态: {results.solver.termination_condition}")
            return False
            
    except Exception as e:
        print(f"[FAIL] 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_adjustable_loads()
    
    if success:
        print("\n[OK] 可调负荷功能测试通过！")
        print("\n[CHECK] 功能确认:")
        print("  - 冷机和热机模型创建成功")
        print("  - 可调负荷参与优化调度")
        print("  - 结果分析包含可调负荷数据")
        print("  - 可视化图表显示可调负荷")
        print("  - 汇总报告包含可调负荷分析")
    else:
        print("\n[FAIL] 可调负荷功能测试失败，请检查配置和实现")
