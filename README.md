# Virtual Power Plant Optimization System

[中文版](README_zh.md) | **English**

An advanced Virtual Power Plant (VPP) multi-resource coordination and optimization system built on oemof-solph framework with CBC solver for linear programming optimization.

---

## 🌟 System Preview

![VPP Optimization Results](examples/optimization_results.png)

---

## 🎯 Project Overview

This project is a comprehensive Virtual Power Plant optimization solution designed to provide intelligent energy resource scheduling strategies for VPPs, achieving coordinated operation and cost optimization of multiple energy resources. The system integrates the modern **Source-Network-Load-Storage** integrated energy management concept, supporting collaborative optimization of renewable energy, conventional generation, energy storage systems, adjustable loads, and grid interaction.

## Notice!!!
This project uses virtual data generated through data generation methods. To replace with real data, please refer to the generation code for replacement.

### Core Features
- **Multi-energy modeling**: PV, wind, gas turbine, energy storage, adjustable loads, grid interaction
- **Intelligent scheduling**: Optimal scheduling strategy based on linear programming, supporting multiple optimization objectives
- **Multi-objective optimization**: Support for both cost minimization and profit maximization objectives
- **Multi-mode scheduling**: 6 different scheduling modes for various application scenarios
- **Ancillary services**: Energy storage participation in frequency regulation and spinning reserve services
- **Demand response**: Adjustable loads (chiller, heat pump) participate in system optimization
- **Real-time analysis**: Complete economic and technical performance analysis including ancillary service revenue assessment
- **Visualization**: Rich charts and report generation with ancillary service strategy display
- **Configuration**: Flexible YAML configuration file management with ancillary service parameter adjustment
- **Interactive interface**: User-friendly interactive mode selection interface

### Latest Features ✨
- ✅ **Multi-objective optimization**: New profit maximization objective, supporting dual objectives
- ✅ **Interactive selection**: Intelligent interactive interface for flexible selection of optimization objectives and scheduling modes
- ✅ **Mode comparison**: Support for comparative analysis of all scheduling modes with detailed reports
- ✅ **Session management**: New session context management with automatic result file organization
- 🔥 **Energy storage modeling refactoring**: Separated modeling architecture ensuring charge/discharge exclusivity and power constraints
- ✅ **Physical constraints**: Real physical characteristic modeling of energy storage systems ensuring executable scheduling results
- ✅ **Ancillary services**: Energy storage participation in frequency regulation and spinning reserve services
- ✅ **Adjustable loads**: Chiller and heat pump adjustable loads supporting demand response
- ✅ **Economic optimization**: Comprehensive consideration of generation costs, storage costs, adjustable load costs, and ancillary service revenues
- ✅ **Intelligent visualization**: Automatic component detection with dynamic chart generation including ancillary service analysis
- ✅ **Complete reports**: Detailed operation reports including ancillary service and adjustable load analysis

## 🏗️ System Architecture

```
vpp_opt_test_qqder/
├── README.md                    # Project documentation (English)
├── README_zh.md                 # Project documentation (Chinese)
├── pyproject.toml              # Project configuration
├── main.py                     # Main program entry
├── config/                     # Configuration files
│   ├── system_config.yaml     # System parameter configuration
│   └── solver_config.yaml     # Solver configuration
├── docs/                       # Project documentation
│   └── optimization_modeling.md # Detailed optimization modeling
├── src/                        # Source code
│   ├── __init__.py
│   ├── data/                   # Data generation module
│   │   ├── __init__.py
│   │   └── data_generator.py   # Load, PV, wind, price data generation
│   ├── models/                 # Optimization model module
│   │   ├── __init__.py
│   │   └── vpp_model.py        # oemof-solph energy system modeling
│   ├── solvers/                # Solver module
│   │   ├── __init__.py
│   │   └── optimization_solver.py # CBC solver configuration and optimization
│   ├── analysis/               # Result analysis module
│   │   ├── __init__.py
│   │   └── result_analyzer.py  # Economic analysis and performance metrics
│   └── visualization/          # Visualization module
│       ├── __init__.py
│       └── plot_generator.py   # Result chart generation and reporting
├── tests/                      # Test files
│   └── test_vpp_system.py     # System tests
├── examples/                   # Examples and demos
│   └── demo_optimization.py   # Simple demo
├── outputs/                    # Output results
│   ├── plots/                  # Chart outputs
│   └── reports/                # Report outputs
├── logs/                       # Log files
├── cbc/                        # CBC solver
│   └── bin/
│       └── cbc.exe            # CBC executable
└── test_*.py                   # Function test scripts
```

