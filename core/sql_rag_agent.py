from collections import defaultdict
from typing import Optional

from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities import SQLDatabase
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


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
                rows = conn.execute(sql).fetchall()
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


class ValueVectorStore:
    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        self.vs: Optional[FAISS] = None

    def build_index(self, db: SQLDatabase, text_columns, per_column_limit=200):
        docs, metas = [], []
        for table, col in text_columns:
            sql = f'SELECT DISTINCT "{col}" FROM "{table}" LIMIT {per_column_limit};'
            try:
                with db._engine.connect() as conn:
                    rows = conn.execute(sql).fetchall()
            except Exception:
                rows = []
            for r in rows:
                val = r[0]
                if val is None:
                    continue
                s = str(val)
                if not s.strip():
                    continue
                docs.append(s)
                metas.append({"table": table, "column": col, "value": s})

        if docs:
            self.vs = FAISS.from_texts(docs, self.embeddings, metadatas=metas)
        else:
            self.vs = None

    def search_values(self, text, k=8):
        if not self.vs:
            return []
        return self.vs.similarity_search_with_score(text, k=k)


class SQLRAGContext:
    def __init__(self, db_uri: str, openai_model: str):
        self.db = SQLDatabase.from_uri(db_uri)
        self.schema_store = SchemaStore(self.db)
        self.value_store = ValueVectorStore()
        self.llm = ChatOpenAI(model_name=openai_model, temperature=0)

        self.agent = create_sql_agent(
            llm=self.llm,
            db=self.db,
            agent_type="openai-tools",
            verbose=True,
            allow_dangerous_requests=False,
        )

    def initialize_indexes(self, per_column_limit: int = 200):
        schema_rows = self.schema_store.fetch_schema()
        text_cols = self.schema_store.text_like_columns(schema_rows)
        self.value_store.build_index(
            self.db, text_cols, per_column_limit=per_column_limit
        )

    def retrieve_relevant_values(
        self, user_text, k_values=8, max_cols=6, max_examples_per_col=5
    ):
        hits = self.value_store.search_values(user_text, k=k_values)
        grouped = defaultdict(list)
        for doc, score in hits:
            meta = doc.metadata or {}
            key = (meta.get("table"), meta.get("column"))
            val = meta.get("value")
            if key[0] and key[1] and val:
                grouped[key].append((score, val))

        ranked = {}
        for key, pairs in grouped.items():
            pairs.sort(key=lambda x: x[0])
            examples = []
            seen = set()
            for _, v in pairs:
                if v in seen:
                    continue
                examples.append(v)
                seen.add(v)
                if len(examples) >= max_examples_per_col:
                    break
            ranked[key] = examples

        col_scores = []
        for (t, c), pairs in grouped.items():
            best = min(pairs, key=lambda x: x[0])[0]
            col_scores.append(((t, c), best))
        col_scores.sort(key=lambda x: x[1])
        top_cols = [kc for kc, _ in col_scores[:max_cols]]

        return {kc: ranked[kc] for kc in top_cols if kc in ranked}

    def build_compact_context(self, retrieved):
        cols = list(retrieved.keys())
        tables = self.schema_store.tables_for_columns(cols)
        schema_summary = self.schema_store.compact_schema_for_tables(tables)

        lines = ["Relevant columns and example values:"]
        for (table, col), examples in retrieved.items():
            ex_str = ", ".join(examples[:5])
            suffix = "" if len(examples) <= 5 else f" (+{len(examples)-5} more)"
            lines.append(f"- {table}.{col}: {ex_str}{suffix}")

        return f"""\
        Database tables & columns (compact):
        {schema_summary}

        {chr(10).join(lines)}
        """

    def generate_sql(self, jira_ticket, feasibility_summary, k_values=10):
        query_text = f"{jira_ticket}\n\n{feasibility_summary}".strip()
        retrieved = self.retrieve_relevant_values(
            user_text=query_text,
            k_values=k_values,
            max_cols=6,
            max_examples_per_col=5,
        )
        compact_ctx = self.build_compact_context(retrieved)

        prompt = f"""
        
        Jira Ticket:
        {jira_ticket}

        Feasibility Study:
        {feasibility_summary}

        Context (only use real values shown; don't guess):
        {compact_ctx}

        INSTRUCTIONS:
        - Use only the columns and example values above when applying filters.
        - Prefer JOINs that reflect foreign keys (e.g., trades.symbol -> instruments.symbol).
        - Do NOT hardcode categories not present in examples (e.g., avoid sector='Equity' unless in values).
        - Do NOT include any extra columns.
        - Output ONLY the final SQL query. No commentary.
        - RETURN ALL rows of data unless specified
        """

        resp = self.agent.invoke({"input": prompt})

        sql_text = (resp.get("output") or resp.get("output_text") or "").strip()
        return {"sql": sql_text}


class SQLRAGAgent:
    def __init__(self, rag_ctx: SQLRAGContext):
        self.rag_ctx = rag_ctx
        self.agent = rag_ctx.agent

    def run(self, jira_ticket: str, feasibility_summary: str) -> str:
        retrieved = self.rag_ctx.retrieve_relevant_values(
            f"{jira_ticket}\n{feasibility_summary}",
            k_values=10,
            max_cols=6,
            max_examples_per_col=5,
        )
        compact_ctx = self.rag_ctx.build_compact_context(retrieved)

        prompt = f"""
        
        Jira Ticket:
        {jira_ticket}

        Feasibility Study:
        {feasibility_summary}

        Context (only use these values and columns):
        {compact_ctx}

        INSTRUCTIONS:
        - Write a valid SQL query for the above.
        - Use only the schema/values shown.
        - Do NOT hallucinate missing categories.
        - Return ONLY the SQL.
        """

        resp = self.agent.invoke({"input": prompt})
        return resp.get("output") or resp.get("output_text") or ""
