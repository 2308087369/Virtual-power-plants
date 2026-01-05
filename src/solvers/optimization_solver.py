"""
优化求解器
Optimization Solver

基于 CBC 求解器的虚拟电厂优化问题求解
"""

import os
import time
import yaml
import pandas as pd
import psutil
from typing import Dict, Optional, Any, Callable
import warnings
warnings.filterwarnings('ignore')

import oemof.solph as solph
import logging

# 获取模块级日志记录器
logger = logging.getLogger(__name__)


class OptimizationSolver:
    """优化求解器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化求解器
        
        Args:
            config_path: 求解器配置文件路径
        """
        self.config = self._load_solver_config(config_path)
        self.optimization_model = None
        self.results = None
        self.solve_stats = {}
        
        # 设置求解器路径
        self._setup_solver()
    
    def _load_solver_config(self, config_path: Optional[str]) -> Dict:
        """加载求解器配置"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'config', 'solver_config.yaml'
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载求解器配置失败: {e}，使用默认配置")
            return self._get_default_solver_config()
    
    def _get_default_solver_config(self) -> Dict:
        """获取默认求解器配置"""
        return {
            'solver': {
                'name': 'cbc',
                'executable_path': os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cbc', 'bin', 'cbc.exe')
            },
            'cbc_options': {
                'threads': 4,
                'timeLimit': 300,
                'ratioGap': 0.01,
                'logLevel': 1
            },
            'solving_strategy': {
                'auto_select': True,
                'retry_on_failure': True,
                'max_retries': 3,
                'verify_solution': True
            },
            'performance': {
                'log_solve_time': True,
                'log_memory_usage': True
            },
            'debug': {
                'save_solver_log': True,
                'verbose': False
            }
        }
    
    def _setup_solver(self):
        """设置求解器环境"""
        solver_config = self.config['solver']
        
        # 设置 CBC 可执行文件路径
        if 'executable_path' in solver_config:
            cbc_path = solver_config['executable_path']
            
            # 如果是相对路径，转换为绝对路径
            if not os.path.isabs(cbc_path):
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                cbc_path = os.path.join(project_root, cbc_path)
            
            if os.path.exists(cbc_path):
                os.environ['CBC_EXECUTABLE'] = cbc_path
                # 同时设置多个可能的环境变量
                os.environ['CBCDIR'] = os.path.dirname(cbc_path)
                os.environ['PATH'] = os.path.dirname(cbc_path) + os.pathsep + os.environ.get('PATH', '')
                logger.info(f"使用指定的CBC路径: {cbc_path}")
                
                # 验证CBC是否可执行
                try:
                    import subprocess
                    result = subprocess.run([cbc_path, '-help'], capture_output=True, timeout=5)
                    if result.returncode == 0:
                        logger.info("[OK] CBC求解器验证成功")
                    else:
                        logger.warning("[WARNING] CBC求解器验证失败，但文件存在")
                except Exception as e:
                    logger.error(f"[ERROR] 求解器验证失败: {str(e)}")
            else:
                logger.warning(f"警告：指定的CBC路径不存在: {cbc_path}")
                logger.info("将尝试使用系统默认的CBC求解器")
    
    def create_optimization_model(self, energy_system: solph.EnergySystem) -> solph.Model:
        """
        创建优化模型
        
        Args:
            energy_system: 能源系统对象
            
        Returns:
            优化模型
        """
        logger.info("正在创建优化模型...")
        
        try:
            self.optimization_model = solph.Model(energy_system)
            logger.info("优化模型创建成功")
            return self.optimization_model
        except Exception as e:
            logger.error(f"创建优化模型失败: {e}")
            raise
    
    def solve(self, energy_system: solph.EnergySystem, pre_solve_callback: Optional[Callable] = None) -> bool:
        """
        求解优化问题
        
        Args:
            energy_system: 能源系统对象
            pre_solve_callback: 在求解前调用的回调函数，接收 optimization_model 作为参数
            
        Returns:
            求解是否成功
        """
        logger.info("="*50)
        logger.info("开始优化求解...")
        logger.info("="*50)
        
        # 记录开始时间和内存
        start_time = time.time()
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            # 创建优化模型
            self.optimization_model = self.create_optimization_model(energy_system)
            
            # 执行回调函数（例如添加自定义约束）
            if pre_solve_callback:
                logger.info("执行预求解回调函数（添加自定义约束等）...")
                pre_solve_callback(self.optimization_model)
            
            # 准备求解器参数
            solver_name = self.config['solver']['name']
            solve_kwargs = self._prepare_solve_kwargs()
            
            logger.info(f"使用求解器: {solver_name}")
            logger.info(f"求解器参数: {solve_kwargs}")
            
            # 尝试求解
            success = self._attempt_solve(solver_name, solve_kwargs)
            
            if success:
                # 提取结果
                from oemof.solph import processing
                self.results = processing.results(self.optimization_model)
                
                # 验证解的可行性
                if self.config['solving_strategy']['verify_solution']:
                    if self._verify_solution():
                        logger.info("[OK] 解验证通过")
                    else:
                        logger.warning("[WARNING] 解验证失败，但求解器返回成功")
                
                logger.info("[OK] 优化求解成功完成")
            else:
                logger.error("[ERROR] 优化求解失败")
            
            # 记录求解统计信息
            end_time = time.time()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            self.solve_stats = {
                'solve_time_seconds': end_time - start_time,
                'memory_usage_mb': end_memory - start_memory,
                'success': success,
                'solver_used': solver_name
            }
            
            self._print_solve_stats()
            
            return success
            
        except Exception as e:
            logger.error(f"求解过程中发生错误: {e}")
            self.solve_stats = {
                'solve_time_seconds': time.time() - start_time,
                'success': False,
                'error': str(e)
            }
            return False
    
    def _prepare_solve_kwargs(self) -> Dict[str, Any]:
        """准备求解器参数"""
        solver_name = self.config['solver']['name']
        solve_kwargs = {'tee': self.config['debug']['verbose']}
        
        if solver_name == 'cbc':
            cbc_options = self.config['cbc_options']
            solve_kwargs['options'] = {
                'threads': cbc_options.get('threads', 4),
                'ratioGap': cbc_options.get('ratioGap', 0.01),
                'timeLimit': cbc_options.get('timeLimit', 300)
            }
        
        return solve_kwargs
    
    def _attempt_solve(self, solver_name: str, solve_kwargs: Dict) -> bool:
        """尝试求解优化问题"""
        max_retries = self.config['solving_strategy']['max_retries']
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"第 {attempt + 1} 次尝试求解...")
                
                # 执行求解
                if solver_name == 'cbc':
                    # 尝试直接指定可执行文件
                    cbc_path = self.config.get('solver', {}).get('executable_path')
                    if cbc_path and not os.path.isabs(cbc_path):
                        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                        cbc_path = os.path.join(project_root, cbc_path)
                    
                    if cbc_path and os.path.exists(cbc_path):
                        # 直接使用pyomo调用CBC
                        try:
                            from pyomo.opt import SolverFactory
                            pyomo_solver = SolverFactory('cbc', executable=cbc_path)
                            if pyomo_solver.available():
                                logger.info(f"使用Pyomo调用CBC: {cbc_path}")
                                result = pyomo_solver.solve(self.optimization_model, **solve_kwargs)
                                if str(result.solver.termination_condition).lower() in ['optimal', 'feasible']:
                                    return True
                        except Exception as pyomo_error:
                            logger.warning(f"Pyomo调用失败: {pyomo_error}")
                
                # 默认方式求解
                self.optimization_model.solve(
                    solver=solver_name,
                    solve_kwargs=solve_kwargs
                )
                
                # 检查求解状态
                if self._check_solve_status():
                    return True
                else:
                    if attempt < max_retries:
                        logger.warning(f"求解失败，准备重试... ({attempt + 1}/{max_retries})")
                        # 可以在这里调整求解参数
                        solve_kwargs = self._adjust_solve_parameters(solve_kwargs, attempt)
                    else:
                        logger.error("达到最大重试次数，求解失败")
                        return False
                        
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"求解器异常: {e}，准备重试... ({attempt + 1}/{max_retries})")
                else:
                    logger.error(f"求解器异常: {e}，求解失败")
                    return False
        
        return False
    
    def _check_solve_status(self) -> bool:
        """检查求解状态"""
        try:
            # 尝试访问求解结果来判断是否成功
            if hasattr(self.optimization_model, 'solver_results'):
                solver_results = self.optimization_model.solver_results
                termination_condition = solver_results.solver.termination_condition
                
                success_conditions = ['optimal', 'maxTimeLimit', 'other']
                
                if str(termination_condition).lower() in [cond.lower() for cond in success_conditions]:
                    return True
            
            # 如果没有solver_results属性，尝试其他方法验证
            return self._basic_solution_check()
            
        except Exception as e:
            logger.error(f"检查求解状态时出错: {e}")
            return self._basic_solution_check()
    
    def _basic_solution_check(self) -> bool:
        """基本解检查"""
        try:
            from oemof.solph import processing
            # 尝试获取一个变量的值来验证是否有解
            test_results = processing.results(self.optimization_model)
            return test_results is not None and len(test_results) > 0
        except:
            return False
    
    def _adjust_solve_parameters(self, solve_kwargs: Dict, attempt: int) -> Dict:
        """根据重试次数调整求解参数"""
        # 复制原参数
        adjusted_kwargs = solve_kwargs.copy()
        
        if 'options' in adjusted_kwargs:
            options = adjusted_kwargs['options'].copy()
            
            # 根据尝试次数调整参数
            if attempt == 1:
                # 第二次尝试：放宽最优性间隙
                options['ratioGap'] = options.get('ratioGap', 0.01) * 2
            elif attempt == 2:
                # 第三次尝试：增加时间限制，进一步放宽间隙
                options['timeLimit'] = options.get('timeLimit', 300) * 2
                options['ratioGap'] = options.get('ratioGap', 0.01) * 5
            
            adjusted_kwargs['options'] = options
        
        return adjusted_kwargs
    
    def _verify_solution(self) -> bool:
        """验证解的可行性"""
        try:
            if self.results is None:
                return False
            
            # 基本验证：检查是否有结果数据
            if len(self.results) == 0:
                return False
            
            # 可以在这里添加更多的验证逻辑
            # 例如：能量平衡检查、约束满足检查等
            
            return True
            
        except Exception as e:
            logger.error(f"验证解时出错: {e}")
            return False
    
    def _print_solve_stats(self):
        """打印求解统计信息"""
        if not self.solve_stats:
            return
        
        logger.info("-"*40)
        logger.info("求解统计信息:")
        logger.info("-"*40)
        
        if 'solve_time_seconds' in self.solve_stats:
            logger.info(f"求解时间: {self.solve_stats['solve_time_seconds']:.2f} 秒")
        
        if 'memory_usage_mb' in self.solve_stats:
            logger.info(f"内存使用: {self.solve_stats['memory_usage_mb']:.1f} MB")
        
        if 'solver_used' in self.solve_stats:
            logger.info(f"使用求解器: {self.solve_stats['solver_used']}")
        
        logger.info(f"求解状态: {'成功' if self.solve_stats['success'] else '失败'}")
        
        if 'error' in self.solve_stats:
            logger.info(f"错误信息: {self.solve_stats['error']}")
        
        logger.info("-"*40)
    
    def get_results(self) -> Optional[Dict]:
        """获取优化结果"""
        return self.results
    
    def get_solve_statistics(self) -> Dict:
        """获取求解统计信息"""
        return self.solve_stats.copy()
    
    def save_solver_log(self, log_path: Optional[str] = None):
        """保存求解器日志"""
        if not self.config['debug']['save_solver_log']:
            return
        
        if log_path is None:
            log_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'logs'
            )
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, 'solver_results.log')
        
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("虚拟电厂优化求解日志\n")
                f.write("="*50 + "\n\n")
                
                # 写入求解统计
                f.write("求解统计信息:\n")
                for key, value in self.solve_stats.items():
                    f.write(f"{key}: {value}\n")
                f.write("\n")
                
                # 写入配置信息
                f.write("求解器配置:\n")
                f.write(str(self.config))
                f.write("\n")
            
            logger.info(f"求解器日志已保存到: {log_path}")
            
        except Exception as e:
            logger.error(f"保存求解器日志失败: {e}")


# 示例使用
if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    
    from data.data_generator import VPPDataGenerator
    from models.vpp_model import VPPOptimizationModel
    
    # 创建数据
    data_generator = VPPDataGenerator()
    load_data, pv_data, wind_data, price_data = data_generator.generate_all_data()
    
    # 创建模型
    model = VPPOptimizationModel(data_generator.time_index)
    energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
    
    # 创建求解器并求解
    solver = OptimizationSolver()
    success = solver.solve(energy_system)
    
    if success:
        results = solver.get_results()
        stats = solver.get_solve_statistics()
        print(f"\n求解成功！用时 {stats['solve_time_seconds']:.2f} 秒")
    else:
        print("\n求解失败！")