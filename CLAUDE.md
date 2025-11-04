# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Virtual Power Plant (VPP) Optimization System built on the oemof-solph framework with CBC solver for linear programming optimization. The system provides intelligent energy resource scheduling strategies for VPPs, achieving coordinated operation and cost optimization of multiple energy resources including renewable energy, conventional generation, energy storage systems, adjustable loads, and grid interaction.

## Key Commands

### Development Setup
```bash
# Install dependencies (recommended with uv)
uv pip install -e .

# Or use pip
pip install -e .
```

### Running the System
```bash
# Interactive mode (recommended for selecting optimization objectives and scheduling modes)
python main.py

# Demo mode - complete VPP optimization demo
python main.py --demo

# Specific scheduling mode
python main.py --mode=full_system

# Compare all scheduling modes
python main.py --compare-all

# List available modes
python main.py --list-modes
```

### Testing
```bash
# Run all tests
python tests/run_tests.py

# Run specific test categories
python tests/run_tests.py --type basic        # Basic functionality tests
python tests/run_tests.py --type cbc          # CBC solver tests
python tests/run_tests.py --type scheduling   # Scheduling mode tests
python tests/run_tests.py --type objectives   # Optimization objective tests
python tests/run_tests.py --type loads        # Adjustable load tests
python tests/run_tests.py --type ancillary    # Ancillary service tests
python tests/run_tests.py --type flow         # Complete flow tests

# Run unit tests directly
python tests/test_vpp_system.py
```

## Architecture Overview

### Core Module Structure (`src/`)
- **data/**: Data generation module for load, PV, wind, and price data
- **models/**: Optimization modeling using oemof-solph framework
  - `vpp_model.py`: Core energy system modeling with separated storage architecture
  - `scheduling_modes.py`: Six scheduling modes management
- **solvers/**: CBC solver configuration and optimization execution
- **analysis/**: Economic and performance analysis with ancillary service assessment
- **visualization/**: Chart generation and reporting with automatic component detection
- **utils/**: File management, session context, and logging configuration

### Key Technical Innovations
1. **Separated Energy Storage Modeling**: Converter + GenericStorage architecture ensuring physical constraints (charge/discharge exclusivity, power limits)
2. **Six Scheduling Modes**: renewable_storage, adjustable_storage, traditional, no_renewable, storage_only, full_system
3. **Multi-objective Optimization**: Cost minimization and profit maximization
4. **Ancillary Services**: Energy storage participation in frequency regulation and spinning reserve
5. **Adjustable Loads**: Chiller and heat pump demand response capabilities

### Configuration Files
- `config/system_config.yaml`: System parameters, resource capacities, costs, ancillary service settings
- `config/solver_config.yaml`: CBC solver settings (threads, time limits, gaps)

### Output Structure
Results are organized in `outputs/{mode}_{objective}_{timestamp}/` with:
- `optimization_results.csv`: Detailed scheduling results
- `economics_analysis.csv`: Economic analysis including ancillary service revenues
- `technical_metrics.csv`: Technical performance indicators
- `summary_report.txt`: Operation summary with mode-specific insights
- `optimization_results.png`: Visualization charts

## Important Technical Details

### Energy Storage Modeling
The system uses a separated modeling architecture to solve traditional GenericStorage constraint failures:
- **Architecture**: Grid Bus ↔ Converter(Charger) ↔ Storage Internal Bus ↔ GenericStorage(Storage Tank)
- **Constraints**: Strict power limits (10MW), SOC range (10%-95%), charge/discharge exclusivity
- **Validation**: Zero simultaneous charge/discharge periods, power ≤ rated capacity

### Optimization Objectives
1. **Cost Minimization**: Minimize total operating costs including generation, storage, adjustable loads, grid trading, minus revenues
2. **Profit Maximization**: Maximize total profit (sale revenue + ancillary service revenue - all costs)

### Scheduling Modes
Each mode represents different combinations of available resources:
- `renewable_storage`: PV + wind + storage (most profitable)
- `adjustable_storage`: Adjustable loads + storage
- `traditional`: All resources without ancillary services
- `no_renewable`: Conventional generation + storage + adjustable loads
- `storage_only`: Pure storage arbitrage
- `full_system`: Complete system with all resources and services

## Development Guidelines

### When Modifying Energy Storage Models
- Maintain the separated Converter + GenericStorage architecture
- Ensure charge/discharge exclusivity through physical constraint modeling
- Validate results for power limits and simultaneous operation violations

### When Adding New Resources
1. Update `config/system_config.yaml` with new resource parameters
2. Add modeling logic in `src/models/vpp_model.py`
3. Update result analysis in `src/analysis/result_analyzer.py`
4. Add corresponding tests in `tests/` directory

### When Working with Optimization Objectives
- Objectives are implemented through oemof-solph model configuration
- Both cost minimization and profit maximization use the same constraint set
- Profit maximization is mathematically equivalent to negative cost minimization

## Common Issues and Solutions

### CBC Solver Issues
- Check CBC path: `cbc/bin/cbc.exe` exists
- Verify solver configuration in `config/solver_config.yaml`
- Monitor solver logs in `logs/solver.log`

### Energy Storage Constraint Violations
- Verify separated modeling architecture is used
- Check result analyzer correctly identifies storage components
- Validate no simultaneous charge/discharge in results

### Performance Optimization
- Adjust time periods and model complexity for large problems
- Use multi-threading via solver configuration
- Monitor memory usage during optimization

## Testing Strategy

The test suite covers:
- **Basic functionality**: Core system components and data generation
- **CBC solver**: Solver configuration and execution
- **Scheduling modes**: All six modes with different resource combinations
- **Optimization objectives**: Both cost minimization and profit maximization
- **Adjustable loads**: Chiller and heat pump demand response
- **Ancillary services**: Frequency regulation and spinning reserve
- **Complete flow**: End-to-end system integration

Each test category validates specific aspects of the multi-resource coordination system.