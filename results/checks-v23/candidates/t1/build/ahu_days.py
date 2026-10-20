"""Deterministic AHU demand for hidden and fresh days, keyed by local half-hour."""
from pathlib import Path
from datetime import datetime, timezone
import csv

TASK = Path(__file__).resolve().parent.parent/'task'


def add_ahu(folder):
    reheat = [float(r['ahu_heat_kw']) for r in csv.DictReader(open(TASK/'environment/data/demand.csv'))]
    p = folder/'demand.csv'
    rows = list(csv.DictReader(open(p)))
    wx = {datetime.fromisoformat(r['time_utc'].replace('Z', '+00:00')): r
          for r in csv.DictReader(open(folder/'weather.csv'))}
    fields = list(rows[0])
    if 'ahu_heat_kw' not in fields:
        fields.insert(fields.index('heat_kw')+1, 'ahu_heat_kw')
    for row in rows:
        start = datetime.fromisoformat(row['period_start'])
        t = start.hour*2 + start.minute//30
        dry = float(wx[start.astimezone(timezone.utc)]['dry_bulb_c'])
        row['ahu_heat_kw'] = f'{reheat[t] + max(0.0, 25.0*(14.0-dry)):.3f}'
    with p.open('w', newline='') as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(rows)
