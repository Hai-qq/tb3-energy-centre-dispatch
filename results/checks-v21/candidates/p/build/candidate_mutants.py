"""Add the candidate mutation without changing the shared tool."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tools"))
import energy_mutants as M
M.MUTANTS['lt_pump_outage_ignored'] = [('planner/plant.py', 'for item in c["to"] + ([c["pump"]] if "pump" in c else []))', 'for item in c["to"])')]
if len(sys.argv) == 1:
    sys.argv.append('lt_pump_outage_ignored')
M.main()