## 🔧 Technology Stack

### Core Technologies
- **Optimization Engine**: oemof-solph 0.6.0 (Open-source energy system modeling framework)
- **Solver**: CBC (Coin-or Branch and Cut) linear programming solver
- **Modeling Tool**: pyomo 6.6.0+ (Mathematical modeling language)
- **Energy Storage Modeling**: Separated Converter + GenericStorage architecture
- **Constraint Management**: Strict physical constraint enforcement ensuring charge/discharge exclusivity
- **Data Processing**: pandas, numpy
- **Visualization**: matplotlib, plotly
- **Configuration Management**: PyYAML
- **Python Version**: 3.12+

### Dependencies
```toml
oemof.solph>=0.5.0      # Energy system modeling
pyomo>=6.6.0            # Mathematical optimization modeling
psutil>=7.0.0           # System monitoring
PyYAML>=6.0             # Configuration file parsing
scipy>=1.11.0           # Scientific computing
matplotlib>=3.8.0       # Chart plotting
pandas>=2.1.0           # Data analysis
numpy>=1.26.0           # Numerical computing
```

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone repository
git clone https://github.com/2308087369/Virtual-power-plants
cd vpp_opt_test_qqder

# Install dependencies (recommended with uv)
uv pip install -e .

# Or use pip
pip install -e .
```

### 2. Run Optimization

#### Interactive Mode (Recommended)
```bash
# Run interactive mode to select optimization objectives and scheduling modes
python main.py
```

#### Command Line Mode
```bash
# Run complete VPP optimization demo
python main.py --demo

# Run specific scheduling mode
python main.py --mode=full_system

# Run all modes comparison analysis
python main.py --compare-all

# List all available scheduling modes
python main.py --list-modes

# Show help information
python main.py --help
```

#### Available Scheduling Modes
- `renewable_storage`: Renewable energy + storage mode
- `adjustable_storage`: Adjustable load + storage mode  
- `traditional`: Traditional mode (no ancillary services)
- `no_renewable`: No renewable energy mode
- `storage_only`: Pure storage scheduling mode
- `full_system`: Complete system mode

#### Optimization Objectives
- `cost_minimization`: Cost minimization (default)
- `profit_maximization`: Profit maximization

### 3. Testing

```bash
# Run all tests
python test_runner.py

# Run basic function tests
python test_runner.py --type basic

# Test CBC solver
python test_runner.py --type cbc

# Test scheduling modes
python test_runner.py --type scheduling

# Test optimization objectives
python test_runner.py --type objectives

# Test adjustable load functionality
python test_runner.py --type loads

# Test ancillary service functionality
python test_runner.py --type ancillary

# Test complete flow
python test_runner.py --type flow

# Run unit tests
python tests/test_vpp_system.py
```

### 4. Custom Configuration

Edit configuration files to customize system parameters:

**System Configuration** (`config/system_config.yaml`):
```yaml
# Energy resource capacity configuration
energy_resources:
  photovoltaic:
    capacity_mw: 50          # PV installed capacity
  wind:
    capacity_mw: 30          # Wind installed capacity
  gas_turbine:
    capacity_mw: 100         # Gas turbine capacity
  battery_storage:
    power_capacity_mw: 10    # Energy storage power capacity
    energy_capacity_mwh: 40  # Energy storage energy capacity (4-hour storage)
    charge_efficiency: 0.95  # Charging efficiency
    discharge_efficiency: 0.93  # Discharging efficiency
    min_soc: 0.1            # Minimum SOC (10%)
    max_soc: 0.95           # Maximum SOC (95%)
    
    # Ancillary service configuration (currently disabled to ensure storage constraint correctness)
    ancillary_services:
      frequency_regulation:
        max_capacity_mw: 20     # Maximum frequency regulation capacity
        up_price_yuan_mw: 80     # Up regulation price
        down_price_yuan_mw: 70   # Down regulation price
        enable: true             # Enable frequency regulation

