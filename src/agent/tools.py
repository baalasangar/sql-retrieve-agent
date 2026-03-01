"""
agent/tools.py
--------------
Tool functions exposed to the Gemini agent for querying the SQLite database.

Each public function maps to one semantic view. All database access goes
through `_execute_readonly_query()`, which enforces SELECT-only execution,
handles SQLite-specific errors with specific exception types, and logs the
full traceback on unexpected failures.
"""

import logging
import sqlite3
import os

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "poc.db")
)
logger.debug("Database path resolved to: %s", DB_PATH)


# ── Internal helper ───────────────────────────────────────────────────────────

def _execute_readonly_query(query: str) -> list[dict]:
    """
    Safely execute a SELECT-only query against the SQLite database.

    Returns a list of row dicts on success, or a single-element list with
    an ``{"error": "..."}`` dict on failure — this lets the Gemini agent
    surface the error in its response without crashing.

    Exception hierarchy handled (most specific → least specific):
        sqlite3.OperationalError  – bad SQL syntax, missing table/view, etc.
        sqlite3.DatabaseError     – lower-level DB corruption or I/O issues.
        sqlite3.Error             – any other SQLite error.
        Exception                 – truly unexpected errors (logged with traceback).
    """
    conn = None
    try:
        # ── Guard: only SELECT statements are permitted ───────────────────────
        normalised = query.upper().strip()
        if not normalised.startswith("SELECT"):
            logger.warning(
                "Blocked non-SELECT query attempt: %r", query
            )
            return [{"error": "Forbidden: Only SELECT queries are allowed."}]

        logger.debug("Connecting to database: %s", DB_PATH)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        logger.debug("Executing query: %s", query)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        logger.debug("Query returned %d row(s).", len(result))
        return result

    except sqlite3.OperationalError as exc:
        # Most common: bad column name, missing view, syntax error in the SQL.
        logger.error(
            "SQLite OperationalError — likely a bad column name, missing view, "
            "or SQL syntax error.\n  Query : %s\n  Error : %s",
            query,
            exc,
            exc_info=True,
        )
        return [{"error": f"SQL OperationalError: {exc} | Query: {query}"}]

    except sqlite3.DatabaseError as exc:
        # Covers corruption, I/O problems, and other low-level DB failures.
        logger.error(
            "SQLite DatabaseError — possible database file corruption or I/O issue.\n"
            "  Query : %s\n  Error : %s",
            query,
            exc,
            exc_info=True,
        )
        return [{"error": f"SQL DatabaseError: {exc} | Query: {query}"}]

    except sqlite3.Error as exc:
        # Catch-all for any other sqlite3 exception not covered above.
        logger.error(
            "SQLite Error (unexpected type: %s).\n  Query : %s\n  Error : %s",
            type(exc).__name__,
            query,
            exc,
            exc_info=True,
        )
        return [{"error": f"SQL Error ({type(exc).__name__}): {exc} | Query: {query}"}]

    except Exception:
        # Non-SQLite failure (e.g., OS error opening the file).
        logger.exception(
            "Unexpected non-SQLite error while executing query: %r", query
        )
        return [{"error": "An unexpected internal error occurred. Check logs/agent.log for the full trace."}]

    finally:
        if conn is not None:
            conn.close()
            logger.debug("Database connection closed.")


# ── Schema introspection tool ─────────────────────────────────────────────────

def get_view_schemas() -> str:
    """
    Returns the schema definitions of the 3 available semantic views.

    Call this tool FIRST to understand exactly what columns are available
    to SELECT or filter on in the WHERE clause.
    """
    logger.debug("TOOL CALLED: get_view_schemas")
    return """
    Available Views and their schemas:

    1. v_supplier_purchases
       - po_id (INTEGER)
       - order_date (DATE)
       - order_status (TEXT)
       - supplier_id (INTEGER)
       - supplier_name (TEXT)
       - supplier_rating (REAL)
       - product_id (INTEGER)
       - product_name (TEXT)
       - quantity (INTEGER)
       - unit_price (REAL)
       - line_total (REAL)

    2. v_customer_sales
       - so_id (INTEGER)
       - order_date (DATE)
       - order_status (TEXT)
       - customer_id (INTEGER)
       - customer_name (TEXT)
       - customer_email (TEXT)
       - product_id (INTEGER)
       - product_name (TEXT)
       - quantity (INTEGER)
       - unit_price (REAL)
       - line_total (REAL)

    3. v_inventory_status
       - warehouse_id (INTEGER)
       - warehouse_location (TEXT)
       - product_id (INTEGER)
       - product_name (TEXT)
       - category_name (TEXT)
       - quantity_on_hand (INTEGER)
       - last_counted_date (DATE)
    """


# ── Query tools ───────────────────────────────────────────────────────────────

def query_supplier_purchases_view(select_clause: str, where_clause: str) -> list[dict]:
    """
    Executes a query against the v_supplier_purchases view.

    Args:
        select_clause: Columns to return — do NOT include the word SELECT.
                       Example: "supplier_name, SUM(line_total) as total"
        where_clause:  Filter / GROUP BY conditions — do NOT include WHERE.
                       Example: "supplier_rating > 4.0 GROUP BY supplier_name"
                       Pass an empty string or "1=1" to return all rows.
    """
    logger.debug("TOOL CALLED: query_supplier_purchases_view called with select_clause=%r, where_clause=%r",
                 select_clause, where_clause)
    where = f"WHERE {where_clause}" if where_clause and where_clause.strip() not in ("", "1=1") else ""
    query = f"SELECT {select_clause} FROM v_supplier_purchases {where}".strip()
    logger.debug("query_supplier_purchases_view → %s", query)
    logger.debug("TOOL COMPLETED: query_supplier_purchases_view")
    return _execute_readonly_query(query)


def query_customer_sales_view(select_clause: str, where_clause: str) -> list[dict]:
    """
    Executes a query against the v_customer_sales view.

    Args:
        select_clause: Columns to return — do NOT include the word SELECT.
                       Example: "customer_name, order_date"
        where_clause:  Filter / GROUP BY conditions — do NOT include WHERE.
                       Example: "order_status = 'COMPLETED'"
                       Pass an empty string or "1=1" to return all rows.
    """
    logger.debug("TOOL CALLED: query_customer_sales_view called with select_clause=%r, where_clause=%r",
                 select_clause, where_clause)
    where = f"WHERE {where_clause}" if where_clause and where_clause.strip() not in ("", "1=1") else ""
    query = f"SELECT {select_clause} FROM v_customer_sales {where}".strip()
    logger.debug("query_customer_sales_view → %s", query)
    logger.debug("TOOL COMPLETED: query_customer_sales_view")
    return _execute_readonly_query(query)


def query_inventory_status_view(select_clause: str, where_clause: str) -> list[dict]:
    """
    Executes a query against the v_inventory_status view.

    Args:
        select_clause: Columns to return — do NOT include the word SELECT.
                       Example: "product_name, quantity_on_hand"
        where_clause:  Filter / GROUP BY conditions — do NOT include WHERE.
                       Example: "quantity_on_hand < 10"
                       Pass an empty string or "1=1" to return all rows.
    """
    logger.debug("TOOL CALLED: query_inventory_status_view called with select_clause=%r, where_clause=%r",
                 select_clause, where_clause)
    where = f"WHERE {where_clause}" if where_clause and where_clause.strip() not in ("", "1=1") else ""
    query = f"SELECT {select_clause} FROM v_inventory_status {where}".strip()
    logger.debug("query_inventory_status_view → %s", query)
    logger.debug("TOOL COMPLETED: query_inventory_status_view")
    return _execute_readonly_query(query)
