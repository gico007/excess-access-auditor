"""
load_to_sqlite.py
Loads the synthetic org chart, AD group catalogue, and group memberships
into a local SQLite database so the same checks can be run as real SQL.
"""
import csv
import sqlite3

DB_PATH = "access.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS employees")
cur.execute("""CREATE TABLE employees (
    employee_id TEXT, name TEXT, department TEXT,
    job_level TEXT, level_rank INTEGER, hire_date TEXT
)""")
with open("employees.csv", newline="") as f:
    rows = [tuple(r.values()) for r in csv.DictReader(f)]
cur.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?)", rows)

cur.execute("DROP TABLE IF EXISTS ad_groups")
cur.execute("""CREATE TABLE ad_groups (
    group_name TEXT, dept TEXT, min_level INTEGER, sensitive TEXT
)""")
with open("ad_groups.csv", newline="") as f:
    rows2 = [tuple(r.values()) for r in csv.DictReader(f)]
cur.executemany("INSERT INTO ad_groups VALUES (?,?,?,?)", rows2)

cur.execute("DROP TABLE IF EXISTS group_memberships")
cur.execute("""CREATE TABLE group_memberships (
    membership_id TEXT, employee_id TEXT, group_name TEXT,
    granted_date TEXT, approver TEXT
)""")
with open("group_memberships.csv", newline="") as f:
    rows3 = [tuple(r.values()) for r in csv.DictReader(f)]
cur.executemany("INSERT INTO group_memberships VALUES (?,?,?,?,?)", rows3)

conn.commit()
print(f"Loaded {len(rows)} employees, {len(rows2)} groups, {len(rows3)} memberships into {DB_PATH}")
conn.close()
