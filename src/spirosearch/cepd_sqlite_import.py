"""Stream MySQL SQL dump into SQLite (CEPDB optimized path).

Instead of scanning the 49 GB dump repeatedly, a single streaming pass
converts ``CREATE TABLE`` statements into SQLite DDL and feeds ``INSERT``
rows through parameterized batch inserts. After the import, all HTL-window
queries run as indexed SQL against SQLite — no repeated text scans.

Line-based streaming: statements are collected line by line until a
terminating ``;`` (no large-buffer copies, no per-character scans).
"""
from __future__ import annotations

import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from spirosearch.cepd_import import _sql_unescape

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?\s*\(",
    re.IGNORECASE,
)
_INSERT_INTO_RE = re.compile(r"INSERT\s+INTO\s+`?(\w+)`?", re.IGNORECASE)

_MYSQL_TYPE_MAP = {
    "int": "INTEGER", "tinyint": "INTEGER", "smallint": "INTEGER",
    "mediumint": "INTEGER", "bigint": "INTEGER", "float": "REAL",
    "double": "REAL", "real": "REAL", "decimal": "REAL", "numeric": "REAL",
    "varchar": "TEXT", "char": "TEXT", "text": "TEXT", "tinytext": "TEXT",
    "mediumtext": "TEXT", "longtext": "TEXT", "datetime": "TEXT",
    "timestamp": "TEXT", "date": "TEXT", "time": "TEXT", "blob": "BLOB",
    "longblob": "BLOB", "varbinary": "BLOB", "binary": "BLOB", "json": "TEXT",
    "enum": "TEXT", "set": "TEXT", "year": "INTEGER", "bit": "INTEGER",
    "bool": "INTEGER", "boolean": "INTEGER", "mediumblob": "BLOB",
    "tinyblob": "BLOB",
}


def _convert_column_type(decl: str) -> str:
    """Convert one MySQL column definition to SQLite DDL text."""
    decl = decl.strip()
    match = re.match(r"`?(\w+)`?\s+([a-z]+)", decl, re.IGNORECASE)
    if not match:
        return decl
    column = match.group(1)
    base = match.group(2).casefold().split("(")[0]
    sqlite_type = _MYSQL_TYPE_MAP.get(base, "TEXT")
    body = decl[match.end():]
    body = re.sub(r"\s*UNSIGNED", "", body, flags=re.IGNORECASE)
    not_null = " NOT NULL" if re.search(r"\bNOT\s+NULL\b", body, re.IGNORECASE) else ""
    primary = " PRIMARY KEY" if re.search(r"\bPRIMARY\s+KEY\b", body, re.IGNORECASE) else ""
    return f"{column} {sqlite_type}{not_null}{primary}"


def _matching_parenthesis_body(text: str, open_index: int) -> str | None:
    """Return the text between the parenthesis at ``open_index`` and its
    matching close, or None when unbalanced."""
    depth = 0
    in_string = False
    index = open_index
    while index < len(text):
        char = text[index]
        if char == "'" and not in_string:
            in_string = True
        elif char == "'" and in_string:
            if index + 1 < len(text) and text[index + 1] == "'":
                index += 1
            else:
                in_string = False
        elif char == "\\" and in_string and index + 1 < len(text):
            index += 1
        elif not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return text[open_index + 1:index]
        index += 1
    return None


def _convert_create_table(statement: str) -> tuple[str, list[str]] | None:
    """Convert a MySQL CREATE TABLE statement to SQLite DDL."""
    match = _CREATE_TABLE_RE.match(statement.strip())
    if not match:
        return None
    table = match.group(1)
    body = _matching_parenthesis_body(statement, match.end() - 1)
    if body is None:
        return None
    columns: list[str] = []
    for raw in _split_top_level(body):
        item = raw.strip()
        if not item:
            continue
        upper = item.upper()
        if upper.startswith(("PRIMARY KEY", "UNIQUE KEY", "KEY ", "CONSTRAINT", "FULLTEXT", "INDEX")):
            if upper.startswith("PRIMARY KEY"):
                key_match = re.search(r"\(([^)]+)\)", item)
                if key_match:
                    parts = [p.strip().strip("`") for p in key_match.group(1).split(",")]
                    columns.append("PRIMARY KEY (" + ", ".join(parts) + ")")
            continue
        columns.append(_convert_column_type(item))
    if not columns:
        return None
    return table, [f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns)})"]


def _split_top_level(body: str) -> list[str]:
    """Split a CREATE TABLE body into top-level comma-separated items."""
    items: list[str] = []
    current: list[str] = []
    depth = 0
    index = 0
    while index < len(body):
        char = body[index]
        if char == "'":
            current.append(char)
            index += 1
            while index < len(body):
                current.append(body[index])
                if body[index] == "\\" and index + 1 < len(body):
                    current.append(body[index + 1])
                    index += 2
                    continue
                if body[index] == "'":
                    break
                index += 1
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            items.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    if current:
        items.append("".join(current))
    return items


_VALUES_TUPLE_RE = re.compile(r"\((?:'[^'\\]*(?:\\.[^'\\]*)*'|[^()])*\)")
_VALUES_TOKEN_RE = re.compile(r"'(?:[^'\\]|\\.)*'|[^,]+")


