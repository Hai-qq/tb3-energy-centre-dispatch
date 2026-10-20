"""Add the candidate mutation without changing the shared tool."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "tools"))
import energy_mutants as M
M.MUTANTS['grid_direction_ignored'] = [('planner/optimize.py', 'directions = (True, False) if tariff.import_rate(day.starts[t]) < tariff.export_rate else (None,)', 'directions = (None,)')]
if len(sys.argv) == 1:
    sys.argv.append('grid_direction_ignored')
M.main()
