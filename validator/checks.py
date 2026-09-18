"""Validation checks for generated synthetic data."""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    details: dict = field(default_factory=dict)


def check_row_counts(conn: sqlite3.Connection) -> CheckResult:
    required = [
        "users",
        "items",
        "relationship_edges",
        "user_item_interactions",
        "activity_sessions",
        "contributions",
        "feature_exposure_log",
        "planted_influence_rules",
    ]
    empty = []
    counts = {}
    for table in required:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        counts[table] = n
        if n == 0:
            empty.append(table)
    passed = len(empty) == 0
    msg = "All required tables populated" if passed else f"Empty tables: {', '.join(empty)}"
    return CheckResult("row_counts", passed, msg, counts)


def check_foreign_keys(conn: sqlite3.Connection) -> CheckResult:
    conn.execute("PRAGMA foreign_keys = ON")
    orphans = []
    checks = [
        ("users", "organization_id", "organizations", "organization_id"),
        ("relationship_edges", "user_id_a", "users", "user_id"),
        ("user_item_interactions", "user_id", "users", "user_id"),
        ("activity_session_participants", "session_id", "activity_sessions", "session_id"),
        ("contributions", "user_id", "users", "user_id"),
    ]
    for child, col, parent, pcol in checks:
        n = conn.execute(
            f"""
            SELECT COUNT(*) FROM {child} c
            LEFT JOIN {parent} p ON c.{col} = p.{pcol}
            WHERE p.{pcol} IS NULL
            """
        ).fetchone()[0]
        if n:
            orphans.append(f"{child}.{col}: {n}")

    passed = len(orphans) == 0
    msg = "All foreign keys resolve" if passed else "; ".join(orphans)
    return CheckResult("foreign_keys", passed, msg)


def check_timestamps(conn: sqlite3.Connection) -> CheckResult:
    violations = []

    n = conn.execute(
        """
        SELECT COUNT(*) FROM relationship_edges e
        JOIN users ua ON e.user_id_a = ua.user_id
        JOIN users ub ON e.user_id_b = ub.user_id
        WHERE e.connection_date < ua.join_date OR e.connection_date < ub.join_date
        """
    ).fetchone()[0]
    if n:
        violations.append(f"relationship_edges before join: {n}")

    n = conn.execute(
        """
        SELECT COUNT(*) FROM user_item_interactions i
        JOIN users u ON i.user_id = u.user_id
        WHERE i.interaction_date < u.join_date
        """
    ).fetchone()[0]
    if n:
        violations.append(f"interactions before join: {n}")

    n = conn.execute(
        """
        SELECT COUNT(*) FROM activity_session_participants asp
        JOIN activity_sessions s ON asp.session_id = s.session_id
        JOIN users u ON asp.user_id = u.user_id
        WHERE s.session_timestamp < u.join_date
        """
    ).fetchone()[0]
    if n:
        violations.append(f"sessions before participant join: {n}")

    passed = len(violations) == 0
    msg = "Timestamp order valid" if passed else "; ".join(violations)
    return CheckResult("timestamps", passed, msg)


def check_duplicate_undirected(conn: sqlite3.Connection) -> CheckResult:
    n = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT user_id_a, user_id_b, relationship_type, COUNT(*) c
            FROM relationship_edges
            WHERE relationship_type IN ('friend', 'collaborate')
            GROUP BY user_id_a, user_id_b, relationship_type
            HAVING c > 1
        )
        """
    ).fetchone()[0]
    passed = n == 0
    msg = "No duplicate undirected edges" if passed else f"{n} duplicate groups"
    return CheckResult("duplicate_edges", passed, msg)


def check_degree_distribution(conn: sqlite3.Connection) -> CheckResult:
    rows = conn.execute(
        """
        SELECT user_id_a AS u FROM relationship_edges
        UNION ALL
        SELECT user_id_b FROM relationship_edges WHERE relationship_type IN ('friend','collaborate','member_of')
        """
    ).fetchall()
    degrees = Counter(r[0] for r in rows)
    if not degrees:
        return CheckResult("distribution", False, "No edges for degree calculation")

    values = list(degrees.values())
    values.sort()
    median = values[len(values) // 2]
    max_deg = max(values)
    p95 = values[int(len(values) * 0.95)]
    passed = max_deg >= median * 3 and max_deg >= 10
    msg = f"median={median}, p95={p95}, max={max_deg}"
    return CheckResult("distribution", passed, msg, {"median": median, "p95": p95, "max": max_deg})


def check_config_hash(conn: sqlite3.Connection, expected_hash: str) -> CheckResult:
    row = conn.execute("SELECT config_hash FROM dataset_metadata WHERE dataset_id = 1").fetchone()
    if not row:
        return CheckResult("config_hash", False, "dataset_metadata missing")
    passed = row[0] == expected_hash
    msg = "config_hash matches" if passed else f"expected {expected_hash}, got {row[0]}"
    return CheckResult("config_hash", passed, msg)


def check_planted_rules_separate(conn: sqlite3.Connection) -> CheckResult:
    n = conn.execute("SELECT COUNT(*) FROM planted_influence_rules").fetchone()[0]
    passed = n >= 5
    msg = f"{n} planted rules stored separately"
    return CheckResult("planted_rules", passed, msg)


def distribution_snapshot(conn: sqlite3.Connection) -> str:
    deg = check_degree_distribution(conn)
    lines = [
        "\n=== Distribution snapshot ===",
        f"Degree stats: {deg.message}",
    ]
    hubs = conn.execute(
        """
        WITH deg AS (
            SELECT user_id_a u FROM relationship_edges
            UNION ALL
            SELECT user_id_b FROM relationship_edges
        )
        SELECT u, COUNT(*) c FROM deg GROUP BY u ORDER BY c DESC LIMIT 10
        """
    ).fetchall()
    lines.append("Top hub users (by edge endpoint count):")
    for user_id, count in hubs:
        lines.append(f"  {user_id}: {count}")

    comm_proxy = conn.execute(
        """
        SELECT organization_id, COUNT(*) FROM users GROUP BY organization_id ORDER BY COUNT(*) DESC LIMIT 5
        """
    ).fetchall()
    lines.append("Largest org user counts:")
    for org, count in comm_proxy:
        lines.append(f"  {org}: {count}")

    return "\n".join(lines)


def run_all_checks(conn: sqlite3.Connection, config_hash: str | None = None) -> list[CheckResult]:
    results = [
        check_row_counts(conn),
        check_foreign_keys(conn),
        check_timestamps(conn),
        check_duplicate_undirected(conn),
        check_degree_distribution(conn),
        check_planted_rules_separate(conn),
    ]
    if config_hash:
        results.append(check_config_hash(conn, config_hash))
    return results
