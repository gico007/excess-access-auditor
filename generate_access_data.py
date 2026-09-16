"""
generate_access_data.py
Generates a synthetic org chart and Active Directory group membership
export for an excess access detector.

All names, job levels, departments, and group memberships in this project
are fictional and randomly generated. No real organisation, employee, or
directory data is used or implied.
"""
import random
import csv
from datetime import date, timedelta

random.seed(43)

TODAY = date(2026, 9, 16)

# Job levels, lowest to highest. The numeric rank is what the detector
# compares a group's required level against.
JOB_LEVELS = [
    ("Associate", 1),
    ("Analyst", 2),
    ("Senior Analyst", 3),
    ("Lead", 4),
    ("Manager", 5),
    ("Senior Manager", 6),
    ("Director", 7),
]
LEVEL_RANK = dict(JOB_LEVELS)

DEPARTMENTS = ["Finance", "HR", "IT", "Operations", "Sales"]

FIRST = ["Jordan","Casey","Morgan","Taylor","Riley","Avery","Quinn","Reese","Rowan",
         "Sage","Dakota","Emerson","Finley","Harper","Skyler","Blair","Cameron",
         "Drew","Ellis","Hayden","Jules","Kai","Logan","Micah","Noor","Parker",
         "Remy","Shay","Tatum","Wren","Alexis","Devon","Frankie","Gray","Indigo"]
LAST = ["Chen","Patel","Nguyen","Garcia","Kim","Singh","Rossi","Muller","Kowalski",
        "Abara","Santos","Dubois","Andersen","Haddad","Costa","Okafor","Ivanov",
        "Fischer","Lindgren","Osei","Tanaka","Silva","Novak","Bauer","Moreau"]

# AD groups. min_level is the lowest job level that would normally justify
# membership. approval_required flags groups where membership is supposed
# to come with a recorded approval.
AD_GROUPS = [
    {"group_name": "FIN-Invoice-Entry",        "dept": "Finance",    "min_level": 1, "sensitive": "false"},
    {"group_name": "FIN-Payment-Release",      "dept": "Finance",    "min_level": 5, "sensitive": "true"},
    {"group_name": "FIN-GL-Close-Approve",     "dept": "Finance",    "min_level": 5, "sensitive": "true"},
    {"group_name": "FIN-Reporting-ReadOnly",   "dept": "Finance",    "min_level": 1, "sensitive": "false"},
    {"group_name": "HR-Employee-Records-Read", "dept": "HR",         "min_level": 2, "sensitive": "false"},
    {"group_name": "HR-Compensation-Admin",    "dept": "HR",         "min_level": 6, "sensitive": "true"},
    {"group_name": "HR-Termination-Process",   "dept": "HR",         "min_level": 5, "sensitive": "true"},
    {"group_name": "IT-Helpdesk-Standard",     "dept": "IT",         "min_level": 1, "sensitive": "false"},
    {"group_name": "IT-Server-Admin",          "dept": "IT",         "min_level": 4, "sensitive": "true"},
    {"group_name": "IT-Domain-Admin",          "dept": "IT",         "min_level": 6, "sensitive": "true"},
    {"group_name": "IT-Prod-Database-Write",   "dept": "IT",         "min_level": 4, "sensitive": "true"},
    {"group_name": "OPS-Workflow-Standard",    "dept": "Operations", "min_level": 1, "sensitive": "false"},
    {"group_name": "OPS-Vendor-Onboard",       "dept": "Operations", "min_level": 4, "sensitive": "true"},
    {"group_name": "SALES-CRM-Standard",       "dept": "Sales",      "min_level": 1, "sensitive": "false"},
    {"group_name": "SALES-Discount-Override",  "dept": "Sales",      "min_level": 5, "sensitive": "true"},
]

GROUP_BY_NAME = {g["group_name"]: g for g in AD_GROUPS}