# Adjustable load configuration
adjustable_loads:
  chiller:
    rated_power_mw: 20       # Chiller rated power
    operating_cost_yuan_mwh: 50  # Operating cost
  heat_pump:
    rated_power_mw: 15       # Heat pump rated power
    operating_cost_yuan_mwh: 40  # Operating cost
```

**Solver Configuration** (`config/solver_config.yaml`):
```yaml
cbc_options:
  threads: 4               # Number of threads
  timeLimit: 300           # Solving time limit (seconds)
  ratioGap: 0.01          # Optimality gap (1%)
```

## 📊 Main Components

### 1. Generation Resources ⚡

#### Renewable Energy
- **Photovoltaic**: 50MW capacity, daytime generation, cost 5 yuan/MWh
- **Wind Power**: 30MW capacity, 24/7 operation, cost 8 yuan/MWh

#### Conventional Generation
- **Gas Turbine**: 100MW capacity, minimum output 30%, cost 600 yuan/MWh

### 2. Energy Storage System 🔋

#### Physical Characteristics
- **Power Capacity**: 10MW (charge/discharge)
- **Energy Capacity**: 40MWh (4-hour storage)
- **Charging Efficiency**: 95%
- **Discharging Efficiency**: 93%
- **Round-trip Efficiency**: 88.35% (95% × 93%)
- **Self-discharge Rate**: 0.05%/hour
- **SOC Operating Range**: 10%-95%

#### Modeling Features ✨
- **Separated Modeling**: Converter + GenericStorage architecture ensuring physical constraints
- **Charge/Discharge Exclusivity**: Energy storage as a single physical entity, strictly ensuring charge and discharge cannot occur simultaneously
- **Power Constraints**: Strict limitation of charge/discharge power to rated capacity through separated Converters
- **Economic Dispatch**: Intelligent arbitrage based on electricity price differences for cost minimization or profit maximization
- **Energy Constraints**: Daily charging total limited to 80MWh (2× energy capacity)
- **Response Speed**: Millisecond-level fast response suitable for ancillary service participation

#### Technical Innovation
- **Constraint Guarantee**: Solves traditional GenericStorage constraint failure issues
- **Physical Modeling**: Truly reflects physical operating characteristics of energy storage stations
- **Economic Optimization**: Charges during low electricity prices, discharges during high prices for maximum economic benefits

### 3. Adjustable Loads 🏭

#### Chiller System
- **Rated Power**: 20MW
- **Adjustment Range**: 30%-100%
- **Cooling Efficiency**: 85%
- **Response Time**: 5 minutes
- **Operating Cost**: 50 yuan/MWh

#### Heat Pump System
- **Rated Power**: 15MW  
- **Adjustment Range**: 20%-100%
- **Heating Coefficient**: COP=3.5
- **Response Time**: 3 minutes
- **Operating Cost**: 40 yuan/MWh

### 4. Grid Interaction 🏗️
- **Maximum Purchase**: 1000MW
- **Maximum Sale**: 500MW
- **Sale Price**: 95% market price
- **Bidirectional Regulation**: Support for flexible purchase/sale switching

## 🎯 Optimization Objectives & Constraints

### Optimization Objectives

The system supports two optimization objectives that users can choose based on actual needs:

#### 1. Cost Minimization
Aims to **minimize total operating costs**, comprehensively optimizing:
```
min: Generation Cost + Storage Cost + Adjustable Load Cost + Grid Trading Cost - Sale Revenue - Ancillary Service Revenue
```

#### 2. Profit Maximization  
Aims to **maximize total profit**, equivalent to the negative of cost minimization:
```
max: Sale Revenue + Ancillary Service Revenue - Generation Cost - Storage Cost - Adjustable Load Cost - Grid Trading Cost
```

> 💡 **Tip**: Both objectives are mathematically equivalent, but profit maximization mode more intuitively reflects VPP profitability, especially suitable for electricity market trading scenarios.

### Main Constraints

#### System-level Constraints
1. **Power Balance Constraint**: Real-time supply-demand balance
2. **Equipment Capacity Constraint**: All equipment operates within rated ranges
3. **Grid Trading Limits**: Purchase/sale power limits

#### Energy Storage System Constraints 🔋
4. **Storage Power Constraint**: Charge/discharge power strictly limited to 10MW
5. **Storage SOC Constraint**: State of charge limited to 10%-95% range
6. **Charge/Discharge Exclusivity Constraint**: Storage cannot charge and discharge simultaneously (physical constraint)
7. **Energy Constraint**: Daily charging total not exceeding 80MWh (2× storage capacity)
8. **Storage Efficiency Constraint**: Considering charge/discharge efficiency and self-discharge losses

#### Other Equipment Constraints
9. **Unit Ramping Constraint**: Gas turbine minimum output constraint
10. **Adjustable Load Constraint**: Chiller/heat pump adjustment range constraints
11. **Ancillary Service Constraint**: Storage capacity reservation and ancillary service exclusivity constraints

> ✨ **Technical Feature**: Through separated modeling architecture, the system can strictly enforce physical constraints of energy storage, ensuring the practical executability of scheduling results.

### 📚 Detailed Mathematical Modeling
> 📖 **Complete Optimization Modeling Documentation**: [Optimization Modeling](docs/optimization_modeling.md)
>
> Includes detailed mathematical formulas and modeling methods for objective functions, constraints, decision variables, etc.

## 📊 Output Results

The system generates detailed analysis reports in the `outputs/` directory:

### Single Mode Analysis Results
```
outputs/{mode}_{objective}_{timestamp}/
├── optimization_results.csv      # Detailed optimization results
├── economics_analysis.csv        # Economic analysis
├── technical_metrics.csv         # Technical metrics statistics
├── summary_report.txt            # Operation summary report
└── optimization_results.png      # Visualization charts
```

### Multi-mode Comparison Analysis Results
```
outputs/
├── modes_comparison_{objective}_{timestamp}.txt    # Mode comparison report
└── {mode}_{objective}_{timestamp}/                 # Detailed results for each mode
    ├── optimization_results.csv
    ├── economics_analysis.csv
    ├── technical_metrics.csv
    ├── summary_report.txt
    └── optimization_results.png
