-- detect_excess_access.sql
-- The same five checks expressed as standalone SQL. Blocks are separated
-- by blank lines, which is what run_sql_analysis.py uses to tell one
-- query from the next.
--
-- A view named v_access is created by run_sql_analysis.py before these
-- run. It joins memberships to employees and groups and derives the
-- level gap, tenure, and approver presence so each query stays readable.

-- 1. Level mismatch. Someone holds a group that normally requires a
--    higher job level than they hold. The core case this tool exists for.
SELECT name, job_level, level_rank, group_name, min_level, level_gap, sensitive
FROM v_access
WHERE level_gap > 0
ORDER BY level_gap DESC, sensitive DESC;

-- 2. Individual contributors holding manager-level or above access. The
--    narrowest, highest-signal cut of the level mismatch check.
SELECT name, job_level, department, group_name, min_level
FROM v_access
WHERE level_rank <= 3 AND min_level >= 5
ORDER BY min_level - level_rank DESC;

-- 3. Cross-department sensitive access. A sensitive group belonging to a
--    department the person does not sit in.
SELECT name, department AS employee_dept, group_dept, group_name
FROM v_access
WHERE sensitive = 'true' AND department != group_dept
ORDER BY name;

-- 4. Sensitive group membership with no approver recorded. An
--    undocumented grant is not an approved one.
SELECT name, job_level, group_name, granted_date
FROM v_access
WHERE sensitive = 'true' AND TRIM(COALESCE(approver, '')) = ''
ORDER BY granted_date;

-- 5. Stale sensitive access: held over a year without re-review.
SELECT name, job_level, group_name, granted_date, days_held
FROM v_access
WHERE sensitive = 'true' AND days_held > 365
ORDER BY days_held DESC;

-- 6. Privilege concentration. Counted per person rather than per grant:
--    several individually defensible grants can still add up to a
--    concentration nobody intended.
SELECT name, job_level, COUNT(*) AS sensitive_groups_held,
       GROUP_CONCAT(group_name, ', ') AS groups_held
FROM v_access
WHERE sensitive = 'true' AND level_rank < 5
GROUP BY employee_id, name, job_level
HAVING COUNT(*) >= 3
ORDER BY sensitive_groups_held DESC;
