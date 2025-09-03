from collections import defaultdict

from langchain_community.utilities import SQLDatabase
from sqlalchemy import text


class SchemaStore:
    def __init__(self, db: SQLDatabase, schema="public"):
        self.db = db
        self.schema = schema

    def fetch_schema(self):

        sql = f"""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = '{self.schema}'
        ORDER BY table_name, ordinal_position;
        """
        try:
            with self.db._engine.connect() as conn:
                rows = conn.execute(text(sql)).fetchall()
            return [{"table": r[0], "column": r[1], "type": r[2]} for r in rows]
        except Exception:
            return []

    def text_like_columns(self, schema_rows):
        if schema_rows is None:
            schema_rows = self.fetch_schema()
        text_types = {"text", "varchar", "character varying", "char"}
        return [
            (r["table"], r["column"])
            for r in schema_rows
            if r["type"].lower() in text_types
        ]

    def tables_for_columns(self, cols):
        return sorted({t for t, _ in cols})

    def compact_schema_for_tables(self, tables):
        all_rows = self.fetch_schema()
        by_table = defaultdict(list)
        for r in all_rows:
            if r["table"] in tables:
                by_table[r["table"]].append(f"{r['column']} ({r['type']})")
        summary_lines = []
        for t in sorted(by_table.keys()):
            cols = ", ".join(by_table[t][:20])
            if len(by_table[t]) > 20:
                cols += f", … (+{len(by_table[t])-20} more)"
            summary_lines.append(f"- {t}: {cols}")
        return "\n".join(summary_lines)
