"""
路线图增强能力测试

验证 EV、工业可中断负荷、楼宇 HVAC、需求响应、多时间尺度和场景生成功能
是否已接入到项目主链路。
"""

import os
import sys
import tempfile
import unittest

import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from src.analysis.result_analyzer import ResultAnalyzer
from src.data.data_generator import VPPDataGenerator
from src.models.vpp_model import VPPOptimizationModel
from src.visualization.plot_generator import PlotGenerator
from main import build_hierarchical_stage_plan


class TestRoadmapFeatures(unittest.TestCase):
    """路线图增强能力测试"""

    def setUp(self):
        self.generator = VPPDataGenerator()
        self.load_data, self.pv_data, self.wind_data, self.price_data = self.generator.generate_all_data()

    def test_config_sections_exist(self):
        """测试路线图配置段存在"""
        for key in [
            "ev_charging_station",
            "interruptible_loads",
            "building_hvac",
            "price_based_dr",
            "incentive_based_dr",
            "multi_time_scheduling",
            "uncertainty_scenarios",
        ]:
            self.assertIn(key, self.generator.config)

    def test_multiscale_and_scenarios_generation(self):
        """测试多时间尺度与场景生成"""
        multiscale = self.generator.generate_multiscale_datasets(
            self.load_data, self.pv_data, self.wind_data, self.price_data
        )
        self.assertIn("day_ahead", multiscale)
        self.assertIn("intraday", multiscale)
        self.assertIn("realtime", multiscale)
        self.assertGreater(len(multiscale["intraday"]), 0)
        self.assertGreater(len(multiscale["realtime"]), 0)
        self.assertGreater(len(multiscale["intraday"]), len(multiscale["day_ahead"]))
        self.assertGreater(len(multiscale["realtime"]), len(multiscale["intraday"]))

        scenarios = self.generator.generate_uncertainty_scenarios(
            self.load_data, self.pv_data, self.wind_data, self.price_data, num_scenarios=3
        )
        self.assertEqual(len(scenarios), 3)
        summary_df = self.generator.summarize_uncertainty_scenarios(scenarios)
        self.assertEqual(len(summary_df), 3)
        self.assertIn("avg_price_yuan_mwh", summary_df.columns)

    def test_hierarchical_stage_plan(self):
        """测试分层调度计划构建"""
        multiscale = self.generator.generate_multiscale_datasets(
            self.load_data, self.pv_data, self.wind_data, self.price_data
        )
        stage_plan = build_hierarchical_stage_plan(self.generator, multiscale)

        self.assertEqual([stage["stage_name"] for stage in stage_plan], ["day_ahead", "intraday", "realtime"])
        self.assertFalse(stage_plan[0]["rolling"])
        self.assertTrue(stage_plan[1]["rolling"])
        self.assertTrue(stage_plan[2]["rolling"])
        self.assertEqual(stage_plan[0]["rolling_horizon_steps"], len(multiscale["day_ahead"]))
        self.assertGreater(stage_plan[1]["rolling_horizon_steps"], 1)
        self.assertGreater(stage_plan[2]["rolling_horizon_steps"], 1)

    def test_model_contains_new_flexible_resources(self):
        """测试模型中包含新增柔性资源组件"""
        model = VPPOptimizationModel(self.generator.time_index)
        energy_system = model.create_energy_system(
            self.load_data, self.pv_data, self.wind_data, self.price_data
        )
        labels = {node.label for node in energy_system.nodes}

        self.assertIn("ev_charging_station", labels)
        self.assertIn("interruptible_load_industrial_plant_1", labels)
        self.assertIn("building_hvac_office_building_1", labels)

    def test_plot_generator_handles_enhanced_results(self):
        """测试增强图表生成"""
        results_df = pd.DataFrame(
            {
                "load_demand_mw": self.load_data,
                "pv_generation_mw": self.pv_data,
                "wind_generation_mw": self.wind_data,
                "battery_charge_mw": -0.1,
                "battery_discharge_mw": 0.2,
                "total_supply_mw": self.load_data,
                "grid_purchase_mw": 0.5,
                "grid_sale_mw": 0.1,
                "chiller_load_mw": 0.2,
                "heat_pump_load_mw": 0.1,
                "ev_charging_power_mw": 0.3,
                "interruptible_load_industrial_plant_1_mw": 0.4,
                "building_hvac_office_building_1_mw": 0.25,
                "total_flexible_load_mw": 1.25,
            },
            index=self.generator.time_index,
        )
        economics = {
            "renewable_cost_yuan": 100,
            "gas_cost_yuan": 0,
            "battery_total_cost_yuan": 50,
            "adjustable_loads_cost_yuan": 40,
            "ev_charging_cost_yuan": 10,
            "interruptible_load_compensation_yuan": 20,
            "building_hvac_cost_yuan": 15,
            "grid_purchase_cost_yuan": 200,
            "ancillary_services_revenue_yuan": 30,
            "demand_response_revenue_yuan": 25,
        }

        plot_generator = PlotGenerator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            plot_path = plot_generator.generate_all_plots(
                results_df, economics, self.price_data, output_dir=tmp_dir
            )
            self.assertTrue(os.path.exists(plot_path))


def run_tests():
    """运行路线图增强测试"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestRoadmapFeatures)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return len(result.failures) + len(result.errors) == 0


if __name__ == "__main__":
    run_tests()