with open("ad_groups.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(AD_GROUPS[0].keys()))
    w.writeheader()
    w.writerows(AD_GROUPS)

# --- Build employees ---
employees = []
used = set()
for i in range(1, 81):
    while True:
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        if name not in used:
            used.add(name)
            break
    # Most people are ICs; leadership is a minority, as in a real org.
    level_name, level_rank = random.choices(
        JOB_LEVELS, weights=[0.18, 0.26, 0.24, 0.12, 0.11, 0.06, 0.03]
    )[0]
    employees.append({
        "employee_id": f"EMP{i:04d}",
        "name": name,
        "department": random.choice(DEPARTMENTS),
        "job_level": level_name,
        "level_rank": str(level_rank),
        "hire_date": (TODAY - timedelta(days=random.randint(90, 2600))).isoformat(),
    })

with open("employees.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(employees[0].keys()))
    w.writeheader()
    w.writerows(employees)

# --- Build group memberships ---
memberships = []
mid = 1

def add(emp, group_name, granted=None, approver=""):
    global mid
    memberships.append({
        "membership_id": f"MBR{mid:05d}",
        "employee_id": emp["employee_id"],
        "group_name": group_name,
        "granted_date": (granted or (TODAY - timedelta(days=random.randint(30, 1400)))).isoformat(),
        "approver": approver,
    })
    mid += 1

for emp in employees:
    rank = int(emp["level_rank"])
    # Baseline: groups in their own department that their level justifies.
    eligible = [g for g in AD_GROUPS if g["dept"] == emp["department"] and g["min_level"] <= rank]
    for g in random.sample(eligible, min(len(eligible), random.randint(1, 3))):
        approver = f"EMP{random.randint(1, 80):04d}" if g["sensitive"] == "true" else ""
        add(emp, g["group_name"], approver=approver)

# --- Seed the findings this tool is meant to catch ---

ics = [e for e in employees if int(e["level_rank"]) <= 3]
leads = [e for e in employees if int(e["level_rank"]) == 4]

# 1. ICs holding groups that require manager level or above. The core
#    case: an individual contributor with approval authority.
sensitive_high = [g for g in AD_GROUPS if g["min_level"] >= 5]
for emp in random.sample(ics, 9):
    g = random.choice(sensitive_high)
    approver = f"EMP{random.randint(1, 80):04d}" if random.random() < 0.5 else ""
    add(emp, g["group_name"], approver=approver)

# 2. Cross-department sensitive access - someone holding a sensitive group
#    belonging to a department that is not theirs.
for emp in random.sample(employees, 7):
    other = [g for g in AD_GROUPS if g["dept"] != emp["department"] and g["sensitive"] == "true"]
    g = random.choice(other)
    approver = f"EMP{random.randint(1, 80):04d}" if random.random() < 0.4 else ""
    add(emp, g["group_name"], approver=approver)

# 3. Sensitive group membership with no recorded approver at all.
for emp in random.sample(employees, 6):
    sens = [g for g in AD_GROUPS if g["sensitive"] == "true"]
    add(emp, random.choice(sens)["group_name"], approver="")

# 4. Long-standing memberships never re-reviewed (granted years ago).
for emp in random.sample(leads + ics, 8):
    g = random.choice([g for g in AD_GROUPS if g["sensitive"] == "true"])
    add(emp, g["group_name"], granted=TODAY - timedelta(days=random.randint(1500, 2400)),
        approver=f"EMP{random.randint(1, 80):04d}")

# 5. Privilege accumulation: a few sub-manager staff who have picked up
#    several sensitive groups over time. Each grant looked reasonable on
#    its own; the accumulation is the problem.
sensitive_groups = [g for g in AD_GROUPS if g["sensitive"] == "true"]
for emp in random.sample(ics + leads, 4):
    existing = {m["group_name"] for m in memberships if m["employee_id"] == emp["employee_id"]}
    candidates = [g for g in sensitive_groups if g["group_name"] not in existing]
    for g in random.sample(candidates, min(3, len(candidates))):
        add(emp, g["group_name"], approver=f"EMP{random.randint(1, 80):04d}")

with open("group_memberships.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(memberships[0].keys()))
    w.writeheader()
    w.writerows(memberships)

print(f"Generated {len(employees)} employees -> employees.csv")
print(f"Generated {len(AD_GROUPS)} AD groups -> ad_groups.csv")
print(f"Generated {len(memberships)} group memberships -> group_memberships.csv")
