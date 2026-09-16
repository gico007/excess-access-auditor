"""
detect_excess_access.py
Finds access that is disproportionate to the person who holds it.

Most access review tooling answers "who has access to what". The harder
question is "does this person's access match their actual role" - an
individual contributor sitting in a group that exists to give managers
approval authority is a real finding, even though every individual grant
looks legitimate in isolation.

Five checks:

1. LEVEL_MISMATCH        - job level below the group's required level.
2. CROSS_DEPT_SENSITIVE  - sensitive group belonging to another department.
3. MISSING_APPROVER      - sensitive group membership with no approver on record.
4. STALE_MEMBERSHIP      - sensitive access granted long ago and never re-reviewed.
5. PRIVILEGE_CONCENTRATION - one person holding an unusual number of
                             sensitive groups relative to their level.

Severity reflects the size of the gap, not just the rule that fired. An
IC two or more levels below a sensitive group is Critical; one level
below a non-sensitive group is Low.
"""
import pandas as pd
from datetime import date

TODAY = pd.Timestamp(date(2026, 9, 16))
STALE_DAYS = 365
CONCENTRATION_THRESHOLD = 3  # sensitive groups held by a sub-manager IC

SEVERITY_ORDER = ["Critical", "High", "Medium", "Low"]
FINDING_COLUMNS = ["employee_id", "name", "job_level", "department", "group_name",
                   "rule", "detail", "severity"]

employees = pd.read_csv("employees.csv", dtype=str)
groups = pd.read_csv("ad_groups.csv", dtype=str)
memberships = pd.read_csv("group_memberships.csv", dtype=str)

employees["level_rank"] = employees["level_rank"].astype(int)
groups["min_level"] = groups["min_level"].astype(int)

df = (memberships
      .merge(employees, on="employee_id")
      .merge(groups.rename(columns={"dept": "group_dept"}), on="group_name"))
df["granted_date"] = pd.to_datetime(df["granted_date"])
df["days_held"] = (TODAY - df["granted_date"]).dt.days
# Read robustly: depending on dtype handling, this column can arrive as
# the string "true" or as a real boolean. Normalise both to a boolean.
df["is_sensitive"] = df["sensitive"].astype(str).str.strip().str.lower() == "true"
df["level_gap"] = df["min_level"] - df["level_rank"]
df["has_approver"] = df["approver"].fillna("").str.strip() != ""

findings = []


def flag(row, rule, detail, severity):
    findings.append({
        "employee_id": row["employee_id"], "name": row["name"],
        "job_level": row["job_level"], "department": row["department"],
        "group_name": row["group_name"], "rule": rule,
        "detail": detail, "severity": severity,
    })


# --- 1. Level mismatch ---
# Severity scales with how far below the bar the person sits, and whether
# the group is sensitive. A two-level gap into a sensitive group means an
# IC holds authority the org reserves for managers.
for _, r in df[df["level_gap"] > 0].iterrows():
    gap = r["level_gap"]
    if r["is_sensitive"] and gap >= 2:
        sev = "Critical"
    elif r["is_sensitive"]:
        sev = "High"
    elif gap >= 2:
        sev = "Medium"
    else:
        sev = "Low"
    flag(r, "LEVEL_MISMATCH",
         f"{r['job_level']} (level {r['level_rank']}) holds '{r['group_name']}', "
         f"which normally requires level {r['min_level']} - a {gap}-level gap",
         sev)

# --- 2. Cross-department sensitive access ---
for _, r in df[(df["department"] != df["group_dept"]) & df["is_sensitive"]].iterrows():
    flag(r, "CROSS_DEPT_SENSITIVE",
         f"{r['department']} employee holds '{r['group_name']}', a sensitive "
         f"{r['group_dept']} group",
         "High")

# --- 3. Missing approver on sensitive access ---
for _, r in df[df["is_sensitive"] & ~df["has_approver"]].iterrows():
    flag(r, "MISSING_APPROVER",
         f"Sensitive group '{r['group_name']}' has no approver on record",
         "Medium")

# --- 4. Stale sensitive membership ---
for _, r in df[df["is_sensitive"] & (df["days_held"] > STALE_DAYS)].iterrows():
    flag(r, "STALE_MEMBERSHIP",
         f"Sensitive access held {r['days_held']} days without re-review "
         f"(threshold {STALE_DAYS})",
         "Medium")

# --- 5. Privilege concentration ---
# Counted per person rather than per grant: several individually
# defensible grants can still add up to a concentration nobody intended.
sens_counts = df[df["is_sensitive"]].groupby("employee_id").size()
for emp_id, count in sens_counts.items():
    emp = employees[employees["employee_id"] == emp_id].iloc[0]
    if count >= CONCENTRATION_THRESHOLD and emp["level_rank"] < 5:
        held = sorted(df[(df["employee_id"] == emp_id) & df["is_sensitive"]]["group_name"].unique())
        findings.append({
            "employee_id": emp_id, "name": emp["name"], "job_level": emp["job_level"],
            "department": emp["department"], "group_name": ", ".join(held),
            "rule": "PRIVILEGE_CONCENTRATION",
            "detail": f"{emp['job_level']} holds {count} sensitive groups: {', '.join(held)}",
            "severity": "High",
        })

# --- Build findings queue ---
fdf = pd.DataFrame(findings, columns=FINDING_COLUMNS)
if not fdf.empty:
    fdf["severity"] = pd.Categorical(fdf["severity"], categories=SEVERITY_ORDER, ordered=True)
    fdf = fdf.sort_values(["severity", "rule", "employee_id"])
fdf.to_csv("excess_access_findings.csv", index=False)

# --- Summary ---
lines = []
lines.append("EXCESS ACCESS DETECTION SUMMARY")
lines.append("=" * 46)
lines.append(f"Employees reviewed:              {len(employees)}")
lines.append(f"AD groups in scope:              {len(groups)}  ({groups['sensitive'].eq('true').sum()} sensitive)")
lines.append(f"Group memberships reviewed:      {len(memberships)}")
lines.append(f"Total findings:                  {len(fdf)}")
lines.append(f"Employees with a finding:        {fdf['employee_id'].nunique() if not fdf.empty else 0}")
lines.append("")

lines.append("Findings by rule:")
if not fdf.empty:
    for rule, n in fdf.groupby("rule", observed=True).size().sort_values(ascending=False).items():
        lines.append(f"  {rule:<26} {n:>4}")
lines.append("")

lines.append("Findings by severity:")
if not fdf.empty:
    by_sev = fdf.groupby("severity", observed=True).size().reindex(SEVERITY_ORDER).fillna(0).astype(int)
    for sev, n in by_sev.items():
        lines.append(f"  {sev:<26} {n:>4}")
lines.append("")

# The headline number: ICs holding manager-or-above access.
ic_on_mgr = df[(df["level_rank"] <= 3) & (df["min_level"] >= 5)]
lines.append(f"Individual contributors holding manager-level or above access: "
             f"{ic_on_mgr['employee_id'].nunique()} people, {len(ic_on_mgr)} memberships")
lines.append("")

lines.append("Sample - widest level gaps:")
widest = df[df["level_gap"] > 0].sort_values("level_gap", ascending=False).head(5)
for _, r in widest.iterrows():
    lines.append(f"  {r['name']:<20} {r['job_level']:<16} -> {r['group_name']:<26} "
                 f"(gap {r['level_gap']})")

summary = "\n".join(lines)
with open("summary_report.txt", "w") as f:
    f.write(summary)
print(summary)
