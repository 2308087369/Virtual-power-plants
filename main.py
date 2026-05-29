"""
虚拟电厂调度优化系统主程序
VPP Optimization System Main Entry

扩展为真正的“日前-日内-实时”分层调度执行流程。
"""

import os
import sys
import time
import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
src_dir = os.path.join(current_dir, "src")
sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)

from src.analysis.result_analyzer import ResultAnalyzer
from src.data.data_generator import VPPDataGenerator
from src.models.scheduling_modes import OptimizationObjective, SchedulingMode, VPPSchedulingManager
from src.solvers.optimization_solver import OptimizationSolver
from src.utils.file_manager import SessionContext, VPPFileManager
from src.visualization.plot_generator import PlotGenerator


@dataclass
class StageExecutionResult:
    """单个调度阶段的执行结果"""

    stage_name: str
    display_name: str
    input_df: pd.DataFrame
    results_df: pd.DataFrame
    economics: Dict[str, Any]
    technical_metrics: Dict[str, Any]
    summary_report: str
    solve_time: float
    total_time: float
    final_soc: Optional[float]
    model_summary: Dict[str, Any]
    alignment_summary: Dict[str, Any]
    alignment_df: Optional[pd.DataFrame] = None
    rolling_window_stats: Optional[pd.DataFrame] = None


