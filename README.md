# Virtual Power Plant Optimization System

[中文版](README_zh.md) | **English**

An advanced Virtual Power Plant (VPP) multi-resource coordination and optimization system built on oemof-solph framework with CBC solver for linear programming optimization.

![VPP Optimization Results](docs/assets/realtime_hierarchical_results.png)

## 🎯 Overview

This project provides intelligent energy resource scheduling strategies for VPPs, achieving coordinated operation and cost optimization of multiple energy resources including renewable energy, conventional generation, energy storage systems, adjustable loads, and grid interaction.

**Note**: This project uses virtual data generated through data generation methods. To replace with real data, please refer to the generation code for replacement.

### Key Features
- **Multi-energy modeling**: PV, wind, gas turbine, energy storage, adjustable loads, grid interaction
- **Six scheduling modes**: renewable_storage, adjustable_storage, traditional, no_renewable, storage_only, full_system
- **Multi-objective optimization**: Cost minimization and profit maximization
- **Ancillary services**: Energy storage participation in frequency regulation and spinning reserve
- **Demand response**: Adjustable loads (chiller, heat pump) with demand response capabilities
- **Hierarchical dispatch**: Day-ahead planning, intraday rolling correction, and real-time rolling execution
- **Separated storage modeling**: Converter + GenericStorage architecture ensuring physical constraints
- **Interactive interface**: User-friendly mode selection and optimization objective choice

## 🚀 Quick Start

### Installation
```bash
git clone https://github.com/2308087369/Virtual-power-plants
cd vpp_opt_test_qqder

# Install dependencies (recommended with uv)
uv pip install -e .

# Or use pip
pip install -e .
```

### Usage
```bash
# Interactive mode (recommended)
python main.py

# Specific hierarchical scheduling mode
python main.py --mode full_system --objective cost_minimization

# Compare all modes
python main.py --compare-all

# List available modes
python main.py --list-modes
```

### Testing
```bash
# Run all tests
python tests/run_tests.py

# Run specific test categories
python tests/run_tests.py --type basic        # Basic functionality
python tests/run_tests.py --type cbc          # CBC solver
python tests/run_tests.py --type scheduling   # Scheduling modes
python tests/run_tests.py --type objectives   # Optimization objectives
python tests/run_tests.py --test roadmap      # Roadmap and hierarchical dispatch checks
```

## Configuration

Edit configuration files to customize system parameters:

**System Configuration** (`config/system_config.yaml`):
- Energy resource capacities and costs
- Storage system parameters (10MW/40MWh)
- Adjustable load settings
- Ancillary service parameters

**Solver Configuration** (`config/solver_config.yaml`):
- CBC solver settings (threads, time limits, gaps)

## System Components

### Generation Resources
- **PV**: 50MW capacity, 5 yuan/MWh cost
- **Wind**: 30MW capacity, 8 yuan/MWh cost
- **Gas Turbine**: 100MW capacity, 600 yuan/MWh cost

### Energy Storage System
- **Power Capacity**: 10MW (charge/discharge)
- **Energy Capacity**: 40MWh (4-hour storage)
- **Efficiency**: 95% charge, 93% discharge
- **SOC Range**: 10%-95%
- **Constraint**: Separated modeling ensures charge/discharge exclusivity

### Adjustable Loads
- **Chiller**: 20MW rated power, 30%-100% adjustment range
- **Heat Pump**: 15MW rated power, 20%-100% adjustment range

## 🎯 Optimization Objectives

1. **Cost Minimization**: Minimize total operating costs
2. **Profit Maximization**: Maximize total profit (sale revenue + ancillary services - all costs)

## 📁 Output Structure

Results organized in `outputs/{mode}_{objective}_{timestamp}/`:
- `data/`: Base input data and multi-timescale input datasets
- `results/`: Day-ahead, intraday, and real-time dispatch results
- `economics/`: Stage-level economic analysis
- `metrics/`: Stage-level metrics, scenario summary, and hierarchical stage summary
- `reports/`: Stage reports and the final `hierarchical_dispatch_report.txt`
- `plots/`: Day-ahead, intraday, and real-time visualization charts

