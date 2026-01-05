"""
虚拟电厂调度优化系统主程序
VPP Optimization System Main Entry

整合所有模块，执行完整的虚拟电厂优化调度流程
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Union

# 尝试在 Windows 上启用 UTF-8 输出以支持 Emoji
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

# 导入项目模块
from src.data.data_generator import VPPDataGenerator
from src.models.vpp_model import VPPOptimizationModel
from src.models.scheduling_modes import VPPSchedulingManager, SchedulingMode, OptimizationObjective
from src.solvers.optimization_solver import OptimizationSolver
from src.analysis.result_analyzer import ResultAnalyzer
from src.visualization.plot_generator import PlotGenerator
from src.utils.file_manager import VPPFileManager, SessionContext

# 导入oemof模块
import oemof.solph as solph


def setup_logging():
    """配置应用程序日志"""
    log_dir = os.path.join(current_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(log_dir, f'vpp_app_{timestamp}.log')
    
    # 获取根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 清除现有的处理器
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # 文件处理器 - 详细格式
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    # 控制台处理器 - 简洁格式，模拟 print 输出
    console_formatter = logging.Formatter('%(message)s')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)


# 初始化全局日志记录器
logger = setup_logging()


def print_header():
    """打印程序头部信息"""
    logger.info("=" * 80)
    logger.info(" " * 20 + "虚拟电厂调度优化系统")
    logger.info(" " * 15 + "Virtual Power Plant Optimization System")
    logger.info("=" * 80)
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("基于 oemof-solph 构建，采用 CBC 求解器")
    logger.info("-" * 80)


def main(scheduling_mode: Optional[str] = None):
    """主程序函数"""
    print_header()
    
    # 如果提供了调度模式参数，运行指定模式
    if scheduling_mode:
        manager = VPPSchedulingManager()
        try:
            mode = SchedulingMode(scheduling_mode)
            objective = OptimizationObjective.COST_MINIMIZATION # 命令行默认使用成本最小化
            return run_scheduling_mode(mode, objective)
        except ValueError:
            logger.error(f"[ERROR] 未知的调度模式: {scheduling_mode}")
            return False
    
    # 否则运行交互式模式选择
    return run_interactive_mode_selection()


def run_interactive_mode_selection():
    """运行交互式调度模式选择"""
    logger.info("\n[CONFIG] 虚拟电厂调度模式选择")
    logger.info("-" * 50)
    
    # 创建调度模式管理器
    manager = VPPSchedulingManager()
    
    # 选择优化目标
    logger.info("步骤1: 选择优化目标")
    available_objectives = manager.list_available_objectives()
    
    logger.info("可选的优化目标:")
    for i, (obj, description) in enumerate(available_objectives, 1):
        logger.info(f"{i}. {obj.value}: {description}")
    
    try:
        obj_choice = input(f"\n请选择优化目标 (1-{len(available_objectives)}, 默认为1): ").strip()
        
        if obj_choice == "":
            selected_objective = available_objectives[0][0]  # 默认为成本最小化
        else:
            obj_index = int(obj_choice) - 1
            if 0 <= obj_index < len(available_objectives):
                selected_objective = available_objectives[obj_index][0]
            else:
                logger.warning("[WARNING] 无效选择，使用默认目标")
                selected_objective = available_objectives[0][0]
        
        manager.set_optimization_objective(selected_objective)
        
    except (ValueError, KeyboardInterrupt):
        logger.error("\n[ERROR] 已取消操作")
        return False
    
    # 选择调度模式
    logger.info(f"\n步骤2: 选择调度模式")
    available_modes = manager.list_available_modes()
    
    logger.info("可选的调度模式:")
    for i, (mode, description) in enumerate(available_modes, 1):
        logger.info(f"{i}. {mode.value}: {description}")
    
    # 添加批量运行选项
    logger.info(f"{len(available_modes)+1}. all: 运行所有调度模式进行对比分析")
    
    try:
        choice = input(f"\n请选择调度模式 (1-{len(available_modes)+1}): ").strip()
        
        if choice == str(len(available_modes)+1) or choice.lower() == 'all':
            return run_all_modes_comparison(selected_objective)
        else:
            mode_index = int(choice) - 1
            if 0 <= mode_index < len(available_modes):
                selected_mode = available_modes[mode_index][0]
                return run_single_mode_analysis(selected_mode, selected_objective)
            else:
                logger.error("[ERROR] 无效选择")
                return False
    except (ValueError, KeyboardInterrupt):
        logger.error("\n[ERROR] 已取消操作")
        return False


def run_single_mode_analysis(mode: SchedulingMode, objective: OptimizationObjective) -> Tuple[bool, Dict]:
    """运行单个调度模式分析"""
    total_start_time = time.time()
    
    # 创建文件管理器
    file_manager = VPPFileManager()
    
    # 使用会话上下文管理文件
    with SessionContext(file_manager, mode, objective) as session:
        
        try:
            # 步骤1: 数据生成
            logger.info("\n>> 步骤1: 生成虚拟电厂数据")
            logger.info("-" * 40)
            
            data_generator = VPPDataGenerator()
            load_data, pv_data, wind_data, price_data = data_generator.generate_all_data()
            
            # 保存输入数据到会话目录
            input_data_path = data_generator.save_data_to_session(session, "input_data.csv")
            logger.info(f"[OK] 输入数据已保存: {input_data_path}")
            
            # 步骤2: 创建调度模式管理器和优化模型
            logger.info("\n>> 步骤2: 构建调度模式优化模型")
            logger.info("-" * 40)
            
            manager = VPPSchedulingManager()
            model = manager.create_optimized_model(mode, data_generator.time_index, objective)
            energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
            
            # 验证系统
            logger.info("\n>> 步骤2.1: 验证能源系统")
            logger.info("-" * 40)
            
            if not model.validate_system():
                logger.error("[ERROR] 能源系统验证失败，程序终止")
                return False, {}
            
            system_summary = model.get_system_summary()
            logger.info(f"[OK] 能源系统构建完成")
            logger.info(f"  - 组件总数: {system_summary['total_components']}")
            logger.info(f"  - 时间段数: {system_summary['time_periods']}")
            logger.info(f"  - 优化目标: {objective.value}")
            
            # 步骤3: 优化求解
            logger.info("\n>> 步骤3: 执行优化求解")
            logger.info("-" * 40)
            
            solver = OptimizationSolver()
            
            # 准备预求解回调函数，用于添加辅助服务约束
            def pre_solve_callback(model_obj):
                # 检查是否包含辅助服务组件
                has_ancillary = False
                for node in energy_system.nodes:
                    if 'service' in node.label:
                        has_ancillary = True
                        break
                
                if has_ancillary:
                    logger.info("检测到辅助服务组件，正在添加耦合约束...")
                    model.add_ancillary_service_constraints(model_obj)
                else:
                    logger.info("未检测到辅助服务组件，跳过耦合约束添加")
            
            success = solver.solve(energy_system, pre_solve_callback=pre_solve_callback)
            
            if success:
                optimization_results = solver.get_results()
                solve_stats = solver.get_solve_statistics()
                solve_time = solve_stats.get('solve_time_seconds', 0)
            else:
                logger.error("[ERROR] 求解失败")
                return False, {}
            
            # 步骤4: 分析优化结果
            logger.info("\n>> 步骤4: 分析优化结果")
            logger.info("-" * 40)
            
            analyzer = ResultAnalyzer()
            results_df, economics, technical_metrics = analyzer.analyze_results(
                optimization_results, energy_system, data_generator.time_index, price_data
            )
            
            # 保存结果到会话目录
            saved_files = analyzer.save_results_to_session(session)
            logger.info(f"[OK] 结果分析完成，已保存 {len(saved_files)} 个文件")
            
            # 步骤5: 生成可视化图表
            logger.info("\n>> 步骤5: 生成可视化图表")
            logger.info("-" * 40)
            
            plot_generator = PlotGenerator()
            plot_path = plot_generator.generate_plots_to_session(
                results_df, economics, price_data, session, "optimization_results.png"
            )
            logger.info(f"[OK] 可视化图表已生成: {plot_path}")
            
            # 步骤6: 生成模式总结报告
            logger.info("\n>> 步骤6: 生成模式总结报告")
            logger.info("-" * 40)
            
            mode_summary = generate_mode_summary_report(
                mode, model, economics, technical_metrics, analyzer
            )
            
            # 添加分析器的总结
            mode_summary += f"\n\n{analyzer.generate_summary_report()}"
            
            mode_summary_path = session.save_file(
                'summary_report', 'mode_summary_report.txt', mode_summary
            )
            logger.info(f"[OK] 模式总结报告已生成: {mode_summary_path}")
            
            # 打印关键指标
            logger.info(f"\n[METRICS] 关键指标:")
            logger.info(f"  - 总负荷: {technical_metrics['load_total_mwh']:.1f} MWh")
            logger.info(f"  - 可再生能源渗透率: {technical_metrics['renewable_penetration_ratio']:.1%}")
            logger.info(f"  - 自给自足率: {technical_metrics['self_sufficiency_ratio']:.1%}")
            logger.info(f"  - 净运行成本: {economics['net_cost_yuan']:,.0f} 元")
            logger.info(f"  - 平均供电成本: {economics['average_cost_yuan_per_mwh']:.2f} 元/MWh")
            
            # 程序完成
            total_time = time.time() - total_start_time
            logger.info(f"\n[COMPLETE] {mode.value} 调度模式（{objective.value}）优化完成！")
            logger.info(f"[TIME] 总耗时: {total_time:.2f} 秒")
            logger.info(f"[DIR] 会话目录: {session.session_dir}")
            
            return True, {
                'session_dir': str(session.session_dir),
                'economics': economics,
                'technical_metrics': technical_metrics,
                'solve_time': solve_time,
                'total_time': total_time
            }
            
        except Exception as e:
            logger.error(f"[ERROR] 系统错误: {str(e)}")
            logger.exception("详细错误堆栈:")
            return False, {}


def run_all_modes_comparison(objective: OptimizationObjective):
    """运行所有调度模式进行对比分析"""
    logger.info(f"\n[PROCESS] 运行所有调度模式进行对比分析（目标: {objective.value}）...")
    logger.info("=" * 80)
    
    manager = VPPSchedulingManager()
    available_modes = [mode for mode, _ in manager.list_available_modes()]
    
    results_summary = []
    
    for i, mode in enumerate(available_modes, 1):
        logger.info(f"\n[{i}/{len(available_modes)}] 运行 {mode.value} 模式（{objective.value}）...")
        logger.info("-" * 60)
        
        success, summary = run_single_mode_analysis(mode, objective)
        if success:
            results_summary.append((mode, summary))
        else:
            logger.error(f"[ERROR] {mode.value} 模式运行失败")
    
    # 生成对比报告
    if results_summary:
        generate_comparison_report(results_summary, objective)
        logger.info("\n[SUCCESS] 所有调度模式对比分析完成！")
        return True
    else:
        logger.error("\n[ERROR] 所有调度模式运行均失败")
        return False


def generate_comparison_report(results_summary: List[Tuple[SchedulingMode, Dict]], 
                               objective: OptimizationObjective):
    """生成调度模式对比报告"""
    logger.info("\n[METRICS] 生成调度模式对比报告")
    logger.info("-" * 60)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"outputs/modes_comparison_{objective.value}_{timestamp}.txt"
    
    os.makedirs("outputs", exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write(f"虚拟电厂调度模式对比分析报告 - {objective.value.upper()}\n")
        f.write("=" * 80 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"优化目标: {objective.value}\n\n")
        
        # 创建对比表格
        f.write("[INFO] 调度模式对比表\n")
        f.write("-" * 60 + "\n")
        
        # 表头
        f.write(f"{'调度模式':<20} {'净运行成本(元)':<15} {'平均成本(元/MWh)':<18} {'运行时间(秒)':<12}\n")
        f.write("-" * 70 + "\n")
        
        # 数据行
        for mode, summary in results_summary:
            economics = summary.get('economics', {})
            net_cost = economics.get('net_cost_yuan', 0)
            avg_cost = economics.get('average_cost_yuan_per_mwh', 0)
            run_time = summary.get('total_time', 0)
            
            f.write(f"{mode.value:<20} {net_cost:>13,.0f} {avg_cost:>16.2f} {run_time:>10.2f}\n")
        
        f.write("\n" + "=" * 80 + "\n")
    
    logger.info(f"[OK] 对比报告已保存: {report_file}")
    
    # 在控制台显示简要对比
    logger.info(f"\n[METRICS] 调度模式对比摘要（{objective.value}）:")
    logger.info(f"{'模式':<20} {'净成本(万元)':<12} {'平均成本(元/MWh)':<16}")
    logger.info("-" * 50)
    
    for mode, summary in results_summary:
        economics = summary.get('economics', {})
        net_cost = economics.get('net_cost_yuan', 0) / 10000  # 转换为万元
        avg_cost = economics.get('average_cost_yuan_per_mwh', 0)
        logger.info(f"{mode.value:<20} {net_cost:>10.1f} {avg_cost:>14.2f}")


def run_scheduling_mode(mode: SchedulingMode, objective: OptimizationObjective):
    """运行指定调度模式"""
    success, summary = run_single_mode_analysis(mode, objective)
    
    if success:
        logger.info(f"\n[SUCCESS] {mode.value} 调度模式（{objective.value}）运行成功！")
        return True
    else:
        logger.error(f"\n[ERROR] {mode.value} 调度模式运行失败")
        return False


def generate_mode_summary_report(mode: SchedulingMode, model, economics: Dict, 
                               technical_metrics: Dict, analyzer) -> str:
    """生成调度模式专用汇总报告"""
    manager = VPPSchedulingManager()
    
    report = []
    report.append("=" * 80)
    report.append(f"虚拟电厂调度模式分析报告 - {mode.value.upper()}")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 调度模式信息
    report.append("[INFO] 调度模式信息")
    report.append("-" * 40)
    report.append(f"模式名称: {mode.value}")
    report.append(f"模式描述: {manager.get_mode_description(mode)}")
    report.append(f"目标函数: {manager.get_objective_function_description(mode)}")
    report.append("")
    
    # 资源配置信息
    report.append("[CONFIG] 资源配置")
    report.append("-" * 40)
    resources = manager.get_mode_resources(mode)
    for resource, enabled in resources.items():
        status = "[OK]" if enabled else "[X] "
        report.append(f"{status} {resource}: {'启用' if enabled else '禁用'}")
    report.append("")
    
    # 经济性分析
    report.append("[ECONOMY] 经济性分析")
    report.append("-" * 40)
    for key, value in economics.items():
        if isinstance(value, (int, float)):
            if 'yuan' in key.lower():
                report.append(f"{key}: {value:,.2f} 元")
            elif 'ratio' in key.lower() or 'rate' in key.lower():
                report.append(f"{key}: {value:.2%}")
            else:
                report.append(f"{key}: {value:.2f}")
        else:
            report.append(f"{key}: {value}")
    report.append("")
    
    # 技术指标
    report.append("[METRICS] 技术指标")
    report.append("-" * 40)
    for key, value in technical_metrics.items():
        if isinstance(value, (int, float)):
            if 'mwh' in key.lower():
                report.append(f"{key}: {value:.1f} MWh")
            elif 'mw' in key.lower():
                report.append(f"{key}: {value:.1f} MW")
            elif 'ratio' in key.lower() or 'rate' in key.lower():
                report.append(f"{key}: {value:.2%}")
            else:
                report.append(f"{key}: {value:.2f}")
        else:
            report.append(f"{key}: {value}")
    report.append("")
    
    # 系统概要
    system_summary = model.get_system_summary()
    report.append("[SUMMARY] 系统概要")
    report.append("-" * 40)
    report.append(f"组件总数: {system_summary.get('total_components', 0)}")
    report.append(f"时间段数: {system_summary.get('time_periods', 0)}")
    report.append(f"包含资源: {', '.join(system_summary.get('included_resources', []))}")
    report.append("")
    
    report.append("=" * 80)
    
    return '\n'.join(report)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="虚拟电厂调度优化系统")
    parser.add_argument("--mode", type=str, help="指定调度模式名称")
    
    args = parser.parse_args()
    
    try:
        main(args.mode)
    except Exception as e:
        logger.exception("主程序执行过程中发生未捕获的异常:")
        sys.exit(1)
    finally:
        logger.info(f"\n程序结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
