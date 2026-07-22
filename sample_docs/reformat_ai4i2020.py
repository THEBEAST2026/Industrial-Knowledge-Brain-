"""
Converts the AI4I2020 predictive maintenance dataset (raw sensor telemetry)
into work-order style rows matching the Industrial Knowledge Brain schema —
so it can flow through the same table_parser.py / entity_extractor.py path
as maintenance_worklog.csv, and share equipment tags for cross-document
entity resolution testing in Neo4j.
"""
import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(7)

df = pd.read_csv("/home/claude/sample_docs/ai 2020.csv")
print(f"Loaded {len(df)} raw sensor rows")

# Only keep rows flagged as failures or a sample of normal rows — 10k rows is
# too much for a hackathon demo corpus; we want a realistic, reviewable subset.
failures = df[df["Machine failure"] == 1]
normal_sample = df[df["Machine failure"] == 0].sample(n=60, random_state=7)
subset = pd.concat([failures, normal_sample]).sample(frac=1, random_state=7).reset_index(drop=True)
print(f"Using subset of {len(subset)} rows ({len(failures)} failures + 60 normal)")

# Reuse the SAME equipment tags as maintenance_worklog.csv so entities can
# resolve across both documents in the knowledge graph.
equipment_pool = ["PUMP-04A", "PUMP-04B", "TK-102", "TK-103", "COMPRESSOR-C1",
                   "VALVE-HW-12", "HEAT-EXCH-E7", "TURBINE-T2", "TANK-FRW-01", "PIPELINE-PL-9"]
personnel = ["R. Nair", "S. Chavan", "A. Sahay", "T. Rahangdale", "M. Iyer",
             "K. Deshpande", "J. Rao", "P. Verma"]

failure_type_map = {
    "TWF": "Tool wear failure",
    "HDF": "Heat dissipation failure",
    "PWF": "Power failure",
    "OSF": "Overstrain failure",
    "RNF": "Random failure (no clear root cause)"
}

def random_date(start_days_ago=365, end_days_ago=0):
    days = random.randint(end_days_ago, start_days_ago)
    return (datetime(2026, 7, 12) - timedelta(days=days)).strftime("%Y-%m-%d")

rows = []
for i, r in subset.iterrows():
    eq = random.choice(equipment_pool)
    fault_types_present = [name for code, name in failure_type_map.items() if r[code] == 1]
    fault_desc = "; ".join(fault_types_present) if fault_types_present else "No fault — routine sensor log"
    permit_id = f"CS-{4100+i}" if random.random() < 0.3 else ""
    rows.append({
        "work_order_id": f"WO-{2000+i}",
        "equipment_tag": eq,
        "product_id_ref": r["Product ID"],
        "work_type": "Corrective" if r["Machine failure"] == 1 else "Routine Monitoring",
        "fault_description": fault_desc,
        "air_temperature_k": r["Air temperature [K]"],
        "process_temperature_k": r["Process temperature [K]"],
        "rotational_speed_rpm": r["Rotational speed [rpm]"],
        "torque_nm": r["Torque [Nm]"],
        "tool_wear_min": r["Tool wear [min]"],
        "permit_ref": permit_id,
        "assigned_engineer": random.choice(personnel),
        "date_reported": random_date(365, 30),
        "status": "Completed" if r["Machine failure"] == 1 else "Logged",
    })

out_df = pd.DataFrame(rows)
out_path = "/home/claude/sample_docs/ai4i2020_worklog_reformatted.csv"
out_df.to_csv(out_path, index=False)
print(f"Wrote {len(out_df)} reformatted rows -> {out_path}")
print(f"Failures included: {out_df['work_type'].value_counts().to_dict()}")
