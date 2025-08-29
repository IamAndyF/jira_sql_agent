from collections import defaultdict
import re

from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from core.schema_store import SchemaStore
from core.vector_store import ValueVectorStore
from utils.jira_utils import JiraUtils
from logger import logger

class SQLRAGContext:
    def __init__(self, db_uri, openai_model):
        self.db = SQLDatabase.from_uri(db_uri)
        self.schema_store = SchemaStore(self.db)
        self.value_store = ValueVectorStore()
        self.llm = ChatOpenAI(model_name=openai_model, temperature=0)

    def initialize_indexes(self, per_column_limit= 200):
        schema_rows = self.schema_store.fetch_schema()
        logger.info(f"{len(schema_rows)} columns found in schema.")
        text_cols = self.schema_store.text_like_columns(schema_rows)
        logger.info(f"{len(text_cols)} text-like columns found for indexing.")
        self.value_store.build_index(self.db, text_cols, per_column_limit=per_column_limit)

    def retrieve_relevant_values(self, user_text, k_values = 8, max_cols = 6, max_examples_per_col = 5):
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
    
    
class SQLRAGAgent:
    def __init__(self, rag_ctx: SQLRAGContext):
        self.rag_ctx = rag_ctx
        self.llm = rag_ctx.llm

    @staticmethod
    def clean_sql_output(raw_text):
        match = re.search(r"```sql(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return raw_text.strip()

    def run(self, jira_ticket):
        retrieved = self.rag_ctx.retrieve_relevant_values(
            f"{jira_ticket}",
            k_values=10,
            max_cols=6,
            max_examples_per_col=5,
        )

        formatted_jira_ticket = JiraUtils.format_issue(jira_ticket)
        compact_ctx = self.rag_ctx.build_compact_context(retrieved)

        # Debug: print schema context to terminal
        print("=== Compact Context ===")
        print(compact_ctx)
        print("=======================")

        prompt = f"""
        
        Jira Ticket:
        {formatted_jira_ticket}

        Schema Context:
        {compact_ctx}

        INSTRUCTIONS:
        - Carefully review the Jira ticket and understand what the ticket requires to be transformed into a SQL query.
        - Use the Schema Context to identify relevant tables and columns.
        - Capture **all constraints** mentioned in the ticket (filters, groupings, breakdowns, date ranges, categories, limits).
        - If time ranges are mentioned, filter using the correct date column.
        - Use JOINs if needed to pull in columns from related tables.
        - Do NOT hallucinate missing categories.
        - Do NOT include any extra columns.
        - Be precise, but don’t ignore requested details in favor of simplicity.
        - RETURN ALL rows of data unless specified.
        - Wrap the SQL inside a fenced block like this:

        ```sql
        SELECT ...
        FROM ...
        """

        resp = self.llm.invoke(prompt)
        return resp.content
        
    

        
