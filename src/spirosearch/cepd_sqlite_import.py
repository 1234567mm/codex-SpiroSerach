"""Stream MySQL SQL dump into SQLite (CEPDB optimized path).

Instead of scanning the 49 GB dump repeatedly, a single streaming pass
converts ``CREATE TABLE`` statements into SQLite DDL and feeds ``INSERT``
rows through parameterized batch inserts. After the import, all HTL-window
queries run as indexed SQL against SQLite — no repeated text scans.

Usage (import):
    stream_mysql_dump_to_sqlite(
        sql_path, db_path,
        progress_every_mb=300,
        batch_rows=5000,
        table_prefixes=("data_",),  # skip Django framework tables
    )
"""
from __future__ import annotations

import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Iterator

from spirosearch.cepd_import import _parse_sql_literal, _split_sql_values

_MYSQL_TYPE_MAP = {
    "int": "INTEGER",
    "tinyint": "INTEGER",
    "smallint": "INTEGER",
    "mediumint": "INTEGER",
    "bigint": "INTEGER",
    "float": "REAL",
    "double": "REAL",
    "real": "REAL",
    "decimal": "REAL",
    "numeric": "REAL",
    "varchar": "TEXT",
    "char": "TEXT",
    "text": "TEXT",
    "tinytext": "TEXT",
    "mediumtext": "TEXT",
    "longtext": "TEXT",
    "datetime": "TEXT",
    "timestamp": "TEXT",
    "date": "TEXT",
    "time": "TEXT",
    "blob": "BLOB",
    "longblob": "BLOB",
    "varbinary": "BLOB",
    "binary": "BLOB",
    "json": "TEXT",
    "enum": "TEXT",
    "set": "TEXT",
    "year": "INTEGER",
    "bit": "INTEGER",
    "bool": "INTEGER",
    "boolean": "INTEGER",
    "mediumblob": "BLOB",
    "tinyblob": "BLOB",
}

_STRIP_TRAILING = re.compile(
    r"\s*(?:ENGINE|DEFAULT CHARSET|COLLATE|AUTO_INCREMENT|COMMENT)[^,)]*"
    r"(?:,\s*(?:ENGINE|DEFAULT CHARSET|COLLATE|AUTO_INCREMENT|COMMENT)[^,)]*)*$",
    re.IGNORECASE,
)


def _convert_column_type(decl: str) -> str:
    """Convert one MySQL column definition to SQLite DDL text."""
    decl = decl.strip()
    match = re.match(r"`?(\w+)`?\s+([a-z]+)", decl, re.IGNORECASE)
    if not match:
        return decl
    column = match.group(1)
    base = match.group(2).casefold()
    base = base.split("(")[0]
    sqlite_type = _MYSQL_TYPE_MAP.get(base, "TEXT")
    body = decl[match.end():]
    if "UNSIGNED" in body.upper():
        body = re.sub(r"\s*UNSIGNED", "", body, flags=re.IGNORECASE)
    # Keep NOT NULL; drop DEFAULT expressions that SQLite may reject.
    not_null = " NOT NULL" if re.search(r"\bNOT\s+NULL\b", body, re.IGNORECASE) else ""
    primary = " PRIMARY KEY" if re.search(r"\bPRIMARY\s+KEY\b", body, re.IGNORECASE) else ""
    if primary and not re.search(r"\bAUTO_INCREMENT\b", body, re.IGNORECASE):
        pass
    return f"{column} {sqlite_type}{not_null}{primary}"


def _convert_create_table(statement: str) -> tuple[str, list[str]] | None:
    """Convert a MySQL CREATE TABLE statement to SQLite DDL.

    Returns ``(table_name, sqlite_statements)`` or None when the statement is
    not a plain table create. The trailing ``ENGINE=...`` / ``CHARSET=...``
    options after the closing parenthesis are ignored.
    """
    match = re.match(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?\s*\(",
        statement.strip(),
        re.IGNORECASE,
    )
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
                columns.append("PRIMARY KEY (" + _key_columns(item) + ")")
            continue
        columns.append(_convert_column_type(item))
    if not columns:
        return None
    return table, [f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns)})"]


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


def _key_columns(item: str) -> str:
    match = re.search(r"\(([^)]+)\)", item)
    if not match:
        return ""
    parts = [p.strip().strip("`") for p in match.group(1).split(",")]
    return ", ".join(parts)


def _split_top_level(body: str) -> Iterator[str]:
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
    return iter(items)


