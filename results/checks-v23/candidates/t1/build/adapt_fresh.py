"""Create a candidate-local fresh-day adapter without editing shared tools."""
from pathlib import Path
import difflib

B = Path(__file__).resolve().parent
ROOT = B.parents[4]
original = (ROOT/'tools/fresh_days.py').read_text()
s = original
changes = [
    ('ROOT = Path(__file__).resolve().parents[1]', 'ROOT = Path(__file__).resolve().parents[5]'),
    ('from reference import Day  # noqa: E402', 'from reference import Day  # noqa: E402\nfrom ahu_days import add_ahu'),
    ('"GE2 jacket water and exhaust"]', '"GE2 jacket water and exhaust", "LT PHE 1", "LT PHE 2"]'),
    ('    return problems', '''    if not problems:
        try:
            Day(folder)  # certifies every radiator-outage period before feasibility
        except AssertionError as exc:
            problems.append(str(exc))
    return problems'''),
    ('        B.write_day(folder, spec)', '        B.write_day(folder, spec)\n        add_ahu(folder)'),
]
for old, new in changes:
    assert s.count(old) == 1, old
    s = s.replace(old, new)
(B/'fresh_days.py').write_text(s)
(B/'fresh_days.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True), s.splitlines(True), fromfile='tools/fresh_days.py', tofile='build/fresh_days.py')))
