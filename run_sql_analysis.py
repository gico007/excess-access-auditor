"""
run_sql_analysis.py
Creates a view joining memberships to employees and groups with the
derived level gap, tenure, and approver presence, then runs every query
in detect_excess_access.sql and prints the results.

The logic here mirrors detect_excess_access.py. Both implementations are
cross-checked against each other in the README.
"""
import sqlite3

DB_PATH = "access.db"
SQL_PATH = "detect_excess_access.sql"
TODAY = "2026-09-16"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript(f"""
DROP VIEW IF EXISTS v_access;
CREATE VIEW v_access AS
SELECT
    m.membership_id,
    m.employee_id,
    e.name,
    e.department,
    e.job_level,
    e.level_rank,
    m.group_name,
    g.dept AS group_dept,
    g.min_level,
    g.sensitive,
    m.granted_date,
    m.approver,
    (g.min_level - e.level_rank) AS level_gap,
    CAST(julianday('{TODAY}') - julianday(m.granted_date) AS INTEGER) AS days_held
FROM group_memberships m
JOIN employees e ON e.employee_id = m.employee_id
JOIN ad_groups g ON g.group_name = m.group_name;
""")


def load_queries(path):
    with open(path) as f:
        content = f.read()
    # Split on blank lines rather than semicolons - a semicolon can appear
    # inside a comment and break a naive split.
    blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
    return blocks[1:]  # blocks[0] is the file header comment


def label_for(block):
    # First comment line is the numbered query title.
    lines = [l.strip() for l in block.splitlines() if l.strip().startswith("--")]
    return lines[0].lstrip("-").strip() if lines else "(query)"


print("SQL EXCESS ACCESS DETECTION RESULTS")
print("=" * 60)

for block in load_queries(SQL_PATH):
    label = label_for(block)
    stmt_lines = [l for l in block.splitlines() if not l.strip().startswith("--")]
    stmt = "\n".join(stmt_lines).strip().rstrip(";")
    if not stmt:
        continue
    cur.execute(stmt)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(f"\n{label}")
    print("-" * len(label))
    print(f"Rows returned: {len(rows)}")
    if rows:
        print("Columns:", ", ".join(cols))
        for r in rows[:5]:
            print("  ", r)
        if len(rows) > 5:
            print(f"   ... and {len(rows) - 5} more")

conn.close()
