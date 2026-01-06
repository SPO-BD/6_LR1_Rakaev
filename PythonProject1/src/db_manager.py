import os
import sqlite3
import pandas as pd

class SQLiteManager:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path

    def connect(self):
        return sqlite3.connect(self.db_path)

    def import_csv_to_table(self, csv_path: str, table_name: str):
        df = pd.read_csv(csv_path)
        with self.connect() as conn:
            df.to_sql(table_name, conn, if_exists="replace", index=False)
        return df

    def list_tables(self):
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            return [row[0] for row in cur.fetchall()]

    def read_table(self, table_name: str) -> pd.DataFrame:
        with self.connect() as conn:
            return pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
