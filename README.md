# Virtual Power Plant Optimization System

[中文版](README_zh.md) | **English**

An advanced Virtual Power Plant (VPP) multi-resource coordination and optimization system built on oemof-solph framework with CBC solver for linear programming optimization.

![VPP Optimization Results](examples/optimization_results.png)

## 🎯 Overview

This project provides intelligent energy resource scheduling strategies for VPPs, achieving coordinated operation and cost optimization of multiple energy resources including renewable energy, conventional generation, energy storage systems, adjustable loads, and grid interaction.

**Note**: This project uses virtual data generated through data generation methods. To replace with real data, please refer to the generation code for replacement.

### Key Features
- **Multi-energy modeling**: PV, wind, gas turbine, energy storage, adjustable loads, grid interaction
- **Six scheduling modes**: renewable_storage, adjustable_storage, traditional, no_renewable, storage_only, full_system
- **Multi-objective optimization**: Cost minimization and profit maximization
- **Ancillary services**: Energy storage participation in frequency regulation and spinning reserve
- **Demand response**: Adjustable loads (chiller, heat pump) with demand response capabilities
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

# Demo mode
python main.py --demo

# Specific scheduling mode
python main.py --mode=full_system

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
```

## 🔧 Configuration

Edit configuration files to customize system parameters:

**System Configuration** (`config/system_config.yaml`):
- Energy resource capacities and costs
- Storage system parameters (10MW/40MWh)
- Adjustable load settings
- Ancillary service parameters

**Solver Configuration** (`config/solver_config.yaml`):
- CBC solver settings (threads, time limits, gaps)

## 📊 System Components

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
- `optimization_results.csv`: Detailed scheduling results
- `economics_analysis.csv`: Economic analysis with ancillary service revenues
- `technical_metrics.csv`: Technical performance indicators
- `summary_report.txt`: Operation summary with mode-specific insights
- `optimization_results.png`: Visualization charts

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

## 📈 Typical Results

Based on 24-hour optimization:
- **Renewable Penetration**: 49.1%
- **Ancillary Service Revenue**: 49,450 yuan/day
- **Optimal Mode**: renewable_storage (most profitable)
- **Storage Arbitrage**: Effective peak shaving and valley filling

## 🛠️ Technology Stack

- **Optimization**: oemof-solph 0.6.0 + CBC solver
- **Modeling**: pyomo 6.6.0+
- **Data Processing**: pandas, numpy
- **Visualization**: matplotlib
- **Configuration**: PyYAML
- **Python**: 3.12+

## 📄 License

MIT License - See [LICENSE](LICENSE) file for details