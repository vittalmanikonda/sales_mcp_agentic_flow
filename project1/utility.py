import os
import re

import mysql.connector
from dotenv import load_dotenv

load_dotenv(override=True)

MAX_ROWS = 100
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke|call|"
    r"load|outfile|dumpfile|into|lock|handler)\b",
    re.IGNORECASE,
)


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE", "ecommerce_sales"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "mysql"),
    )


def get_schema(connection) -> str:
    """Describe every table and column so the model knows what it can query."""
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT table_name, column_name, column_type
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
        ORDER BY table_name, ordinal_position
        """
    )
    tables: dict[str, list[str]] = {}
    for table, column, col_type in cursor.fetchall():
        tables.setdefault(table, []).append(f"{column} {col_type}")
    cursor.close()
    return "\n".join(f"{t}({', '.join(cols)})" for t, cols in tables.items())


def clean_sql(text: str) -> str:
    """Strip markdown fences and a trailing semicolon from the model's reply."""
    text = re.sub(r"^```(?:sql)?|```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE)
    return text.strip().rstrip(";").strip()


def ensure_read_only(sql: str) -> None:
    """Allow a single SELECT only; never let the model change data."""
    if not sql.lower().startswith("select"):
        raise ValueError(f"Only SELECT queries are allowed. Got: {sql!r}")
    if ";" in sql:
        raise ValueError("Only one statement is allowed.")
    if FORBIDDEN.search(sql):
        raise ValueError(f"Query contains a forbidden keyword: {sql!r}")


def run_query(connection, sql: str) -> list[dict]:
    cursor = connection.cursor(dictionary=True)
    cursor.execute(sql)
    rows = cursor.fetchmany(MAX_ROWS)
    cursor.close()
    return rows