```

### Scheduling Strategy Output
- ⚡ **Generation Plan**: PV, wind, gas turbine output for each time period
- 🔋 **Storage Strategy**: Charge/discharge power and SOC changes
- 🏭 **Load Regulation**: Chiller, heat pump power regulation strategy
- 🔌 **Grid Trading**: Purchase/sale plan and trading volume

### Analysis Reports
- 📊 **Economic Analysis**: Cost structure, revenue analysis, investment returns
- 📈 **Technical Indicators**: Renewable penetration, self-sufficiency ratio, equipment utilization
- 📋 **Operation Report**: Detailed system operation summary and recommendations

### Visualization Charts
- 📉 **Generation Resource Output Curves**
- ⚖️ **Load and Supply Balance Chart**
- 🔋 **Energy Storage Charge/Discharge Strategy Chart**
- 🏭 **Adjustable Load Operation Status Chart**
- 💰 **Electricity Price Changes and Cost Structure Chart**

## 📊 Typical Operation Results

Based on 24-hour optimization scheduling typical results:

### Energy Supply-Demand Structure
- **Total Load Demand**: 1,259.8 MWh
- **Renewable Energy Generation**: 665.8 MWh (49.1% penetration)
- **Adjustable Load Participation**: 207.0 MWh (16.4% participation)
- **Ancillary Service Capacity**: 33.5 MW (67.1% participation)
- **Self-sufficiency Ratio**: 100%

### Economic Indicators

#### Cost Minimization Mode
- **Net Operating Cost**: 109,805 yuan
- **Ancillary Service Revenue**: 49,450 yuan
- **Average Power Supply Cost**: 87.16 yuan/MWh
- **Ancillary Service Revenue Ratio**: 13.7%
- **Annualized Operating Cost**: ~40 million yuan

#### Profit Maximization Mode
- **Net Operating Cost**: -14,121 to 122,933 yuan/day (negative indicates profit)
- **Average Electricity Cost**: -224 to 1,952 yuan/MWh
- **Optimal Mode**: renewable_storage (renewable energy + storage)
- **Profitability Ranking**: renewable_storage > storage_only > traditional > adjustable_storage > full_system > no_renewable

### Technical Indicators
- **Renewable Energy Utilization**: Efficient absorption
- **Ancillary Service Capability**: Down regulation 19.2MW, down reserve 14.4MW
- **Load Response Capability**: 35MW adjustable capacity
- **Grid Trading Balance**: Net electricity sale 672MWh

### Mode Comparison Insights
- **Renewable Energy + Storage**: Achieves profitability through electricity sales and storage arbitrage
- **Pure Storage Mode**: Mainly profits through electricity price arbitrage
- **Traditional Mode**: Higher gas generation costs, limited profitability
- **No Renewable Energy**: Highest costs, worst economics

### 📊 Key Technical Indicators

Through visualization results, you can clearly see:
- **🌞 Photovoltaic Generation**: Efficient daytime generation, peak reaching rated capacity
- **💨 Wind Generation**: 24/7 stable output providing basic power supply
- **⚡ Gas Turbine**: Flexible regulation, timely supplementation when renewable energy insufficient
- **🔋 Energy Storage**: Peak shaving and valley filling, optimizing power supply-demand matching
- **🏭 Adjustable Loads**: Intelligent participation of chillers and heat pumps in demand response
- **🔌 Grid Interaction**: Bidirectional power flow achieving economically optimized operation

> 💡 **Tip**: Chart data is based on real optimization algorithm calculation results, reflecting VPP scheduling strategies and economic benefits in actual operation.

## 🔍 Use Cases

### Applicable Fields
- 🏭 **Industrial Parks**: Multi-energy coordinated scheduling and cost optimization, achieving park energy system profitability through profit maximization mode
- 🏢 **Commercial Complexes**: Combined cooling, heating, and power system optimization supporting dual objectives
- 🌆 **Smart Cities**: Regional energy management and demand response, optimizing urban energy economic benefits
- ⚡ **Electricity Markets**: VPP aggregated resource participation in market trading, ancillary service market bidding strategies
- 🔬 **Research Institutes**: Energy system optimization algorithm research, multi-objective optimization modeling validation

### Typical Users
- **VPP Operators**: Develop optimal scheduling strategies, choose cost minimization or profit maximization objectives
- **Energy Management System Developers**: Algorithm validation and system integration, multi-objective optimization development
- **Electricity Market Participants**: Trading strategy development and risk assessment, maximizing electricity sales revenue
- **Industrial Users**: Energy cost control and demand-side management, participating in ancillary services through adjustable loads for revenue

## 🛠️ Development Guide

### Extending New Adjustable Resources

1. **Configuration File Extension**:
```yaml
# config/system_config.yaml
adjustable_loads:
  new_device:
    rated_power_mw: 10
    operating_cost_yuan_mwh: 30
