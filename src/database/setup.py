"""
database/setup.py
-----------------
One-time database initialisation script.

Creates the 10 core tables, the 3 semantic views, and populates them with
synthetic mock data if the database is empty.

Run directly to bootstrap the database:
    uv run -m database.setup
"""

import logging
import os
import random
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "poc.db")
)
logger.debug("setup.py: DB_PATH resolved to %s", DB_PATH)


# ── Connection helper ─────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """
    Returns a connection to the SQLite database, creating the data directory
    if it does not already exist.

    Raises:
        sqlite3.OperationalError: If SQLite cannot open/create the file.
        OSError: If the data directory cannot be created.
    """
    data_dir = os.path.dirname(DB_PATH)
    try:
        os.makedirs(data_dir, exist_ok=True)
        logger.debug("Data directory confirmed: %s", data_dir)
    except OSError as exc:
        logger.error(
            "Cannot create data directory '%s': %s", data_dir, exc, exc_info=True
        )
        raise

    try:
        conn = sqlite3.connect(DB_PATH)
        logger.debug("SQLite connection opened: %s", DB_PATH)
        return conn
    except sqlite3.OperationalError as exc:
        logger.error(
            "Cannot open SQLite database at '%s': %s", DB_PATH, exc, exc_info=True
        )
        raise


# ── Schema initialisation ─────────────────────────────────────────────────────

def initialize_schema(conn: sqlite3.Connection) -> None:
    """
    Creates the 10 core tables and 3 semantic views using CREATE IF NOT EXISTS,
    so it is safe to call repeatedly.

    Raises:
        sqlite3.Error: If any DDL statement fails.
    """
    cursor = conn.cursor()
    logger.info("Initialising database schema…")

    try:
        cursor.execute("PRAGMA foreign_keys = ON;")
        logger.debug("Foreign key enforcement enabled.")

        # ── Tables ────────────────────────────────────────────────────────────

        logger.debug("Creating table: Categories")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Categories (
                category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT    NOT NULL UNIQUE,
                description   TEXT
            )
        """)

        logger.debug("Creating table: Suppliers")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Suppliers (
                supplier_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                contact_email TEXT,
                rating        REAL,
                is_active     BOOLEAN DEFAULT 1
            )
        """)

        logger.debug("Creating table: Products")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Products (
                product_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                supplier_id INTEGER,
                name        TEXT NOT NULL,
                description TEXT,
                base_price  REAL NOT NULL,
                FOREIGN KEY (category_id) REFERENCES Categories(category_id),
                FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id)
            )
        """)

        logger.debug("Creating table: Warehouses")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Warehouses (
                warehouse_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                location_name TEXT    NOT NULL,
                capacity      INTEGER
            )
        """)

        logger.debug("Creating table: Inventory")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Inventory (
                inventory_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      INTEGER,
                warehouse_id    INTEGER,
                quantity_on_hand INTEGER DEFAULT 0,
                last_counted_date DATE,
                FOREIGN KEY (product_id)   REFERENCES Products(product_id),
                FOREIGN KEY (warehouse_id) REFERENCES Warehouses(warehouse_id)
            )
        """)

        logger.debug("Creating table: Customers")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name  TEXT NOT NULL,
                last_name   TEXT NOT NULL,
                email       TEXT UNIQUE,
                join_date   DATE
            )
        """)

        logger.debug("Creating table: PurchaseOrders")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PurchaseOrders (
                po_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id  INTEGER,
                order_date   DATE NOT NULL,
                status       TEXT,
                total_amount REAL,
                FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id)
            )
        """)

        logger.debug("Creating table: PurchaseOrderLineItems")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PurchaseOrderLineItems (
                line_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_id        INTEGER,
                product_id   INTEGER,
                quantity     INTEGER NOT NULL,
                unit_price   REAL    NOT NULL,
                FOREIGN KEY (po_id)       REFERENCES PurchaseOrders(po_id),
                FOREIGN KEY (product_id)  REFERENCES Products(product_id)
            )
        """)

        logger.debug("Creating table: SalesOrders")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SalesOrders (
                so_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id  INTEGER,
                order_date   DATE NOT NULL,
                status       TEXT,
                total_amount REAL,
                FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
            )
        """)

        logger.debug("Creating table: SalesOrderLineItems")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SalesOrderLineItems (
                line_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                so_id        INTEGER,
                product_id   INTEGER,
                quantity     INTEGER NOT NULL,
                unit_price   REAL    NOT NULL,
                FOREIGN KEY (so_id)      REFERENCES SalesOrders(so_id),
                FOREIGN KEY (product_id) REFERENCES Products(product_id)
            )
        """)

        # ── Semantic views ─────────────────────────────────────────────────────

        logger.debug("Creating view: v_supplier_purchases")
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS v_supplier_purchases AS
            SELECT
                po.po_id,
                po.order_date,
                po.status             AS order_status,
                s.supplier_id,
                s.name                AS supplier_name,
                s.rating              AS supplier_rating,
                p.product_id,
                p.name                AS product_name,
                poli.quantity,
                poli.unit_price,
                (poli.quantity * poli.unit_price) AS line_total
            FROM PurchaseOrders po
            JOIN Suppliers               s    ON po.supplier_id   = s.supplier_id
            JOIN PurchaseOrderLineItems  poli ON po.po_id         = poli.po_id
            JOIN Products                p    ON poli.product_id  = p.product_id
        """)

        logger.debug("Creating view: v_customer_sales")
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS v_customer_sales AS
            SELECT
                so.so_id,
                so.order_date,
                so.status                              AS order_status,
                c.customer_id,
                c.first_name || ' ' || c.last_name    AS customer_name,
                c.email                               AS customer_email,
                p.product_id,
                p.name                                AS product_name,
                soli.quantity,
                soli.unit_price,
                (soli.quantity * soli.unit_price)     AS line_total
            FROM SalesOrders so
            JOIN Customers              c    ON so.customer_id   = c.customer_id
            JOIN SalesOrderLineItems    soli ON so.so_id         = soli.so_id
            JOIN Products               p    ON soli.product_id  = p.product_id
        """)

        logger.debug("Creating view: v_inventory_status")
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS v_inventory_status AS
            SELECT
                w.warehouse_id,
                w.location_name  AS warehouse_location,
                p.product_id,
                p.name           AS product_name,
                c.category_name,
                i.quantity_on_hand,
                i.last_counted_date
            FROM Inventory i
            JOIN Warehouses  w ON i.warehouse_id = w.warehouse_id
            JOIN Products    p ON i.product_id   = p.product_id
            JOIN Categories  c ON p.category_id  = c.category_id
        """)

        conn.commit()
        logger.info("Database schema initialised successfully.")

    except sqlite3.Error as exc:
        logger.error(
            "Schema initialisation failed at DDL execution: %s", exc, exc_info=True
        )
        conn.rollback()
        raise RuntimeError(f"Schema initialisation failed: {exc}") from exc


