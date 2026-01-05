"""
虚拟电厂优化目标对比测试
VPP Optimization Objectives Comparison Test

测试不同优化目标对系统性能的影响
"""

import os
import sys
import time
from datetime import datetime

# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # 从tests目录回到项目根目录
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)

# 导入项目模块
from src.models.scheduling_modes import VPPSchedulingManager, SchedulingMode, OptimizationObjective
from src.data.data_generator import VPPDataGenerator


def test_optimization_objectives():
    """测试不同优化目标"""
    print("[TEST] 虚拟电厂优化目标对比测试")
    print("=" * 80)
    
    # 创建管理器和数据生成器
    manager = VPPSchedulingManager()
    data_generator = VPPDataGenerator()
    
    # 测试场景: 完整系统模式下的不同优化目标
    test_mode = SchedulingMode.FULL_SYSTEM
    test_objectives = [
        OptimizationObjective.COST_MINIMIZATION,
        OptimizationObjective.REVENUE_MAXIMIZATION, 
        OptimizationObjective.PROFIT_MAXIMIZATION,
        OptimizationObjective.ANCILLARY_REVENUE_MAX
    ]
    
    print(f"\n[SCENARIO] 测试场景: {test_mode.value} 模式")
    print(f"[OBJECTIVE] 测试目标数量: {len(test_objectives)}")
    print("-" * 60)
    
    results = {}
    
    for i, objective in enumerate(test_objectives, 1):
        print(f"\n[{i}/{len(test_objectives)}] 测试优化目标: {objective.value}")
        print("-" * 50)
        
        try:
            # 创建带优化目标的模型
            model = manager.create_optimized_model(test_mode, data_generator.time_index, objective)
            
            # 获取目标函数描述
            objective_desc = manager.get_objective_function_description(test_mode, objective)
            print(f"[DESC] 目标函数: {objective_desc}")
            
            # 获取模型摘要
            summary = model.get_mode_summary()
            
            # 记录结果
            results[objective] = {
                'success': True,
                'description': manager.get_optimization_objective_description(objective),
                'objective_function': objective_desc,
                'components_count': summary.get('total_components', 0),
                'resources': summary.get('included_resources', [])
            }
            
            print(f"[OK] 模型创建成功")
            print(f"  - 组件数量: {summary.get('total_components', 0)}")
            print(f"  - 包含资源: {len(summary.get('included_resources', []))} 种")
            
        except Exception as e:
            print(f"[FAIL] 模型创建失败: {str(e)}")
            results[objective] = {
                'success': False,
                'error': str(e)
            }
    
    # 打印对比结果
    print_objectives_comparison(results)
    
    return results


def print_objectives_comparison(results):
    """打印优化目标对比结果"""
    print(f"\n{'='*80}")
    print("[ANALYSIS] 优化目标对比分析")
    print(f"{'='*80}")
    
    print(f"\n{'优化目标':<25} {'状态':<8} {'组件数':<8} {'目标描述'}")
    print("-" * 80)
    
    for objective, result in results.items():
        if result['success']:
            status = "[OK] 成功"
            components = result.get('components_count', 0)
            description = result.get('description', '')[:40] + "..."
            print(f"{objective.value:<25} {status:<8} {components:<8} {description}")
        else:
            status = "[FAIL] 失败"
            print(f"{objective.value:<25} {status:<8} {'N/A':<8} {'N/A'}")
    
    print(f"\n[DETAILS] 优化目标详细信息:")
    print("-" * 60)
    
    for objective, result in results.items():
        if result['success']:
            print(f"\n[OBJECTIVE] {objective.value.upper()}")
            print(f"   描述: {result['description']}")
            print(f"   目标函数: {result['objective_function']}")
            print(f"   系统复杂度: {result['components_count']} 个组件")


def demonstrate_objective_differences():
    """演示不同优化目标的差异"""
    print(f"\n{'='*80}")
    print("[TIP] 优化目标差异说明")
    print(f"{'='*80}")
    
    manager = VPPSchedulingManager()
    
    print("\n[ANALYSIS] 各优化目标的核心差异:")
    
    objectives_explanation = {
        OptimizationObjective.COST_MINIMIZATION: {
            "焦点": "成本控制",
            "适用场景": "传统电力系统、成本敏感型应用",
            "优势": "运行成本低、风险小",
            "劣势": "收益潜力有限"
        },
        OptimizationObjective.REVENUE_MAXIMIZATION: {
            "焦点": "收入增长", 
            "适用场景": "电力市场化环境、售电公司",
            "优势": "收入最大化、市场机会捕获",
            "劣势": "可能忽视成本控制"
        },
        OptimizationObjective.PROFIT_MAXIMIZATION: {
            "焦点": "利润优化",
            "适用场景": "商业化虚拟电厂、投资项目",
            "优势": "综合考虑收入和成本、投资回报最佳",
            "劣势": "可能波动较大"
        },
        OptimizationObjective.ANCILLARY_REVENUE_MAX: {
            "焦点": "辅助服务",
            "适用场景": "电网服务商、储能运营商",
            "优势": "高价值服务收入、电网稳定性贡献",
            "劣势": "对储能等设备要求高"
        },
        OptimizationObjective.GRID_SUPPORT_OPTIMIZED: {
            "焦点": "电网支撑",
            "适用场景": "电网公司、系统运营商",
            "优势": "电网稳定性最优、社会效益高",
            "劣势": "经济性可能不是最优"
        }
    }
    
    for obj, info in objectives_explanation.items():
        description = manager.get_optimization_objective_description(obj)
        print(f"\n[INFO] {obj.value.upper()}")
        print(f"   核心描述: {description}")
        for key, value in info.items():
            print(f"   {key}: {value}")


def run_comparison_demo():
    """运行完整的对比演示"""
    print("[START] 启动虚拟电厂优化目标对比演示")
    start_time = time.time()
    
    # 1. 测试不同优化目标
    results = test_optimization_objectives()
    
    # 2. 演示目标差异
    demonstrate_objective_differences()
    
    # 3. 总结
    total_time = time.time() - start_time
    successful_objectives = sum(1 for r in results.values() if r.get('success', False))
    
    print(f"\n{'='*80}")
    print("[SUMMARY] 测试总结")
    print(f"{'='*80}")
    print(f"[OK] 成功测试优化目标: {successful_objectives}/{len(results)}")
    print(f"[TIME] 总用时: {total_time:.2f} 秒")
    print(f"[DATE] 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if successful_objectives == len(results):
        print("\n[SUCCESS] 所有优化目标测试通过！系统支持多目标优化。")
    else:
        print(f"\n[WARNING] 部分优化目标测试失败，请检查错误信息。")
    
    print("\n[TIP] 使用建议:")
    print("1. 成本最小化适用于传统调度场景")
    print("2. 收益最大化适用于市场化电力交易")
    print("3. 利润最大化适用于商业化虚拟电厂运营")
    print("4. 辅助服务优化适用于储能等高价值服务")
    print("5. 电网支撑优化适用于系统运营商需求")


if __name__ == "__main__":
    run_comparison_demo()