```

2. **Model Component Addition**:
```python
# src/models/vpp_model.py
def _create_adjustable_loads(self):
    # Add modeling logic for new device
    new_device = solph.components.Sink(...)
```

3. **Result Analysis Update**:
```python
# src/analysis/result_analyzer.py
# Add result extraction and analysis for new device
```

### Custom Optimization Objectives

Different optimization objectives can be implemented by modifying the oemof-solph model:
- Carbon emission minimization
- Renewable energy utilization maximization
- Peak-valley difference minimization
- Multi-objective trade-off optimization

## ⚠️ Notes

### System Requirements
- **Operating System**: Windows 10+, Linux, macOS
- **Python Version**: 3.12 or higher
- **Memory**: Recommended 8GB or more
- **Processor**: Multi-core processor supporting parallel computing

### Solver Configuration
- CBC solver included in project (`cbc/bin/cbc.exe`)
- Commercial solvers recommended for large-scale problems (Gurobi, CPLEX)
- Solving time adjustable through configuration files

### Performance Optimization Suggestions
- Appropriately adjust number of time periods and model complexity
- Use multi-threading for improved performance
- Monitor memory usage to avoid insufficient memory

## 🐛 Troubleshooting

### Common Issues

**1. CBC Solver Not Found**
```bash
# Check CBC path
ls cbc/bin/cbc.exe

