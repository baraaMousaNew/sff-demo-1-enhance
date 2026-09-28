"""
Iris Database Connector (JDBC via JAR)
Handles connections and queries to the InterSystems IRIS database
using the JDBC driver JAR and jaydebeapi.

Requirements:
    - Java must be installed on the machine.
    - jaydebeapi must be installed: pip install jaydebeapi
    - The InterSystems JDBC JAR must be downloaded and its path set below.
      Download from: https://intersystems.com/downloads (intersystems-jdbc-x.x.x.jar)

Usage:
    client = IrisDBClient(host="localhost", port=1972, namespace="USER",
                          username="user", password="pass")
    client.connect()
    rows = client.execute_query("SELECT TOP 10 Name FROM MyTable")
    client.disconnect()
"""

import jaydebeapi

# ─────────────────────────────────────────────────────────────────────────────
# TODO: Set the full path to your InterSystems JDBC JAR file here.
#       Example (Windows): r"C:\iris\intersystems-jdbc-3.8.4.jar"
#       Example (Linux):   "/opt/iris/intersystems-jdbc-3.8.4.jar"
# ─────────────────────────────────────────────────────────────────────────────
IRIS_JDBC_JAR_PATH = r"C:\path\to\intersystems-jdbc-x.x.x.jar"

IRIS_JDBC_DRIVER_CLASS = "com.intersystems.jdbc.IRISDriver"


class IrisDBClient:
    """
    Client for connecting to an InterSystems IRIS database via JDBC.

    Args:
        host (str):      Iris server hostname or IP address.
        port (int):      Iris Superserver port (default: 1972).
        namespace (str): Iris namespace (e.g. 'USER').
        username (str):  Iris username.
        password (str):  Iris password.
        jar_path (str):  Optional override for the JDBC JAR path.
                         Falls back to the module-level IRIS_JDBC_JAR_PATH.
    """

    def __init__(self, host, port, namespace, username, password, jar_path=None):
        self.host = host
        self.port = int(port)
        self.namespace = namespace
        self.username = username
        self.password = password
        self.jar_path = jar_path or IRIS_JDBC_JAR_PATH
        self.connection = None

    # ─────────────────────────────────────────────────────────────────────────
    # Connection Management
    # ─────────────────────────────────────────────────────────────────────────

    def connect(self):
        """Open the JDBC connection to Iris."""
        jdbc_url = f"jdbc:IRIS://{self.host}:{self.port}/{self.namespace}"
        try:
            self.connection = jaydebeapi.connect(
                IRIS_JDBC_DRIVER_CLASS,
                jdbc_url,
                [self.username, self.password],
                self.jar_path
            )
            print(f"[IrisDB] Connected to {jdbc_url}")
        except Exception as e:
            print(f"[IrisDB] Connection failed: {e}")
            raise

    def disconnect(self):
        """Close the JDBC connection."""
        if self.connection:
            try:
                self.connection.close()
                print("[IrisDB] Disconnected.")
            except Exception as e:
                print(f"[IrisDB] Error while disconnecting: {e}")
            finally:
                self.connection = None

    def is_connected(self):
        """Return True if a connection is currently open."""
        return self.connection is not None

    # ─────────────────────────────────────────────────────────────────────────
    # Query Execution
    # ─────────────────────────────────────────────────────────────────────────

    def execute_query(self, sql, params=None):
        """
        Execute a SELECT query and return all rows as a list of dicts.

        Args:
            sql (str):        SQL query string.
            params (list):    Optional list of positional parameters (use ? as placeholder).

        Returns:
            list[dict]: Each row as a dictionary keyed by column name.

        Example:
            rows = client.execute_query(
                "SELECT Name, Age FROM MyTable WHERE Status = ?", ["Active"]
            )
        """
        self._require_connection()
        cursor = None
        try:
            cursor = self.connection.cursor()
            if params:
                print(f"[IrisDB] SQL  : {sql}")
                print(f"[IrisDB] Params: {params}")
                cursor.execute(sql, params)
            else:
                print(f"[IrisDB] SQL  : {sql}")
                cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(columns, row)) for row in rows]
            print(f"[IrisDB] Rows : {len(result)} — {result}")
            return result
        except Exception as e:
            print(f"[IrisDB] Query failed: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def execute_non_query(self, sql, params=None):
        """
        Execute an INSERT, UPDATE, or DELETE statement.

        Args:
            sql (str):     SQL statement.
            params (list): Optional list of positional parameters.

        Returns:
            int: Number of rows affected.

        Example:
            client.execute_non_query(
                "UPDATE MyTable SET Status = ? WHERE Id = ?", ["Inactive", 42]
            )
        """
        self._require_connection()
        cursor = None
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            self.connection.commit()
            affected = cursor.rowcount
            print(f"[IrisDB] Statement executed. Rows affected: {affected}")
            return affected
        except Exception as e:
            print(f"[IrisDB] Statement failed, rolling back: {e}")
            try:
                self.connection.rollback()
            except Exception:
                pass
            raise
        finally:
            if cursor:
                cursor.close()

    def get_schemas_and_tables(self) -> dict:
        """
        Return a dict mapping each schema name to a sorted list of table names.
        Queries INFORMATION_SCHEMA.TABLES for BASE TABLE entries only.

        Returns:
            dict[str, list[str]]: e.g. {"MySchema": ["TableA", "TableB"], ...}
        """
        sql = (
            "SELECT TABLE_SCHEMA, TABLE_NAME "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME"
        )
        rows = self.execute_query(sql)
        result: dict = {}
        for row in rows:
            schema = row["TABLE_SCHEMA"]
            table  = row["TABLE_NAME"]
            result.setdefault(schema, []).append(table)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Context Manager Support  (use with `with IrisDBClient(...) as client:`)
    # ─────────────────────────────────────────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False  # do not suppress exceptions

    # ─────────────────────────────────────────────────────────────────────────
    # Internal Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _require_connection(self):
        """Raise a RuntimeError if there is no active connection."""
        if not self.is_connected():
            raise RuntimeError(
                "[IrisDB] No active connection. Call connect() first "
                "or use the client as a context manager (with statement)."
            )
