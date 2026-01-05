"""
完整流程测试脚本
Test Complete Workflow

确保整个虚拟电厂优化流程能够正常运行并生成所有输出文件
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


def test_complete_flow():
    """测试完整工作流程"""
    print("=" * 60)
    print("虚拟电厂完整流程测试")
    print("=" * 60)
    
    try:
        # 1. 数据生成
        print("\n1. 生成数据...")
        gen = VPPDataGenerator()
        load_data, pv_data, wind_data, price_data = gen.generate_all_data()
        print("[OK] 数据生成成功")
        
        # 2. 创建模型
        print("\n2. 创建优化模型...")
        model = VPPOptimizationModel(gen.time_index)
        energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
        print("[OK] 能源系统创建成功")
        
        # 3. 求解优化问题
        print("\n3. 求解优化问题...")
        
        # 创建优化模型
        opt_model = solph.Model(energy_system)
        print("[OK] 优化模型创建成功")
        
        # 设置CBC路径
        cbc_path = os.path.join(project_root, 'cbc', 'bin', 'cbc.exe')
        print(f"CBC路径: {cbc_path}")
        print(f"文件存在: {os.path.exists(cbc_path)}")
        
        # 使用pyomo直接调用CBC
        solver = SolverFactory('cbc', executable=cbc_path)
        
        if not solver.available():
            print("[FAIL] CBC求解器不可用")
            return False
        
        print("[OK] CBC求解器可用，开始求解...")
        
        # 求解
        results = solver.solve(opt_model, tee=True)
        
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
            
            # 保存分析结果
            saved_files = analyzer.save_results("outputs")
            print(f"[OK] 结果分析完成，保存了 {len(saved_files)} 个文件")
            for file_type, file_path in saved_files.items():
                print(f"  - {file_type}: {file_path}")
            
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
            
            # 保存报告到reports目录
            os.makedirs("outputs/reports", exist_ok=True)
            report_file = "outputs/reports/summary_report.txt"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(summary_report)
            print(f"[OK] 汇总报告已保存: {report_file}")
            
            # 打印关键指标
            print("\n[METRICS] 关键指标:")
            print(f"  - 总负荷: {technical_metrics['load_total_mwh']:.1f} MWh")
            print(f"  - 可再生能源渗透率: {technical_metrics['renewable_penetration_ratio']:.1%}")
            print(f"  - 自给自足率: {technical_metrics['self_sufficiency_ratio']:.1%}")
            print(f"  - 净运行成本: {economics['net_cost_yuan']:,.0f} 元")
            
            print("\n[SUCCESS] 完整流程测试成功！")
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
    success = test_complete_flow()
    
    if success:
        print("\n[FILES] 输出文件检查:")
        
        # 检查outputs目录
        for root, dirs, files in os.walk("outputs"):
            for file in files:
                file_path = os.path.join(root, file)
                print(f"  - {file_path}")
    else:
        print("\n[FAIL] 测试失败，请检查错误信息")