# ── Mock data generation ──────────────────────────────────────────────────────

def generate_mock_data(conn: sqlite3.Connection) -> None:
    """
    Populates all tables with synthetic data if they are empty.

    Raises:
        sqlite3.Error: If any INSERT or UPDATE fails.
    """
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM Categories")
        count = cursor.fetchone()[0]
        if count > 0:
            logger.info(
                "Database already contains %d category row(s). "
                "Skipping mock data generation.",
                count,
            )
            return

        logger.info("Generating mock data…")

        # Categories
        categories = [("Electronics",), ("Office Supplies",), ("Furniture",), ("Breakroom",)]
        cursor.executemany("INSERT INTO Categories (category_name) VALUES (?)", categories)
        logger.debug("Inserted %d categories.", len(categories))

        # Suppliers
        suppliers = [
            ("TechGlobal Inc.",  "sales@techglobal.com",   4.8),
            ("Office Depot Pro", "b2b@officedepot.com",    4.2),
            ("ErgoChairs Ltd.",  "support@ergochairs.com", 3.9),
            ("SnackCorp",        "orders@snackcorp.com",   4.5),
        ]
        cursor.executemany(
            "INSERT INTO Suppliers (name, contact_email, rating) VALUES (?, ?, ?)",
            suppliers,
        )
        logger.debug("Inserted %d suppliers.", len(suppliers))

        # Products  (category_id, supplier_id, name, description, base_price)
        products = [
            (1, 1, "Pro Laptop 15-inch",       "High performance laptop",      1200.00),
            (1, 1, "Wireless Mouse",            "Ergonomic wireless mouse",       25.00),
            (2, 2, "Printer Paper A4",          "500 sheets standard paper",       5.50),
            (2, 2, "Blue Ink Pens (12-pack)",   "Smooth writing pens",             8.25),
            (3, 3, "Mesh Office Chair",         "Adjustable lumbar support",      150.00),
            (3, 3, "Standing Desk",             "Motorized adjustable desk",      350.00),
            (4, 4, "Coffee Beans 1kg",          "Dark roast espresso blend",       18.00),
        ]
        cursor.executemany(
            "INSERT INTO Products (category_id, supplier_id, name, description, base_price) VALUES (?, ?, ?, ?, ?)",
            products,
        )
        logger.debug("Inserted %d products.", len(products))

        # Warehouses
        warehouses = [("North Wing", 5000), ("South Depot", 10000), ("East Annex", 2500)]
        cursor.executemany(
            "INSERT INTO Warehouses (location_name, capacity) VALUES (?, ?)", warehouses
        )
        logger.debug("Inserted %d warehouses.", len(warehouses))

        # Inventory
        inventory_rows = 0
        for product_id in range(1, len(products) + 1):
            for warehouse_id in range(1, 4):
                qty = random.randint(0, 100)
                date = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime(
                    "%Y-%m-%d"
                )
                cursor.execute(
                    "INSERT INTO Inventory (product_id, warehouse_id, quantity_on_hand, last_counted_date) "
                    "VALUES (?, ?, ?, ?)",
                    (product_id, warehouse_id, qty, date),
                )
                inventory_rows += 1
        logger.debug("Inserted %d inventory rows.", inventory_rows)

        # Customers
        customers = [
            ("Alice",   "Smith",    "alice.s@example.com",    "2023-01-15"),
            ("Bob",     "Johnson",  "bjohnson@corporate.com", "2023-06-22"),
            ("Charlie", "Davis",    "cdavis@startup.io",      "2024-02-10"),
        ]
        cursor.executemany(
            "INSERT INTO Customers (first_name, last_name, email, join_date) VALUES (?, ?, ?, ?)",
            customers,
        )
        logger.debug("Inserted %d customers.", len(customers))

        # Purchase Orders & Line Items
        logger.debug("Generating purchase orders…")
        for po_id in range(1, 6):
            supplier_id = random.randint(1, 4)
            order_date = (datetime.now() - timedelta(days=random.randint(30, 365))).strftime(
                "%Y-%m-%d"
            )
            status = random.choice(["DELIVERED", "SHIPPED", "PROCESSING"])
            cursor.execute(
                "INSERT INTO PurchaseOrders (supplier_id, order_date, status, total_amount) VALUES (?, ?, ?, 0)",
                (supplier_id, order_date, status),
            )
            total = 0.0
            for _ in range(random.randint(1, 4)):
                product_id = random.randint(1, 7)
                qty = random.randint(10, 50)
                price = products[product_id - 1][4] * 0.9  # 10 % wholesale discount
                total += qty * price
                cursor.execute(
                    "INSERT INTO PurchaseOrderLineItems (po_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (po_id, product_id, qty, price),
                )
            cursor.execute(
                "UPDATE PurchaseOrders SET total_amount = ? WHERE po_id = ?",
                (total, po_id),
            )
        logger.debug("Inserted 5 purchase orders with line items.")

        # Sales Orders & Line Items
        logger.debug("Generating sales orders…")
        for so_id in range(1, 15):
            customer_id = random.randint(1, 3)
            order_date = (datetime.now() - timedelta(days=random.randint(1, 60))).strftime(
                "%Y-%m-%d"
            )
            status = random.choice(["COMPLETED", "SHIPPED", "CANCELLED"])
            cursor.execute(
                "INSERT INTO SalesOrders (customer_id, order_date, status, total_amount) VALUES (?, ?, ?, 0)",
                (customer_id, order_date, status),
            )
            total = 0.0
            for _ in range(random.randint(1, 3)):
                product_id = random.randint(1, 7)
                qty = random.randint(1, 5)
                price = products[product_id - 1][4]
                total += qty * price
                cursor.execute(
                    "INSERT INTO SalesOrderLineItems (so_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (so_id, product_id, qty, price),
                )
            cursor.execute(
                "UPDATE SalesOrders SET total_amount = ? WHERE so_id = ?",
                (total, so_id),
            )
        logger.debug("Inserted 14 sales orders with line items.")

        conn.commit()
        logger.info("Mock data generated and committed successfully.")

    except sqlite3.IntegrityError as exc:
        logger.error(
            "Data integrity violation during mock data generation "
            "(duplicate key or constraint failure): %s",
            exc,
            exc_info=True,
        )
        conn.rollback()
        raise

    except sqlite3.Error as exc:
        logger.error(
            "SQLite error during mock data generation: %s", exc, exc_info=True
        )
        conn.rollback()
        raise

    except Exception:
        logger.exception("Unexpected error during mock data generation. Rolling back.")
        conn.rollback()
        raise


# ── Public entry point ────────────────────────────────────────────────────────

def setup_database() -> None:
    """Main entry point — opens a connection, initialises the schema, and seeds data."""
    logger.info("setup_database() called. DB path: %s", DB_PATH)
    conn = None
    try:
        conn = get_connection()
        initialize_schema(conn)
        generate_mock_data(conn)
        logger.info("Database setup complete.")
    except Exception:
        logger.exception("setup_database() failed. The database may be in an inconsistent state.")
        raise
    finally:
        if conn is not None:
            conn.close()
            logger.debug("setup_database(): connection closed.")


if __name__ == "__main__":
    import sys
    import os

    # When run directly, bootstrap logging so output is visible on console.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.logging_config import setup_logging  # type: ignore[import]

    setup_logging()
    setup_database()
    print(f"Database setup complete. File at: {DB_PATH}")