def setup_logging():
    """配置应用程序日志"""
    log_dir = os.path.join(current_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"vpp_app_{timestamp}.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    console_formatter = logging.Formatter("%(message)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    return logging.getLogger(__name__)


logger = setup_logging()


def print_header():
    """打印程序头部信息"""
    logger.info("=" * 80)
    logger.info(" " * 20 + "虚拟电厂分层调度优化系统")
    logger.info(" " * 12 + "Hierarchical Virtual Power Plant Optimization System")
    logger.info("=" * 80)
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("执行流程: 日前计划 -> 日内滚动修正 -> 实时滚动校正")
    logger.info("基于 oemof-solph 构建，采用 CBC 求解器")
    logger.info("-" * 80)


def main(
    scheduling_mode: Optional[str] = None,
    objective_name: Optional[str] = None,
    compare_all: bool = False,
    list_modes: bool = False,
):
    """主程序函数"""
    print_header()

    if list_modes:
        return print_available_modes_and_objectives()

    objective = parse_objective(objective_name)
    if compare_all:
        return run_all_modes_comparison(objective)

    if scheduling_mode:
        try:
            mode = SchedulingMode(scheduling_mode)
            return run_scheduling_mode(mode, objective)
        except ValueError:
            logger.error(f"[ERROR] 未知的调度模式: {scheduling_mode}")
            return False

    return run_interactive_mode_selection()


def print_available_modes_and_objectives():
    """列出所有调度模式和优化目标"""
    manager = VPPSchedulingManager()
    logger.info("\n可用调度模式:")
    for mode, description in manager.list_available_modes():
        logger.info(f"  - {mode.value}: {description}")

    logger.info("\n可用优化目标:")
    for objective, description in manager.list_available_objectives():
        logger.info(f"  - {objective.value}: {description}")
    return True


def parse_objective(objective_name: Optional[str]) -> OptimizationObjective:
    """解析优化目标"""
    if objective_name is None:
        return OptimizationObjective.COST_MINIMIZATION
    try:
        return OptimizationObjective(objective_name)
    except ValueError:
        logger.warning(f"[WARNING] 未知优化目标 {objective_name}，使用默认目标 cost_minimization")
        return OptimizationObjective.COST_MINIMIZATION


def run_interactive_mode_selection():
    """运行交互式调度模式选择"""
    logger.info("\n[CONFIG] 虚拟电厂调度模式选择")
    logger.info("-" * 50)

    manager = VPPSchedulingManager()
    logger.info("步骤1: 选择优化目标")
    available_objectives = manager.list_available_objectives()
    logger.info("可选的优化目标:")
    for i, (obj, description) in enumerate(available_objectives, 1):
        logger.info(f"{i}. {obj.value}: {description}")

    try:
        obj_choice = input(f"\n请选择优化目标 (1-{len(available_objectives)}, 默认为1): ").strip()
        if obj_choice == "":
            selected_objective = available_objectives[0][0]
        else:
            obj_index = int(obj_choice) - 1
            if 0 <= obj_index < len(available_objectives):
                selected_objective = available_objectives[obj_index][0]
            else:
                logger.warning("[WARNING] 无效选择，使用默认目标")
                selected_objective = available_objectives[0][0]
    except (ValueError, KeyboardInterrupt):
        logger.error("\n[ERROR] 已取消操作")
        return False

    logger.info("\n步骤2: 选择调度模式")
    available_modes = manager.list_available_modes()
    logger.info("可选的调度模式:")
    for i, (mode, description) in enumerate(available_modes, 1):
        logger.info(f"{i}. {mode.value}: {description}")
    logger.info(f"{len(available_modes)+1}. all: 运行所有调度模式进行对比分析")

    try:
        choice = input(f"\n请选择调度模式 (1-{len(available_modes)+1}): ").strip()
        if choice == str(len(available_modes) + 1) or choice.lower() == "all":
            return run_all_modes_comparison(selected_objective)

        mode_index = int(choice) - 1
        if 0 <= mode_index < len(available_modes):
            selected_mode = available_modes[mode_index][0]
            return run_single_mode_analysis(selected_mode, selected_objective)[0]

        logger.error("[ERROR] 无效选择")
        return False
    except (ValueError, KeyboardInterrupt):
        logger.error("\n[ERROR] 已取消操作")
        return False


def build_hierarchical_stage_plan(data_generator: VPPDataGenerator, multiscale_datasets: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
    """构建分层调度执行计划"""
    scheduling_config = data_generator.config.get("multi_time_scheduling", {})
    intraday_resolution = scheduling_config.get("intraday_resolution_minutes", 30)
    realtime_resolution = scheduling_config.get("realtime_resolution_minutes", 15)
    intraday_horizon_hours = scheduling_config.get("intraday_horizon_hours", 6)
    realtime_horizon_hours = scheduling_config.get("realtime_horizon_hours", 2)

    intraday_horizon_steps = max(int(intraday_horizon_hours * 60 / intraday_resolution), 1)
    realtime_horizon_steps = max(int(realtime_horizon_hours * 60 / realtime_resolution), 1)

    return [
        {
            "stage_name": "day_ahead",
            "display_name": "日前调度",
            "dataset": multiscale_datasets["day_ahead"],
            "rolling": False,
            "rolling_horizon_steps": len(multiscale_datasets["day_ahead"]),
        },
        {
            "stage_name": "intraday",
            "display_name": "日内滚动调度",
            "dataset": multiscale_datasets["intraday"],
            "rolling": True,
            "rolling_horizon_steps": intraday_horizon_steps,
        },
        {
            "stage_name": "realtime",
            "display_name": "实时滚动调度",
            "dataset": multiscale_datasets["realtime"],
            "rolling": True,
            "rolling_horizon_steps": realtime_horizon_steps,
        },
    ]


def create_pre_solve_callback(model, energy_system):
    """创建求解前回调函数"""
    def pre_solve_callback(model_obj):
        has_ancillary = any("service" in node.label for node in energy_system.nodes)
        if has_ancillary:
            logger.info("检测到辅助服务组件，正在添加耦合约束...")
            model.add_ancillary_service_constraints(model_obj)
        else:
            logger.info("未检测到辅助服务组件，跳过耦合约束添加")

    return pre_solve_callback


def create_configured_model(
    mode: SchedulingMode,
    objective: OptimizationObjective,
    time_index: pd.DatetimeIndex,
    initial_soc: Optional[float] = None,
    disable_ancillary_services: bool = False,
):
    """创建带初始SOC配置的优化模型"""
    manager = VPPSchedulingManager()
    model = manager.create_optimized_model(mode, time_index, objective)
    battery_config = model.config.get("energy_resources", {}).get("battery_storage", {})
    if initial_soc is not None and battery_config:
        min_soc = float(battery_config.get("min_soc", 0.0))
        max_soc = float(battery_config.get("max_soc", 1.0))
        battery_config["initial_soc"] = float(np.clip(initial_soc, min_soc, max_soc))
    if disable_ancillary_services and battery_config.get("ancillary_services"):
        battery_config["ancillary_services"] = {
            "frequency_regulation": {"enable": False},
            "spinning_reserve": {"enable": False},
        }
    return model, manager


def solve_dispatch_dataset(
    mode: SchedulingMode,
    objective: OptimizationObjective,
    dataset: pd.DataFrame,
    initial_soc: Optional[float] = None,
    disable_ancillary_services: bool = False,
) -> Dict[str, Any]:
    """对指定时间尺度数据执行一次完整调度求解"""
    model, manager = create_configured_model(
        mode,
        objective,
        dataset.index,
        initial_soc,
        disable_ancillary_services=disable_ancillary_services,
    )
    energy_system = model.create_energy_system(
        dataset["load_demand_mw"],
        dataset["pv_generation_mw"],
        dataset["wind_generation_mw"],
        dataset["electricity_price_yuan_mwh"],
    )

    if not model.validate_system():
        raise RuntimeError("能源系统验证失败")

    solver = OptimizationSolver()
    solve_success = solver.solve(energy_system, pre_solve_callback=create_pre_solve_callback(model, energy_system))
    if not solve_success:
        raise RuntimeError("优化求解失败")

    analyzer = ResultAnalyzer()
    results_df, economics, technical_metrics = analyzer.analyze_results(
        solver.get_results(),
        energy_system,
        dataset.index,
        dataset["electricity_price_yuan_mwh"],
    )

    final_soc = None
    if "battery_soc" in results_df.columns and not results_df["battery_soc"].empty:
        final_soc = float(results_df["battery_soc"].iloc[-1])

    return {
        "model": model,
        "manager": manager,
        "energy_system": energy_system,
        "analyzer": analyzer,
        "results_df": results_df,
        "economics": economics,
        "technical_metrics": technical_metrics,
        "summary_report": analyzer.generate_summary_report(),
        "solve_time": solver.get_solve_statistics().get("solve_time_seconds", 0.0),
        "model_summary": model.get_mode_summary(),
        "final_soc": final_soc,
    }


def analyze_precomputed_stage_results(results_df: pd.DataFrame, price_series: pd.Series) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """对滚动执行后的聚合结果重新计算指标"""
    analyzer = ResultAnalyzer()
    analyzer.time_index = results_df.index
    analyzer.results_df = results_df.copy()
    analyzer.time_step_hours = analyzer._get_time_step_hours()
    analyzer.economics = analyzer._calculate_economics(price_series.reindex(results_df.index))
    analyzer.technical_metrics = analyzer._calculate_technical_metrics()
    return analyzer.economics, analyzer.technical_metrics, analyzer.generate_summary_report()


def extract_executed_soc(window_results_df: pd.DataFrame, fallback_soc: Optional[float]) -> Optional[float]:
    """提取滚动执行后第一步的SOC，用于传递到下一个滚动窗口"""
    if "battery_soc" in window_results_df.columns and not window_results_df["battery_soc"].empty:
        return float(window_results_df["battery_soc"].iloc[0])
    return fallback_soc


def compare_stage_to_baseline(
    current_results_df: pd.DataFrame,
    baseline_results_df: Optional[pd.DataFrame],
) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
    """对比当前阶段与上一阶段基线调度结果"""
    if baseline_results_df is None or baseline_results_df.empty:
        return None, {}

    compare_cols = [
        "load_demand_mw",
        "grid_purchase_mw",
        "grid_sale_mw",
        "battery_net_mw",
        "total_supply_mw",
        "total_flexible_load_mw",
    ]
    available_cols = [col for col in compare_cols if col in current_results_df.columns and col in baseline_results_df.columns]
    if not available_cols:
        return None, {}

    alignment_df = pd.DataFrame(index=current_results_df.index)
    summary = {}

    for col in available_cols:
        union_index = baseline_results_df.index.union(current_results_df.index)
        baseline_interp = (
            baseline_results_df[col]
            .reindex(union_index)
            .sort_index()
            .interpolate(method="time")
            .ffill()
            .bfill()
            .reindex(current_results_df.index)
        )
        deviation = current_results_df[col] - baseline_interp
        alignment_df[f"{col}_baseline"] = baseline_interp
        alignment_df[f"{col}_deviation"] = deviation
        summary[f"{col}_mean_abs_deviation"] = float(deviation.abs().mean())

    return alignment_df, summary


def interpolate_baseline_at_index(
    baseline_results_df: pd.DataFrame,
    target_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """将上一阶段结果插值到目标时间索引"""
    aligned = pd.DataFrame(index=target_index)
    union_index = baseline_results_df.index.union(target_index)
    for col in baseline_results_df.columns:
        aligned[col] = (
            baseline_results_df[col]
            .reindex(union_index)
            .sort_index()
            .interpolate(method="time")
            .ffill()
            .bfill()
            .reindex(target_index)
        )
    return aligned


def build_baseline_fallback_row(
    window_df: pd.DataFrame,
    baseline_results_df: pd.DataFrame,
    fallback_soc: Optional[float],
) -> pd.DataFrame:
    """当滚动窗口求解失败时，使用上一层基线生成保底执行点"""
    target_index = pd.DatetimeIndex([window_df.index[0]])
    fallback_row = interpolate_baseline_at_index(baseline_results_df, target_index)

    for col in [
        "load_demand_mw",
        "pv_generation_mw",
        "wind_generation_mw",
        "electricity_price_yuan_mwh",
    ]:
        if col in window_df.columns:
            fallback_row[col] = window_df.iloc[0][col]

    if "battery_soc" in fallback_row.columns and fallback_soc is not None:
        fallback_row["battery_soc"] = float(fallback_soc)

    if "pv_generation_mw" in fallback_row.columns and "wind_generation_mw" in fallback_row.columns:
        fallback_row["total_renewable_mw"] = fallback_row["pv_generation_mw"] + fallback_row["wind_generation_mw"]

    flexible_cols = [
        col
        for col in fallback_row.columns
        if (
            col.endswith("_load_mw")
            or col == "ev_charging_power_mw"
            or col.startswith("interruptible_load_")
            or col.startswith("building_hvac_")
        )
    ]
    if flexible_cols:
        fallback_row["total_flexible_load_mw"] = fallback_row[flexible_cols].sum(axis=1)

    fallback_row["grid_purchase_mw"] = fallback_row.get("grid_purchase_mw", pd.Series([0.0], index=target_index)).clip(lower=0)
    fallback_row["grid_sale_mw"] = fallback_row.get("grid_sale_mw", pd.Series([0.0], index=target_index)).clip(lower=0)
    fallback_row["battery_net_mw"] = fallback_row.get("battery_net_mw", pd.Series([0.0], index=target_index))
    fallback_row["gas_generation_mw"] = fallback_row.get("gas_generation_mw", pd.Series([0.0], index=target_index))
    fallback_row["grid_net_mw"] = fallback_row["grid_purchase_mw"] - fallback_row["grid_sale_mw"]
    fallback_row["total_supply_mw"] = (
        fallback_row.get("total_renewable_mw", pd.Series([0.0], index=target_index))
        + fallback_row["gas_generation_mw"]
        + fallback_row["battery_net_mw"]
        + fallback_row["grid_net_mw"]
    )
    fallback_row["power_balance_mw"] = fallback_row["total_supply_mw"] - fallback_row.get(
        "load_demand_mw",
        pd.Series([0.0], index=target_index),
    )
    return fallback_row


def save_stage_outputs(session: SessionContext, stage_result: StageExecutionResult):
    """保存阶段性结果"""
    stage_name = stage_result.stage_name
    input_to_save = stage_result.input_df.reset_index().rename(columns={"index": "timestamp"})
    result_to_save = stage_result.results_df.reset_index().rename(columns={"index": "timestamp"})
    economics_df = pd.DataFrame(list(stage_result.economics.items()), columns=["指标", "数值"])
    metrics_df = pd.DataFrame(list(stage_result.technical_metrics.items()), columns=["指标", "数值"])

    session.save_file("input_data", f"{stage_name}_input_data.csv", input_to_save)
    session.save_file("optimization_results", f"{stage_name}_dispatch_results.csv", result_to_save)
    session.save_file("economics_analysis", f"{stage_name}_economics.csv", economics_df)
    session.save_file("technical_metrics", f"{stage_name}_technical_metrics.csv", metrics_df)
    session.save_file("summary_report", f"{stage_name}_summary_report.txt", stage_result.summary_report)

    if stage_result.alignment_df is not None:
        alignment_to_save = stage_result.alignment_df.reset_index().rename(columns={"index": "timestamp"})
        session.save_file("optimization_results", f"{stage_name}_baseline_alignment.csv", alignment_to_save)

    if stage_result.rolling_window_stats is not None and not stage_result.rolling_window_stats.empty:
        session.save_file("optimization_results", f"{stage_name}_rolling_windows.csv", stage_result.rolling_window_stats)

    plot_generator = PlotGenerator()
    plot_generator.generate_plots_to_session(
        stage_result.results_df,
        stage_result.economics,
        stage_result.input_df["electricity_price_yuan_mwh"],
        session,
        f"{stage_name}_optimization_results.png",
    )


def execute_single_stage(
    mode: SchedulingMode,
    objective: OptimizationObjective,
    stage_spec: Dict[str, Any],
    initial_soc: Optional[float],
    baseline_results_df: Optional[pd.DataFrame],
) -> StageExecutionResult:
    """执行单次求解的阶段，如日前调度"""
    stage_start_time = time.time()
    dataset = stage_spec["dataset"]
    solve_bundle = solve_dispatch_dataset(mode, objective, dataset, initial_soc, disable_ancillary_services=False)
    alignment_df, alignment_summary = compare_stage_to_baseline(solve_bundle["results_df"], baseline_results_df)

    summary_report = generate_stage_summary_report(
        stage_spec["display_name"],
        solve_bundle["model_summary"],
        solve_bundle["economics"],
        solve_bundle["technical_metrics"],
        solve_bundle["summary_report"],
        alignment_summary,
        rolling_stats_df=None,
    )

    return StageExecutionResult(
        stage_name=stage_spec["stage_name"],
        display_name=stage_spec["display_name"],
        input_df=dataset,
        results_df=solve_bundle["results_df"],
        economics=solve_bundle["economics"],
        technical_metrics=solve_bundle["technical_metrics"],
        summary_report=summary_report,
        solve_time=solve_bundle["solve_time"],
        total_time=time.time() - stage_start_time,
        final_soc=solve_bundle["final_soc"],
        model_summary=solve_bundle["model_summary"],
        alignment_summary=alignment_summary,
        alignment_df=alignment_df,
        rolling_window_stats=None,
    )


def execute_rolling_stage(
    mode: SchedulingMode,
    objective: OptimizationObjective,
    stage_spec: Dict[str, Any],
    initial_soc: Optional[float],
    baseline_results_df: Optional[pd.DataFrame],
) -> StageExecutionResult:
    """执行滚动调度阶段，如日内和实时调度"""
    stage_start_time = time.time()
    dataset = stage_spec["dataset"]
    rolling_horizon_steps = min(stage_spec["rolling_horizon_steps"], len(dataset))

    aggregated_rows = []
    rolling_records = []
    current_soc = initial_soc
    last_model_summary = {}
    total_solve_time = 0.0

    for start in range(len(dataset)):
        window_df = dataset.iloc[start : start + rolling_horizon_steps]
        if window_df.empty:
            continue

        window_status = "optimized"
        try:
            if len(window_df) < 2:
                raise ValueError("滚动窗口长度不足，使用基线回退")
            solve_bundle = solve_dispatch_dataset(
                mode,
                objective,
                window_df,
                current_soc,
                disable_ancillary_services=True,
            )
            executed_row = solve_bundle["results_df"].iloc[[0]].copy()
            current_soc = extract_executed_soc(solve_bundle["results_df"], current_soc)
            total_solve_time += solve_bundle["solve_time"]
            last_model_summary = solve_bundle["model_summary"]
            solve_time_seconds = solve_bundle["solve_time"]
        except Exception:
            if baseline_results_df is None or baseline_results_df.empty:
                raise
            executed_row = build_baseline_fallback_row(window_df, baseline_results_df, current_soc)
            current_soc = extract_executed_soc(executed_row, current_soc)
            solve_time_seconds = 0.0
            window_status = "baseline_fallback"

        aggregated_rows.append(executed_row)
        rolling_records.append(
            {
                "window_start": window_df.index[0],
                "window_end": window_df.index[-1],
                "window_steps": len(window_df),
                "solve_time_seconds": solve_time_seconds,
                "executed_soc": current_soc if current_soc is not None else np.nan,
                "grid_purchase_first_step_mw": executed_row.get("grid_purchase_mw", pd.Series([0.0])).iloc[0]
                if "grid_purchase_mw" in executed_row.columns
                else 0.0,
                "status": window_status,
            }
        )

    if not aggregated_rows:
        raise RuntimeError(f"{stage_spec['display_name']}未能生成滚动执行结果")

    results_df = pd.concat(aggregated_rows).sort_index()
    economics, technical_metrics, analyzer_report = analyze_precomputed_stage_results(
        results_df,
        dataset["electricity_price_yuan_mwh"],
    )
    alignment_df, alignment_summary = compare_stage_to_baseline(results_df, baseline_results_df)
    rolling_stats_df = pd.DataFrame(rolling_records)

    summary_report = generate_stage_summary_report(
        stage_spec["display_name"],
        last_model_summary,
        economics,
        technical_metrics,
        analyzer_report,
        alignment_summary,
        rolling_stats_df=rolling_stats_df,
    )

    return StageExecutionResult(
        stage_name=stage_spec["stage_name"],
        display_name=stage_spec["display_name"],
        input_df=dataset,
        results_df=results_df,
        economics=economics,
        technical_metrics=technical_metrics,
        summary_report=summary_report,
        solve_time=total_solve_time,
        total_time=time.time() - stage_start_time,
        final_soc=current_soc,
        model_summary=last_model_summary,
        alignment_summary=alignment_summary,
        alignment_df=alignment_df,
        rolling_window_stats=rolling_stats_df,
    )


def run_dispatch_stage(
    mode: SchedulingMode,
    objective: OptimizationObjective,
    stage_spec: Dict[str, Any],
    initial_soc: Optional[float],
    baseline_results_df: Optional[pd.DataFrame],
    session: SessionContext,
) -> StageExecutionResult:
    """执行单个调度阶段并保存输出"""
    logger.info(f"\n>> 执行 {stage_spec['display_name']}")
    logger.info("-" * 50)
    logger.info(
        f"时间步数: {len(stage_spec['dataset'])}, "
        f"滚动模式: {'是' if stage_spec['rolling'] else '否'}, "
        f"滚动窗口: {stage_spec['rolling_horizon_steps']} 步"
    )

    if stage_spec["rolling"]:
        stage_result = execute_rolling_stage(mode, objective, stage_spec, initial_soc, baseline_results_df)
    else:
        stage_result = execute_single_stage(mode, objective, stage_spec, initial_soc, baseline_results_df)

    save_stage_outputs(session, stage_result)
    logger.info(
        f"[OK] {stage_spec['display_name']}完成: "
        f"求解时间 {stage_result.solve_time:.2f} 秒, "
        f"阶段总耗时 {stage_result.total_time:.2f} 秒"
    )
    return stage_result


def build_hierarchical_summary_dataframe(stage_results: List[StageExecutionResult]) -> pd.DataFrame:
    """构建阶段性汇总表"""
    rows = []
    for stage_result in stage_results:
        rows.append(
            {
                "stage_name": stage_result.stage_name,
                "display_name": stage_result.display_name,
                "time_steps": len(stage_result.results_df),
                "solve_time_seconds": stage_result.solve_time,
                "total_time_seconds": stage_result.total_time,
                "net_cost_yuan": stage_result.economics.get("net_cost_yuan", 0.0),
                "average_cost_yuan_per_mwh": stage_result.economics.get("average_cost_yuan_per_mwh", 0.0),
                "load_total_mwh": stage_result.technical_metrics.get("load_total_mwh", 0.0),
                "renewable_penetration_ratio": stage_result.technical_metrics.get("renewable_penetration_ratio", 0.0),
                "self_sufficiency_ratio": stage_result.technical_metrics.get("self_sufficiency_ratio", 0.0),
                "final_soc": stage_result.final_soc if stage_result.final_soc is not None else np.nan,
            }
        )
    return pd.DataFrame(rows)


def generate_stage_summary_report(
    display_name: str,
    model_summary: Dict[str, Any],
    economics: Dict[str, Any],
    technical_metrics: Dict[str, Any],
    analyzer_report: str,
    alignment_summary: Dict[str, Any],
    rolling_stats_df: Optional[pd.DataFrame],
) -> str:
    """生成单阶段总结报告"""
    report = []
    report.append("=" * 80)
    report.append(f"{display_name}结果报告")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    report.append("[SUMMARY] 模型概要")
    report.append("-" * 40)
    for key in ["scheduling_mode", "optimization_objective", "mode_description", "objective_description"]:
        if key in model_summary:
            report.append(f"{key}: {model_summary[key]}")
    included_resources = model_summary.get("included_resources", [])
    if included_resources:
        report.append(f"included_resources: {', '.join(included_resources)}")
    report.append("")

    report.append("[ECONOMY] 经济性指标")
    report.append("-" * 40)
    for key, value in economics.items():
        if isinstance(value, (int, float)):
            if "yuan" in key.lower():
                report.append(f"{key}: {value:,.2f} 元")
            elif "ratio" in key.lower() or "rate" in key.lower():
                report.append(f"{key}: {value:.2%}")
            else:
                report.append(f"{key}: {value:.4f}")
    report.append("")

    report.append("[METRICS] 技术指标")
    report.append("-" * 40)
    for key, value in technical_metrics.items():
        if isinstance(value, (int, float)):
            if "mwh" in key.lower():
                report.append(f"{key}: {value:.2f} MWh")
            elif "mw" in key.lower():
                report.append(f"{key}: {value:.2f} MW")
            elif "ratio" in key.lower() or "rate" in key.lower():
                report.append(f"{key}: {value:.2%}")
            else:
                report.append(f"{key}: {value:.4f}")
    report.append("")

    if alignment_summary:
        report.append("[ALIGNMENT] 与上阶段基线偏差")
        report.append("-" * 40)
        for key, value in alignment_summary.items():
            report.append(f"{key}: {value:.4f}")
        report.append("")

    if rolling_stats_df is not None and not rolling_stats_df.empty:
        report.append("[ROLLING] 滚动执行统计")
        report.append("-" * 40)
        report.append(f"滚动窗口数量: {len(rolling_stats_df)}")
        report.append(f"平均窗口求解时间: {rolling_stats_df['solve_time_seconds'].mean():.2f} 秒")
        report.append(f"最大窗口求解时间: {rolling_stats_df['solve_time_seconds'].max():.2f} 秒")
        report.append("")

    report.append("[ANALYZER] 分析器报告")
    report.append("-" * 40)
    report.append(analyzer_report)
    return "\n".join(report)


def generate_hierarchical_summary_report(
    mode: SchedulingMode,
    objective: OptimizationObjective,
    stage_results: List[StageExecutionResult],
    scenario_summary_df: pd.DataFrame,
    multiscale_datasets: Dict[str, pd.DataFrame],
) -> str:
    """生成分层调度总报告"""
    report = []
    report.append("=" * 80)
    report.append(f"虚拟电厂分层调度总报告 - {mode.value} / {objective.value}")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    report.append("[FLOW] 执行流程")
    report.append("-" * 40)
    report.append("1. 日前调度: 24小时全局计划，形成日内基线")
    report.append("2. 日内调度: 以更高分辨率滚动修正日前计划")
    report.append("3. 实时调度: 以最细粒度滚动校正并形成实际执行结果")
    report.append("")

    report.append(generate_multiscale_summary(multiscale_datasets))
    report.append("")
    report.append(generate_scenario_summary_report(scenario_summary_df))
    report.append("")

    report.append("[STAGES] 各阶段关键结果")
    report.append("-" * 40)
    for stage_result in stage_results:
        report.append(
            f"{stage_result.display_name}: "
            f"净成本 {stage_result.economics.get('net_cost_yuan', 0):,.2f} 元, "
            f"负荷 {stage_result.technical_metrics.get('load_total_mwh', 0):.2f} MWh, "
            f"可再生渗透率 {stage_result.technical_metrics.get('renewable_penetration_ratio', 0):.2%}, "
            f"最终SOC {stage_result.final_soc if stage_result.final_soc is not None else 0:.3f}"
        )
    report.append("")

    report.append("[DETAILS] 阶段详细报告")
    report.append("-" * 40)
    for stage_result in stage_results:
        report.append(stage_result.summary_report)
        report.append("")

    return "\n".join(report)


def run_single_mode_analysis(mode: SchedulingMode, objective: OptimizationObjective) -> Tuple[bool, Dict]:
    """运行单个调度模式的分层调度实验"""
    total_start_time = time.time()
    file_manager = VPPFileManager()

    with SessionContext(file_manager, mode, objective) as session:
        try:
            logger.info("\n>> 步骤1: 生成基础数据")
            logger.info("-" * 40)
            data_generator = VPPDataGenerator()
            load_data, pv_data, wind_data, price_data = data_generator.generate_all_data()
            input_data_path = data_generator.save_data_to_session(session, "input_data.csv")
            logger.info(f"[OK] 输入数据已保存: {input_data_path}")

            logger.info("\n>> 步骤2: 生成多时间尺度数据与不确定性场景")
            logger.info("-" * 40)
            multiscale_datasets = data_generator.generate_multiscale_datasets(load_data, pv_data, wind_data, price_data)
            scenario_bundle = data_generator.generate_uncertainty_scenarios(load_data, pv_data, wind_data, price_data)
            scenario_summary_df = data_generator.summarize_uncertainty_scenarios(scenario_bundle)

            for dataset_name, dataset_df in multiscale_datasets.items():
                session.save_file(
                    "input_data",
                    f"{dataset_name}_input_data.csv",
                    dataset_df.reset_index().rename(columns={"index": "timestamp"}),
                )
            session.save_file("technical_metrics", "scenario_summary.csv", scenario_summary_df)
            logger.info("[OK] 多时间尺度输入与场景摘要已生成")

            logger.info("\n>> 步骤3: 执行分层调度")
            logger.info("-" * 40)
            stage_plan = build_hierarchical_stage_plan(data_generator, multiscale_datasets)
            initial_soc = (
                VPPSchedulingManager()
                .config.get("energy_resources", {})
                .get("battery_storage", {})
                .get("initial_soc")
            )

            stage_results: List[StageExecutionResult] = []
            baseline_results_df = None
            for stage_spec in stage_plan:
                stage_result = run_dispatch_stage(
                    mode=mode,
                    objective=objective,
                    stage_spec=stage_spec,
                    initial_soc=initial_soc,
                    baseline_results_df=baseline_results_df,
                    session=session,
                )
                stage_results.append(stage_result)
                baseline_results_df = stage_result.results_df
                initial_soc = stage_result.final_soc

            logger.info("\n>> 步骤4: 汇总分层调度结果")
            logger.info("-" * 40)
            hierarchical_summary_df = build_hierarchical_summary_dataframe(stage_results)
            session.save_file("technical_metrics", "hierarchical_stage_summary.csv", hierarchical_summary_df)

            hierarchical_report = generate_hierarchical_summary_report(
                mode,
                objective,
                stage_results,
                scenario_summary_df,
                multiscale_datasets,
            )
            report_path = session.save_file("summary_report", "hierarchical_dispatch_report.txt", hierarchical_report)
            logger.info(f"[OK] 分层调度总报告已生成: {report_path}")

            final_stage = stage_results[-1]
            total_time = time.time() - total_start_time

            logger.info("\n[METRICS] 实验关键结果（以实时阶段为准）:")
            logger.info(f"  - 总负荷: {final_stage.technical_metrics.get('load_total_mwh', 0):.2f} MWh")
            logger.info(f"  - 可再生能源渗透率: {final_stage.technical_metrics.get('renewable_penetration_ratio', 0):.2%}")
            logger.info(f"  - 自给自足率: {final_stage.technical_metrics.get('self_sufficiency_ratio', 0):.2%}")
            logger.info(f"  - 净运行成本: {final_stage.economics.get('net_cost_yuan', 0):,.2f} 元")
            logger.info(f"  - 平均供电成本: {final_stage.economics.get('average_cost_yuan_per_mwh', 0):.2f} 元/MWh")
            logger.info(f"[TIME] 总耗时: {total_time:.2f} 秒")
            logger.info(f"[DIR] 会话目录: {session.session_dir}")

            return True, {
                "session_dir": str(session.session_dir),
                "economics": final_stage.economics,
                "technical_metrics": final_stage.technical_metrics,
                "hierarchical_stage_summary": hierarchical_summary_df.to_dict(orient="records"),
                "scenario_summary": scenario_summary_df.to_dict(orient="records"),
                "solve_time": float(hierarchical_summary_df["solve_time_seconds"].sum()),
                "total_time": total_time,
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

    if results_summary:
        generate_comparison_report(results_summary, objective)
        logger.info("\n[SUCCESS] 所有调度模式对比分析完成！")
        return True

    logger.error("\n[ERROR] 所有调度模式运行均失败")
    return False


def generate_comparison_report(results_summary: List[Tuple[SchedulingMode, Dict]], objective: OptimizationObjective):
    """生成调度模式对比报告"""
    logger.info("\n[METRICS] 生成调度模式对比报告")
    logger.info("-" * 60)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"outputs/modes_comparison_{objective.value}_{timestamp}.txt"
    os.makedirs("outputs", exist_ok=True)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"虚拟电厂调度模式对比分析报告 - {objective.value.upper()}\n")
        f.write("=" * 80 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"优化目标: {objective.value}\n\n")
        f.write("[INFO] 调度模式对比表\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'调度模式':<20} {'净运行成本(元)':<18} {'平均成本(元/MWh)':<20} {'总耗时(秒)':<12}\n")
        f.write("-" * 80 + "\n")

        for mode, summary in results_summary:
            economics = summary.get("economics", {})
            net_cost = economics.get("net_cost_yuan", 0)
            avg_cost = economics.get("average_cost_yuan_per_mwh", 0)
            run_time = summary.get("total_time", 0)
            f.write(f"{mode.value:<20} {net_cost:>16,.2f} {avg_cost:>18.2f} {run_time:>10.2f}\n")

        f.write("\n" + "=" * 80 + "\n")

    logger.info(f"[OK] 对比报告已保存: {report_file}")


def run_scheduling_mode(mode: SchedulingMode, objective: OptimizationObjective):
    """运行指定调度模式"""
    success, _ = run_single_mode_analysis(mode, objective)
    if success:
        logger.info(f"\n[SUCCESS] {mode.value} 调度模式（{objective.value}）运行成功！")
        return True
    logger.error(f"\n[ERROR] {mode.value} 调度模式运行失败")
    return False


def generate_multiscale_summary(multiscale_datasets: Dict[str, pd.DataFrame]) -> str:
    """生成多时间尺度摘要"""
    report = []
    report.append("[MULTI_SCALE] 多时间尺度调度摘要")
    report.append("-" * 40)

    for scale_name, dataset in multiscale_datasets.items():
        report.append(
            f"{scale_name}: {len(dataset)} 个时间步, "
            f"时间范围 {dataset.index[0]} -> {dataset.index[-1]}, "
            f"负荷均值 {dataset['load_demand_mw'].mean():.2f} MW, "
            f"均价 {dataset['electricity_price_yuan_mwh'].mean():.2f} 元/MWh"
        )

    return "\n".join(report)


def generate_scenario_summary_report(scenario_summary_df: pd.DataFrame) -> str:
    """生成不确定性场景摘要"""
    report = []
    report.append("[SCENARIOS] 不确定性场景摘要")
    report.append("-" * 40)
    report.append(f"场景数量: {len(scenario_summary_df)}")

    if len(scenario_summary_df) > 0:
        report.append(
            f"负荷总量范围: {scenario_summary_df['load_total_mwh'].min():.2f} - "
            f"{scenario_summary_df['load_total_mwh'].max():.2f} MWh"
        )
        report.append(
            f"平均电价范围: {scenario_summary_df['avg_price_yuan_mwh'].min():.2f} - "
            f"{scenario_summary_df['avg_price_yuan_mwh'].max():.2f} 元/MWh"
        )
        report.append(
            f"负荷峰值范围: {scenario_summary_df['load_peak_mw'].min():.2f} - "
            f"{scenario_summary_df['load_peak_mw'].max():.2f} MW"
        )

    return "\n".join(report)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="虚拟电厂分层调度优化系统")
    parser.add_argument("--mode", type=str, help="指定调度模式名称")
    parser.add_argument("--objective", type=str, help="指定优化目标名称")
    parser.add_argument("--compare-all", action="store_true", help="运行所有调度模式对比实验")
    parser.add_argument("--list-modes", action="store_true", help="列出可用调度模式与目标")

    args = parser.parse_args()

    try:
        main(
            scheduling_mode=args.mode,
            objective_name=args.objective,
            compare_all=args.compare_all,
            list_modes=args.list_modes,
        )
    except Exception:
        logger.exception("主程序执行过程中发生未捕获的异常:")
        sys.exit(1)
    finally:
        logger.info(f"\n程序结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