def stream_mysql_dump_to_sqlite(
    sql_path: str | Path,
    db_path: str | Path,
    *,
    table_prefixes: tuple[str, ...] = (),
    batch_rows: int = 5000,
    progress_every_mb: int = 300,
) -> dict[str, Any]:
    """Stream the MySQL dump into SQLite in one pass.

    Returns an import summary (tables created, rows inserted, duration).
    """
    sql_path = Path(sql_path)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=OFF")
    summary: dict[str, Any] = {
        "tables": {},
        "skipped_tables": [],
        "rows": 0,
        "duration_seconds": 0.0,
        "bytes_read": 0,
    }
    started = time.monotonic()

    def wanted(table: str) -> bool:
        return not table_prefixes or table.startswith(table_prefixes)

    buffer = ""
    pending: dict[str, list[tuple]] = {}
    table_schema: dict[str, bool] = {}

    def flush_table(table: str) -> None:
        rows = pending.pop(table, [])
        if not rows or table not in table_schema:
            return
        placeholders = ",".join("?" * len(rows[0]))
        connection.executemany(
            f"INSERT INTO {table} VALUES ({placeholders})", rows
        )
        summary["rows"] += len(rows)
        summary["tables"][table] = summary["tables"].get(table, 0) + len(rows)
        connection.commit()

    with sql_path.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            summary["bytes_read"] += len(chunk)
            buffer += chunk
            processed = True
            while processed:
                processed = False
                # CREATE TABLE statement?
                create_match = re.search(
                    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?\s*\(",
                    buffer,
                    re.IGNORECASE,
                )
                if create_match and not table_schema.get(create_match.group(1)):
                    statement_end = _statement_end(buffer, create_match.start())
                    if statement_end is not None:
                        statement = buffer[create_match.start():statement_end + 1]
                        converted = _convert_create_table(statement)
                        table = create_match.group(1)
                        if converted is not None and wanted(table):
                            converted_table, ddl = converted
                            for line in ddl:
                                connection.execute(line)
                            table_schema[table] = True
                            pending.setdefault(table, [])
                        else:
                            table_schema[table] = False
                            if converted is not None:
                                summary["skipped_tables"].append(table)
                        buffer = buffer[:create_match.start()] + buffer[statement_end + 1:]
                        processed = True
                        continue
                # INSERT statement?
                insert_match = re.search(r"INSERT\s+INTO\s+`?(\w+)`?\s+VALUES\s*\(", buffer, re.IGNORECASE)
                if insert_match:
                    statement_end = _statement_end(buffer, insert_match.start())
                    if statement_end is not None:
                        table = insert_match.group(1)
                        statement = buffer[insert_match.start():statement_end + 1]
                        buffer = buffer[:insert_match.start()] + buffer[statement_end + 1:]
                        if table_schema.get(table, False):
                            _feed_insert(statement, pending, table)
                            if len(pending.get(table, ())) >= batch_rows:
                                flush_table(table)
                        elif table not in table_schema:
                            table_schema[table] = False
                            summary["skipped_tables"].append(table)
                        processed = True
                        continue
                if not processed and len(buffer) > 16 * 1024 * 1024:
                    # No complete statement in the head; drop the oldest half
                    # only when it cannot contain a statement start.
                    head = buffer[: len(buffer) // 2]
                    if "VALUES" not in head.upper() and "CREATE TABLE" not in head.upper():
                        buffer = buffer[len(buffer) // 2:]
            if summary["bytes_read"] % (progress_every_mb * 1024 * 1024) < 8 * 1024 * 1024:
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


def _statement_end(buffer: str, start: int) -> int | None:
    """Find the end (index of ';') of the statement starting at ``start``."""
    index = start
    in_string = False
    while index < len(buffer):
        char = buffer[index]
        if char == "'" and not in_string:
            in_string = True
        elif char == "'" and in_string:
            if index + 1 < len(buffer) and buffer[index + 1] == "'":
                index += 1
            else:
                in_string = False
        elif char == "\\" and in_string and index + 1 < len(buffer):
            index += 1
        elif char == ";" and not in_string:
            return index
        index += 1
    return None


def _feed_insert(statement: str, pending: dict[str, list[tuple]], table: str) -> None:
    """Parse an INSERT statement and append its rows to ``pending[table]``."""
    values_start = statement.upper().find("VALUES")
    if values_start == -1:
        return
    body = statement[values_start + len("VALUES"):].strip()
    depth = 0
    start = 0
    index = 0
    while index < len(body):
        char = body[index]
        if char == "'":
            index += 1
            while index < len(body):
                if body[index] == "\\" and index + 1 < len(body):
                    index += 2
                    continue
                if body[index] == "'":
                    break
                index += 1
        elif char == "(":
            depth += 1
            if depth == 1:
                start = index + 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                tokens = _split_sql_values(body[start:index])
                pending.setdefault(table, []).append(
                    tuple(_parse_sql_literal(token) for token in tokens)
                )
        index += 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: python -m spirosearch.cepd_sqlite_import <dump.sql> <out.db>")
    result = stream_mysql_dump_to_sqlite(sys.argv[1], sys.argv[2])
    print(json := {"summary": result})