## 🏗️ Architecture

```
vpp_opt_test_qqder/
├── src/                        # Core modules
│   ├── data/                   # Data generation
│   ├── models/                 # Optimization modeling
│   ├── solvers/                # CBC solver integration
│   ├── analysis/               # Result analysis
│   └── visualization/          # Chart generation
├── config/                     # Configuration files
├── tests/                      # Test suite
└── outputs/                    # Results output
```

## 🔍 Key Technical Innovation

**Separated Energy Storage Modeling**: Solves traditional GenericStorage constraint failures through Converter + GenericStorage architecture, ensuring:
- Zero simultaneous charge/discharge periods
- Power limits strictly enforced (≤10MW)
- Physical constraint compliance
- Executable scheduling results

## 📈 Latest Hierarchical Results

Latest full-system cost-minimization experiment:
- **Command**: `python main.py --mode full_system --objective cost_minimization`
- **Output Directory**: `outputs/full_system_cost_minimization_20260529_095947/`
- **Scenario Summary**: 5 uncertainty scenarios, average price range `415.07-428.22` yuan/MWh

### Stage Summary

| Stage | Time Steps | Net Cost (yuan) | Avg Cost (yuan/MWh) | Load (MWh) | Renewable Penetration | Final SOC |
|---|---:|---:|---:|---:|---:|---:|
| Day-ahead | 24 | -76,490.75 | -604.21 | 126.60 | 67.93% | 0.0000 |
| Intraday | 48 | -51,139.96 | -389.80 | 131.20 | 62.20% | 0.0065 |
| Real-time | 96 | -15,631.36 | -119.14 | 131.20 | 59.53% | 0.0020 |

### Rolling Execution Notes
- **Intraday rolling windows**: 48 windows, with optimized execution in part of the morning and afternoon windows and baseline fallback for infeasible windows
- **Real-time rolling windows**: 96 windows, with optimized execution concentrated around `05:30-06:45`, `15:30-16:45`, and `21:30-21:45`
- **Operational interpretation**: The hierarchical workflow now completes end-to-end, while short rolling windows still rely on baseline fallback when local constraints become infeasible

### Latest Visualizations

Day-ahead dispatch:

![Day-Ahead Hierarchical Dispatch](docs/assets/day_ahead_hierarchical_results.png)

Intraday rolling dispatch:

![Intraday Hierarchical Dispatch](docs/assets/intraday_hierarchical_results.png)

Real-time rolling dispatch:

![Real-Time Hierarchical Dispatch](docs/assets/realtime_hierarchical_results.png)

### Latest Result Files
- Stage summary: [hierarchical_stage_summary.csv](file:///d:/py_work/vpp_opt_test_qqder/outputs/full_system_cost_minimization_20260529_095947/metrics/hierarchical_stage_summary.csv)
- Final report: [hierarchical_dispatch_report.txt](file:///d:/py_work/vpp_opt_test_qqder/outputs/full_system_cost_minimization_20260529_095947/reports/hierarchical_dispatch_report.txt)
- Intraday windows: [intraday_rolling_windows.csv](file:///d:/py_work/vpp_opt_test_qqder/outputs/full_system_cost_minimization_20260529_095947/results/intraday_rolling_windows.csv)
- Real-time windows: [realtime_rolling_windows.csv](file:///d:/py_work/vpp_opt_test_qqder/outputs/full_system_cost_minimization_20260529_095947/results/realtime_rolling_windows.csv)

## 🛠️ Technology Stack

- **Optimization**: oemof-solph 0.6.0 + CBC solver
- **Modeling**: pyomo 6.6.0+
- **Data Processing**: pandas, numpy
- **Visualization**: matplotlib
- **Configuration**: PyYAML
- **Python**: 3.12+

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details
### Examples
- Microgrid optimization demo with full visualization:
  - Script: `examples/optimization_microgrid_complete.py`
  - README (CN): `examples/readme.md`
  - README (EN): `examples/readme_en.md`
  - Results: `examples/microgrid_results/` (figures and reports)
