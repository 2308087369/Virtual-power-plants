"""
虚拟电厂数据生成器
VPP Data Generator

生成虚拟电厂优化调度所需的各类时间序列数据，并提供需求响应、
多时间尺度调度和不确定性场景生成能力。
"""

import os
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from scipy.interpolate import interp1d


class VPPDataGenerator:
    """虚拟电厂数据生成器"""

    def __init__(self, config_path: Optional[str] = None, load_scale_factor: float = 1.0):
        """
        初始化数据生成器

        Args:
            config_path: 配置文件路径，如果为None则使用默认配置
            load_scale_factor: 负荷缩放因子，1.0为原始大小，0.5为减半，2.0为翻倍
        """
        self.config = self._load_config(config_path)
        self.load_scale_factor = load_scale_factor
        self.periods = self.config["time_settings"]["periods"]
        self.time_index = self._create_time_index()
        self.random_seed = self.config.get("random_seed", 42)
        self.rng = np.random.default_rng(self.random_seed)
        self.last_generated_data: Optional[Tuple[pd.Series, pd.Series, pd.Series, pd.Series]] = None

    def _load_config(self, config_path: Optional[str]) -> Dict:
        """加载配置文件"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config",
                "system_config.yaml",
            )

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"配置文件未找到: {config_path}，使用默认配置")
            return self._get_default_config()
        except Exception as e:
            print(f"加载配置文件失败: {e}，使用默认配置")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "time_settings": {
                "periods": 24,
                "start_date": "2024-01-01",
                "frequency": "H",
            },
            "load_profile": {
                "base_load_pattern": [
                    45,
                    42,
                    40,
                    38,
                    37,
                    39,
                    42,
                    48,
                    55,
                    60,
                    65,
                    68,
                    70,
                    72,
                    70,
                    68,
                    66,
                    65,
                    62,
                    58,
                    55,
                    52,
                    48,
                    46,
                ],
                "load_uncertainty": 0.02,
            },
            "renewable_patterns": {
                "pv_pattern": [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0.05,
                    0.15,
                    0.35,
                    0.55,
                    0.75,
                    0.85,
                    0.90,
                    0.95,
                    0.90,
                    0.80,
                    0.65,
                    0.45,
                    0.25,
                    0.10,
                    0.02,
                    0,
                    0,
                    0,
                ],
                "weather_uncertainty": {"mean": 0.9, "std": 0.1, "min": 0.3, "max": 1.0},
            },
            "electricity_prices": {
                "base_price_pattern": [
                    300,
                    280,
                    260,
                    250,
                    250,
                    270,
                    320,
                    380,
                    420,
                    450,
                    480,
                    500,
                    520,
                    540,
                    530,
                    510,
                    480,
                    460,
                    440,
                    420,
                    400,
                    370,
                    340,
                    320,
                ],
                "price_volatility": 0.05,
            },
            "price_based_dr": {
                "enabled": False,
                "tariff_structure": {
                    "peak_hours": [8, 11, 18, 21],
                    "valley_hours": [0, 7],
                    "peak_price_ratio": 1.5,
                    "valley_price_ratio": 0.5,
                },
            },
            "multi_time_scheduling": {
                "enabled": False,
                "intraday_horizon_hours": 6,
                "intraday_resolution_minutes": 30,
                "realtime_horizon_hours": 2,
                "realtime_resolution_minutes": 15,
            },
            "uncertainty_scenarios": {
                "enabled": False,
                "num_scenarios": 3,
                "load_sigma": 0.03,
                "renewable_sigma": 0.1,
                "price_sigma": 0.05,
            },
            "energy_resources": {
                "photovoltaic": {"capacity_mw": 50},
                "wind": {"capacity_mw": 30},
            },
            "random_seed": 42,
        }

    def _create_time_index(self) -> pd.DatetimeIndex:
        """创建时间索引"""
        start_date = self.config["time_settings"]["start_date"]
        frequency = self.config["time_settings"]["frequency"]
        return pd.date_range(start=start_date, periods=self.periods, freq=frequency)

    def _interpolate_pattern(self, pattern: list, target_periods: int) -> np.ndarray:
        """插值扩展模式到目标时间段数"""
        if len(pattern) == target_periods:
            return np.array(pattern, dtype=float)

        interpolation_kind = "cubic" if len(pattern) >= 4 else "linear"
        f = interp1d(
            np.linspace(0, 1, len(pattern)),
            pattern,
            kind=interpolation_kind,
            bounds_error=False,
            fill_value="extrapolate",
        )
        return f(np.linspace(0, 1, target_periods))

    def _get_hour_mask(self, time_index: pd.DatetimeIndex, hour_ranges: list) -> np.ndarray:
        """根据小时区间生成掩码"""
        mask = np.zeros(len(time_index), dtype=float)
        for start_hour, end_hour in hour_ranges:
            for idx, ts in enumerate(time_index):
                if start_hour <= ts.hour <= end_hour:
                    mask[idx] = 1.0
        return mask

    def _apply_price_based_dr(self, prices: pd.Series) -> pd.Series:
        """应用价格型需求响应电价机制"""
        dr_config = self.config.get("price_based_dr", {})
        if not dr_config.get("enabled", False):
            return prices

        tariff = dr_config.get("tariff_structure", {})
        peak_mask = self._get_hour_mask(
            prices.index,
            [
                (
                    tariff.get("peak_hours", [8, 11, 18, 21])[0],
                    tariff.get("peak_hours", [8, 11, 18, 21])[1],
                ),
                (
                    tariff.get("peak_hours", [8, 11, 18, 21])[2],
                    tariff.get("peak_hours", [8, 11, 18, 21])[3],
                ),
            ],
        )
        valley_mask = self._get_hour_mask(
            prices.index,
            [
                (
                    tariff.get("valley_hours", [0, 7])[0],
                    tariff.get("valley_hours", [0, 7])[1],
                )
            ],
        )

        adjusted = prices.astype(float).copy()
        adjusted = adjusted * np.where(peak_mask > 0, tariff.get("peak_price_ratio", 1.5), 1.0)
        adjusted = adjusted * np.where(valley_mask > 0, tariff.get("valley_price_ratio", 0.5), 1.0)
        return adjusted.rename("electricity_price_yuan_mwh")

    def _resample_series(self, series: pd.Series, resolution_minutes: int, periods: int) -> pd.Series:
        """将序列插值到更细的时间分辨率"""
        target_index = pd.date_range(
            start=series.index[0],
            periods=periods,
            freq=f"{resolution_minutes}min",
        )
        source_seconds = (series.index - series.index[0]).total_seconds().to_numpy()
        target_seconds = (target_index - target_index[0]).total_seconds().to_numpy()
        values = np.interp(target_seconds, source_seconds, series.values)
        return pd.Series(values, index=target_index, name=series.name)

    def generate_load_profile(self) -> pd.Series:
        """生成负荷需求曲线数据"""
        base_pattern = self.config["load_profile"]["base_load_pattern"]
        uncertainty = self.config["load_profile"]["load_uncertainty"]

        load_pattern = self._interpolate_pattern(base_pattern, self.periods)
        load_pattern = load_pattern * self.load_scale_factor
        noise = self.rng.normal(0, uncertainty, self.periods)
        load_profile = load_pattern * (1 + noise)
        load_profile = np.maximum(load_profile, load_pattern * 0.5)

        return pd.Series(load_profile, index=self.time_index, name="load_demand_mw")

    def generate_pv_profile(self) -> pd.Series:
        """生成光伏发电出力曲线数据"""
        pv_pattern = self.config["renewable_patterns"]["pv_pattern"]
        weather_config = self.config["renewable_patterns"]["weather_uncertainty"]
        pv_capacity = self.config["energy_resources"]["photovoltaic"]["capacity_mw"]

        pv_normalized = self._interpolate_pattern(pv_pattern, self.periods)
        pv_output = pv_normalized * pv_capacity

        weather_factor = self.rng.normal(
            weather_config["mean"],
            weather_config["std"],
            self.periods,
        )
        weather_factor = np.clip(
            weather_factor,
            weather_config["min"],
            weather_config["max"],
        )
        pv_output = np.maximum(pv_output * weather_factor, 0)
        return pd.Series(pv_output, index=self.time_index, name="pv_generation_mw")

    def generate_wind_profile(self) -> pd.Series:
        """生成风电发电出力曲线数据"""
        wind_capacity = self.config["energy_resources"]["wind"]["capacity_mw"]
        wind_normalized = self.rng.weibull(2.0, self.periods)
        wind_normalized = np.clip(wind_normalized * 0.6, 0, 1)
        wind_output = wind_normalized * wind_capacity
        return pd.Series(wind_output, index=self.time_index, name="wind_generation_mw")

    def generate_electricity_prices(self) -> pd.Series:
        """生成电力市场价格数据"""
        price_pattern = self.config["electricity_prices"]["base_price_pattern"]
        volatility = self.config["electricity_prices"]["price_volatility"]

        prices = self._interpolate_pattern(price_pattern, self.periods)
        price_volatility = self.rng.normal(1, volatility, self.periods)
        prices = prices * price_volatility
        prices = np.maximum(prices, np.array(price_pattern).min() * 0.5)
        price_series = pd.Series(prices, index=self.time_index, name="electricity_price_yuan_mwh")
        return self._apply_price_based_dr(price_series)

    def generate_all_data(self) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """生成所有输入数据"""
        print("正在生成虚拟电厂数据...")

        load_data = self.generate_load_profile()
        pv_data = self.generate_pv_profile()
        wind_data = self.generate_wind_profile()
        price_data = self.generate_electricity_prices()

        print(f"数据生成完成！时间段: {self.periods} 小时")
        print(f"负荷范围: {load_data.min():.1f} - {load_data.max():.1f} MW")
        print(f"光伏出力范围: {pv_data.min():.1f} - {pv_data.max():.1f} MW")
        print(f"风电出力范围: {wind_data.min():.1f} - {wind_data.max():.1f} MW")
        print(f"电价范围: {price_data.min():.1f} - {price_data.max():.1f} 元/MWh")

        self.last_generated_data = (load_data, pv_data, wind_data, price_data)
        return load_data, pv_data, wind_data, price_data

    def generate_multiscale_datasets(
        self,
        load_data: Optional[pd.Series] = None,
        pv_data: Optional[pd.Series] = None,
        wind_data: Optional[pd.Series] = None,
        price_data: Optional[pd.Series] = None,
    ) -> Dict[str, pd.DataFrame]:
        """生成多时间尺度调度数据集"""
        if load_data is None or pv_data is None or wind_data is None or price_data is None:
            load_data, pv_data, wind_data, price_data = self.generate_all_data()

        multiscale_config = self.config.get("multi_time_scheduling", {})
        intraday_resolution = multiscale_config.get("intraday_resolution_minutes", 30)
        realtime_resolution = multiscale_config.get("realtime_resolution_minutes", 15)

        day_ahead = pd.DataFrame(
            {
                "load_demand_mw": load_data,
                "pv_generation_mw": pv_data,
                "wind_generation_mw": wind_data,
                "electricity_price_yuan_mwh": price_data,
            }
        )

        total_hours = max(int(round((self.time_index[-1] - self.time_index[0]).total_seconds() / 3600.0)) + 1, 1)
        intraday_points = max(int(total_hours * 60 / intraday_resolution), 1)
        realtime_points = max(int(total_hours * 60 / realtime_resolution), 1)

        intraday = pd.DataFrame(
            {
                "load_demand_mw": self._resample_series(load_data, intraday_resolution, intraday_points),
                "pv_generation_mw": self._resample_series(pv_data, intraday_resolution, intraday_points),
                "wind_generation_mw": self._resample_series(wind_data, intraday_resolution, intraday_points),
                "electricity_price_yuan_mwh": self._resample_series(price_data, intraday_resolution, intraday_points),
            }
        )

        realtime = pd.DataFrame(
            {
                "load_demand_mw": self._resample_series(load_data, realtime_resolution, realtime_points),
                "pv_generation_mw": self._resample_series(pv_data, realtime_resolution, realtime_points),
                "wind_generation_mw": self._resample_series(wind_data, realtime_resolution, realtime_points),
                "electricity_price_yuan_mwh": self._resample_series(price_data, realtime_resolution, realtime_points),
            }
        )

        return {
            "day_ahead": day_ahead,
            "intraday": intraday,
            "realtime": realtime,
        }

    def generate_uncertainty_scenarios(
        self,
        load_data: Optional[pd.Series] = None,
        pv_data: Optional[pd.Series] = None,
        wind_data: Optional[pd.Series] = None,
        price_data: Optional[pd.Series] = None,
        num_scenarios: Optional[int] = None,
    ) -> Dict[str, pd.DataFrame]:
        """生成不确定性场景数据"""
        if load_data is None or pv_data is None or wind_data is None or price_data is None:
            load_data, pv_data, wind_data, price_data = self.generate_all_data()

        scenario_config = self.config.get("uncertainty_scenarios", {})
        scenario_count = num_scenarios or scenario_config.get("num_scenarios", 5)
        load_sigma = scenario_config.get("load_sigma", 0.04)
        renewable_sigma = scenario_config.get("renewable_sigma", 0.12)
        price_sigma = scenario_config.get("price_sigma", 0.08)

        scenarios = {}
        for idx in range(1, scenario_count + 1):
            load_factor = np.clip(self.rng.normal(1.0, load_sigma, len(load_data)), 0.8, 1.2)
            renewable_factor = np.clip(self.rng.normal(1.0, renewable_sigma, len(load_data)), 0.6, 1.25)
            price_factor = np.clip(self.rng.normal(1.0, price_sigma, len(load_data)), 0.7, 1.35)

            scenarios[f"scenario_{idx}"] = pd.DataFrame(
                {
                    "load_demand_mw": load_data.values * load_factor,
                    "pv_generation_mw": pv_data.values * renewable_factor,
                    "wind_generation_mw": wind_data.values * renewable_factor,
                    "electricity_price_yuan_mwh": price_data.values * price_factor,
                },
                index=self.time_index,
            )

        return scenarios

    def summarize_uncertainty_scenarios(self, scenarios: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """汇总不确定性场景统计信息"""
        records = []
        for scenario_name, scenario_df in scenarios.items():
            records.append(
                {
                    "scenario": scenario_name,
                    "load_total_mwh": scenario_df["load_demand_mw"].sum(),
                    "pv_total_mwh": scenario_df["pv_generation_mw"].sum(),
                    "wind_total_mwh": scenario_df["wind_generation_mw"].sum(),
                    "avg_price_yuan_mwh": scenario_df["electricity_price_yuan_mwh"].mean(),
                    "load_peak_mw": scenario_df["load_demand_mw"].max(),
                }
            )
        return pd.DataFrame(records)

    def save_data(self, output_dir: str = "outputs", filename: str = None) -> str:
        """保存生成的数据到文件"""
        if self.last_generated_data is None:
            self.generate_all_data()
        load_data, pv_data, wind_data, price_data = self.last_generated_data
        os.makedirs(output_dir, exist_ok=True)

        data_df = pd.DataFrame(
            {
                "load_demand_mw": load_data,
                "pv_generation_mw": pv_data,
                "wind_generation_mw": wind_data,
                "electricity_price_yuan_mwh": price_data,
            }
        )

        if filename is None:
            timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            filename = f"vpp_input_data_{timestamp}.csv"

        filepath = os.path.join(output_dir, filename)
        data_df.to_csv(filepath, index=True, encoding="utf-8-sig")
        print(f"数据已保存到: {filepath}")
        return filepath

    def save_data_to_session(self, session_context, filename: str = "input_data.csv") -> str:
        """保存数据到会话目录"""
        if self.last_generated_data is None:
            self.generate_all_data()
        load_data, pv_data, wind_data, price_data = self.last_generated_data
        data_df = pd.DataFrame(
            {
                "load_demand_mw": load_data,
                "pv_generation_mw": pv_data,
                "wind_generation_mw": wind_data,
                "electricity_price_yuan_mwh": price_data,
            }
        )
        filepath = session_context.save_file("input_data", filename, data_df)
        return str(filepath)


if __name__ == "__main__":
    generator = VPPDataGenerator()
    filepath = generator.save_data()
    load_data, pv_data, wind_data, price_data = generator.generate_all_data()

    print("\n数据预览:")
    print(f"数据文件: {filepath}")
    print(f"时间范围: {generator.time_index[0]} 到 {generator.time_index[-1]}")
    print(f"总时间段: {len(generator.time_index)} 小时")
