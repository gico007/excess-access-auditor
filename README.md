# Personal projects and case studies focused on solving business problems through technology, governance, data, # security, and process improvement. 

# excess-access-auditor
Finds access that is disproportionate to the person who holds it, by comparing Active Directory group membership against job level, department, approval records, and tenure. Synthetic data, built to show method.

# Excess Access Detector

Finds access that is disproportionate to the person who holds it, by
comparing Active Directory group membership against job level, department,
approval records, and tenure. Synthetic data, built to show method.

All names, job levels, departments, and group memberships in this project
are fictional and randomly generated. No real organisation, employee, or
directory data is used or implied.

## Why this exists

Most access review tooling answers "who has access to what". The harder
question is "does this person's access match their actual role".

An individual contributor sitting in a group that exists to give managers
payment-release or termination-processing authority is a real finding,
even though every individual grant looks legitimate in isolation. Nobody
maliciously handed out that access - it accumulated. Someone covered a
manager's leave, someone moved teams and kept their old entitlements,
someone was added for a project that ended two years ago.

This is the check that catches that pattern, which is the part a
permissions report alone will not tell you.

## What it does

Five checks, each producing findings with a severity that reflects the
size of the gap rather than just which rule fired:

1. **LEVEL_MISMATCH** - job level below the group's required level.
   Severity scales with the gap: a two-or-more level gap into a sensitive
   group is Critical, one level into a non-sensitive group is Low.
2. **CROSS_DEPT_SENSITIVE** - a sensitive group belonging to a department
   the person does not sit in.
3. **MISSING_APPROVER** - sensitive group membership with no approver on
   record. An undocumented grant is not an approved one.
4. **STALE_MEMBERSHIP** - sensitive access held over a year without
   re-review.
5. **PRIVILEGE_CONCENTRATION** - counted per person rather than per grant,
   because several individually defensible grants can still add up to a
   concentration nobody intended.

## Sample output

```
Employees reviewed:              80
AD groups in scope:              15  (9 sensitive)
Group memberships reviewed:      149
Total findings:                  144
Employees with a finding:        42

Findings by rule:
  STALE_MEMBERSHIP             51
  LEVEL_MISMATCH               38
  CROSS_DEPT_SENSITIVE         35
  MISSING_APPROVER             16
  PRIVILEGE_CONCENTRATION       4

Findings by severity:
  Critical                     33
  High                         44
  Medium                       67

Individual contributors holding manager-level or above access: 19 people, 23 memberships

Sample - widest level gaps:
  Morgan Kim           Associate        -> HR-Compensation-Admin      (gap 5)
  Jules Singh          Associate        -> IT-Domain-Admin            (gap 5)
  Jules Dubois         Associate        -> FIN-GL-Close-Approve       (gap 4)
```

## Sample query (ICs holding manager-level access)

```sql
SELECT name, job_level, department, group_name, min_level
FROM v_access
WHERE level_rank <= 3 AND min_level >= 5
ORDER BY min_level - level_rank DESC;
```

## Two bugs I found and fixed while building this

**A merge that assumed a column collision that never happened.** The
detection engine referenced `department_x` and `department_y`, expecting
pandas to auto-suffix two colliding `department` columns. The AD group
table names its column `dept`, so there was no collision, no suffix, and
the script failed outright with a `KeyError`. Fixed by renaming
explicitly at merge time rather than relying on assumed behaviour - the
column names are now unambiguous regardless of what the source files
happen to be called.

**A boolean that was sometimes a string.** The `sensitive` flag is written
to CSV as the text `true`/`false`, but pandas will silently convert those
into real booleans depending on how the file is read. Comparing against
the string `"true"` then matches nothing, and every sensitive-group check
quietly returns zero results rather than erroring. Found it when
privilege concentration reported no findings and the underlying count
came back as `nan` instead of a number. Fixed by normalising the column
to a real boolean on read, so it behaves the same either way.

The second one is the more interesting failure: it does not crash, it
just silently under-reports. That is the category of bug worth being
paranoid about in any control that is supposed to catch things.

## Design notes

- **Severity reflects the size of the gap, not the rule.** An Associate
  five levels below a sensitive group is a materially different finding
  from a Senior Analyst one level below a read-only group, and the output
  ranks them accordingly.
- **Concentration is measured per person, not per grant.** Each grant in
  the sample run passed its own approval. The finding only appears when
  you look at the individual rather than the individual transaction.
- **Missing approvers are a finding in their own right.** An entitlement
  nobody can point to a decision for is not a clean grant, regardless of
  whether the access itself is appropriate.
- **Python and SQL are cross-checked.** Both implementations were run
  against the same data and compared programmatically - level mismatches,
  stale memberships, and concentration counts all match exactly.

## Run it yourself

Python/pandas version:
```
pip install pandas
python3 generate_access_data.py
python3 detect_excess_access.py
```

SQL version:
```
python3 load_to_sqlite.py
python3 run_sql_analysis.py
```

## Files

- `generate_access_data.py` - synthetic org chart, AD group catalogue, and membership generator
- `detect_excess_access.py` - Python/pandas detection engine
- `load_to_sqlite.py` - loads the data into a local SQLite database
- `detect_excess_access.sql` - standalone SQL implementation of the same checks
- `run_sql_analysis.py` - builds the access view, runs the SQL, prints results
- `employees.csv`, `ad_groups.csv`, `group_memberships.csv` - generated input data
- `excess_access_findings.csv` - findings with rule, detail, and severity
- `summary_report.txt` - run summary

---
*All data in this project is synthetic and fictional, generated for
demonstration purposes.*