def _fast_parse_literal(token: str) -> Any:
    token = token.strip()
    if token == "NULL":
        return None
    if token.startswith("'") and token.endswith("'"):
        if "\\" in token:
            return _sql_unescape(token[1:-1])
        return token[1:-1]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _feed_insert(statement: str, pending: dict[str, list[tuple]], table: str) -> None:
    """Parse an INSERT statement and append its rows to ``pending[table]``."""
    values_start = statement.upper().find("VALUES")
    if values_start == -1:
        return
    body = statement[values_start + len("VALUES"):]
    for tuple_match in _VALUES_TUPLE_RE.finditer(body):
        tokens = _VALUES_TOKEN_RE.findall(tuple_match.group(0)[1:-1])
        if not tokens:
            continue
        pending.setdefault(table, []).append(
            tuple(_fast_parse_literal(token) for token in tokens)
        )


def stream_mysql_dump_to_sqlite(
    sql_path: str | Path,
    db_path: str | Path,
    *,
    table_prefixes: tuple[str, ...] = (),
    batch_rows: int = 5000,
    progress_every_mb: int = 300,
) -> dict[str, Any]:
    """Stream the MySQL dump into SQLite in one line-based pass."""
    sql_path = Path(sql_path)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=OFF")
    summary: dict[str, Any] = {
        "tables": {}, "skipped_tables": [], "rows": 0,
        "duration_seconds": 0.0, "bytes_read": 0,
    }
    started = time.monotonic()

    def wanted(table: str) -> bool:
        return not table_prefixes or table.startswith(table_prefixes)

    table_schema: dict[str, bool] = {}
    pending: dict[str, list[tuple]] = {}

    def flush_table(table: str) -> None:
        rows = pending.pop(table, [])
        if not rows or table not in table_schema:
            return
        placeholders = ",".join("?" * len(rows[0]))
        connection.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
        summary["rows"] += len(rows)
        summary["tables"][table] = summary["tables"].get(table, 0) + len(rows)
        connection.commit()

    statement_lines: list[str] | None = None
    statement_kind = ""
    statement_table = ""
    progress_step = progress_every_mb * 1024 * 1024
    last_progress_step = 0

    def report_progress() -> None:
        nonlocal last_progress_step
        step = summary["bytes_read"] // progress_step
        if step > last_progress_step:
            last_progress_step = step
            print(
                f"[cepd-import] read {summary['bytes_read'] / 1e9:.1f} GB, "
                f"rows {summary['rows']:,}, tables {len(summary['tables'])}",
                flush=True,
            )

    with sql_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            summary["bytes_read"] += len(line)
            if statement_lines is None:
                stripped = line.lstrip()
                if stripped.upper().startswith("CREATE TABLE"):
                    statement_lines = [line]
                    statement_kind = "create"
                    statement_table = ""
                elif stripped.upper().startswith("INSERT INTO"):
                    match = _INSERT_INTO_RE.match(stripped)
                    statement_lines = [line]
                    statement_kind = "insert"
                    statement_table = match.group(1) if match else ""
                if statement_lines is None:
                    report_progress()
                    continue
                if line.rstrip("\r\n").endswith(";"):
                    statement = "".join(statement_lines)
                    statement_lines = None
                    if statement_kind == "create":
                        converted = _convert_create_table(statement)
                        table = _CREATE_TABLE_RE.match(statement.strip())
                        table = table.group(1) if table else ""
                        if converted is not None and wanted(table):
                            for ddl in converted[1]:
                                connection.execute(ddl)
                            table_schema[table] = True
                            pending.setdefault(table, [])
                        else:
                            table_schema[table] = False
                            if converted is not None:
                                summary["skipped_tables"].append(table)
                    elif statement_kind == "insert":
                        table = statement_table
                        if table_schema.get(table, False):
                            _feed_insert(statement, pending, table)
                            if len(pending.get(table, ())) >= batch_rows:
                                flush_table(table)
                        elif table and table not in table_schema:
                            table_schema[table] = False
                            summary["skipped_tables"].append(table)
                    report_progress()
                continue
            statement_lines.append(line)
            if not line.rstrip("\r\n").endswith(";"):
                continue
            statement = "".join(statement_lines)
            statement_lines = None
            if statement_kind == "create":
                converted = _convert_create_table(statement)
                table = _CREATE_TABLE_RE.match(statement.strip())
                table = table.group(1) if table else ""
                if converted is not None and wanted(table):
                    for ddl in converted[1]:
                        connection.execute(ddl)
                    table_schema[table] = True
                    pending.setdefault(table, [])
                else:
                    table_schema[table] = False
                    if converted is not None:
                        summary["skipped_tables"].append(table)
            elif statement_kind == "insert":
                table = statement_table
                if table_schema.get(table, False):
                    _feed_insert(statement, pending, table)
                    if len(pending.get(table, ())) >= batch_rows:
                        flush_table(table)
                elif table and table not in table_schema:
                    table_schema[table] = False
                    summary["skipped_tables"].append(table)
            if summary["bytes_read"] % (progress_every_mb * 1024 * 1024) < 4096:
                print(
                    f"[cepd-import] read {summary['bytes_read'] / 1e9:.1f} GB, "
                    f"rows {summary['rows']:,}, tables {len(summary['tables'])}",
                    flush=True,
                )
    for table in list(pending):
        flush_table(table)
    connection.commit()
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.close()
    summary["duration_seconds"] = round(time.monotonic() - started, 1)
    return summary


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: python -m spirosearch.cepd_sqlite_import <dump.sql> <out.db>")
    print(stream_mysql_dump_to_sqlite(sys.argv[1], sys.argv[2]))