# Reinstall dependencies
uv pip install -e .
```

**2. Solving Failure**
- Check data validity
- Adjust solver parameters
- Check log files `logs/solver.log`

**3. Energy Storage Constraint Anomalies**
```bash
# Check if energy storage modeling is correct
python -c "
import pandas as pd
df = pd.read_csv('outputs/storage_only_*/results/optimization_results.csv')
charge_power = abs(df['battery_charge_mw'])
discharge_power = df['battery_discharge_mw']
print(f'Max charging power: {charge_power.max():.1f} MW')
print(f'Max discharging power: {discharge_power.max():.1f} MW')
# Check charge/discharge exclusivity
simultaneous = ((charge_power > 0.001) & (discharge_power > 0.001)).sum()
print(f'Simultaneous charge/discharge periods: {simultaneous}')
"
```
- If power exceeds limits or simultaneous charge/discharge occurs, energy storage modeling needs repair
- Ensure use of separated modeling architecture (Converter + GenericStorage)
- Check if result analyzer correctly identifies energy storage components

**4. Insufficient Memory**
- Reduce optimization time periods
- Simplify model constraints
- Increase virtual memory

## 🏆 Technical Highlight: Energy Storage Modeling Innovation

### Problem & Challenge
Traditional oemof-solph GenericStorage modeling may encounter in complex scenarios:
- Power constraint failure (charge/discharge power exceeding rated values)
- Simultaneous charge/discharge (violating physical laws)
- SOC constraint failure (state of charge exceeding reasonable ranges)

### Innovative Solution
This project innovatively adopts **Separated Energy Storage Modeling Architecture**:

#### Architecture Design
```
Grid Bus ←→ Converter (Charger) ←→ Storage Internal Bus ←→ GenericStorage (Storage Tank)
                                    ↕
                               Converter (Discharger) ←→ Grid Bus
```

#### Technical Advantages
1. **Physical Constraint Guarantee**: Converter's nominal_value strictly limits power
2. **Charge/Discharge Exclusivity**: Different physical paths naturally ensure exclusivity
3. **Economic Dispatch**: Storage intelligently participates in electricity price arbitrage for maximum economic benefits
4. **Reliable Results**: Scheduling results completely comply with physical operating characteristics of energy storage stations

#### Validation Results
- ✅ Charge/Discharge Exclusivity: 0 simultaneous charge/discharge periods
- ✅ Power Constraints: Charge/discharge power ≤10MW
- ✅ Energy Constraints: Daily charging ≤80MWh 
- ✅ Economic Benefits: Storage participates in arbitrage generating positive revenue

> 🏆 **Technical Achievement**: This project solves energy storage system modeling challenges in the oemof-solph framework, providing a reliable technical solution for VPP energy storage scheduling.

## 📝 License

MIT License - See [LICENSE](LICENSE) file for details