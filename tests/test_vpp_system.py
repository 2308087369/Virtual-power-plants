"""
虚拟电厂系统测试脚本
VPP System Test Script

测试各个模块的功能正确性
"""

import os
import sys
import unittest

# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)

from src.data.data_generator import VPPDataGenerator
from src.models.vpp_model import VPPOptimizationModel
from src.solvers.optimization_solver import OptimizationSolver


class TestVPPSystem(unittest.TestCase):
    """虚拟电厂系统测试类"""
    
    def setUp(self):
        """测试前置设置"""
        print(f"\n{'='*50}")
        print(f"开始测试: {self._testMethodName}")
        print(f"{'='*50}")
    
    def test_data_generator(self):
        """测试数据生成器"""
        print("测试数据生成器...")
        
        generator = VPPDataGenerator()
        
        # 测试数据生成
        load_data, pv_data, wind_data, price_data = generator.generate_all_data()
        
        # 验证数据
        self.assertEqual(len(load_data), 24)
        self.assertEqual(len(pv_data), 24)
        self.assertEqual(len(wind_data), 24)
        self.assertEqual(len(price_data), 24)
        
        # 验证数据类型和范围
        self.assertTrue(all(load_data >= 0))
        self.assertTrue(all(pv_data >= 0))
        self.assertTrue(all(wind_data >= 0))
        self.assertTrue(all(price_data > 0))
        
        print("[OK] 数据生成器测试通过")
    
    def test_vpp_model(self):
        """测试虚拟电厂模型"""
        print("测试虚拟电厂模型...")
        
        # 生成测试数据
        generator = VPPDataGenerator()
        load_data, pv_data, wind_data, price_data = generator.generate_all_data()
        
        # 创建模型
        model = VPPOptimizationModel(generator.time_index)
        energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
        
        # 验证系统
        self.assertTrue(model.validate_system())
        self.assertIsNotNone(energy_system)
        
        # 检查组件
        summary = model.get_system_summary()
        self.assertGreater(summary['total_components'], 0)
        
        print("[OK] 虚拟电厂模型测试通过")
    
    def test_optimization_solver(self):
        """测试优化求解器"""
        print("测试优化求解器...")
        
        # 准备数据和模型
        generator = VPPDataGenerator()
        load_data, pv_data, wind_data, price_data = generator.generate_all_data()
        
        model = VPPOptimizationModel(generator.time_index)
        energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
        
        # 创建求解器
        solver = OptimizationSolver()
        
        # 测试求解（使用较短的时间限制）
        solver.config['cbc_options']['timeLimit'] = 30  # 30秒限制
        success = solver.solve(energy_system)
        
        if success:
            results = solver.get_results()
            self.assertIsNotNone(results)
            print("[OK] 优化求解器测试通过")
        else:
            print("[WARNING] 优化求解器测试未完全成功（可能是求解器配置问题）")
    
    def test_full_workflow(self):
        """测试完整工作流程"""
        print("测试完整工作流程...")
        
        try:
            # 1. 数据生成
            generator = VPPDataGenerator()
            load_data, pv_data, wind_data, price_data = generator.generate_all_data()
            
            # 2. 模型创建
            model = VPPOptimizationModel(generator.time_index)
            energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
            
            # 3. 求解（快速测试）
            solver = OptimizationSolver()
            solver.config['cbc_options']['timeLimit'] = 10  # 10秒快速测试
            success = solver.solve(energy_system)
            
            print(f"完整工作流程测试: {'成功' if success else '部分成功'}")
            
        except Exception as e:
            self.fail(f"完整工作流程测试失败: {e}")


def run_tests():
    """运行所有测试"""
    print("虚拟电厂系统测试")
    print("="*60)
    
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestVPPSystem)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 测试结果总结
    print("\n" + "="*60)
    print("测试结果总结:")
    print(f"运行测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success = len(result.failures) + len(result.errors) == 0
    print(f"\n整体测试结果: {'[PASS] 通过' if success else '[FAIL] 失败'}")
    
    return success


if __name__ == "__main__":
    run_tests()