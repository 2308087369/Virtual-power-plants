"""
CBC求解器测试脚本
"""

import os
import sys
# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # 从tests目录回到项目根目录
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)

# 测试CBC路径
cbc_path = os.path.join(project_root, 'cbc', 'bin', 'cbc.exe')
print(f"CBC路径: {cbc_path}")
print(f"文件存在: {os.path.exists(cbc_path)}")

# 设置环境变量
os.environ['CBC_EXECUTABLE'] = cbc_path

# 测试数据生成
from src.data.data_generator import VPPDataGenerator
print("\n测试数据生成...")
gen = VPPDataGenerator()
load_data, pv_data, wind_data, price_data = gen.generate_all_data()
print("[OK] 数据生成成功")

# 测试模型创建
from src.models.vpp_model import VPPOptimizationModel
print("\n测试模型创建...")
model = VPPOptimizationModel(gen.time_index)
energy_system = model.create_energy_system(load_data, pv_data, wind_data, price_data)
print("[OK] 模型创建成功")

# 测试简单求解
print("\n测试求解器...")
try:
    import oemof.solph as solph
    opt_model = solph.Model(energy_system)
    
    # 使用pyomo调用CBC
    from pyomo.opt import SolverFactory
    solver = SolverFactory('cbc', executable=cbc_path)
    
    if solver.available():
        print("[OK] CBC求解器可用")
        
        # 尝试简单求解
        results = solver.solve(opt_model, tee=False)
        if results.solver.termination_condition.value == 'optimal':
            print("[OK] 求解成功")
        else:
            print(f"[WARNING] 求解状态: {results.solver.termination_condition}")
    else:
        print("[FAIL] CBC求解器不可用")
        
except Exception as e:
    print(f"[FAIL] 求解器测试失败: {e}")

print("\n测试完成！")
