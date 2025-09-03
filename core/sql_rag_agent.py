import re
from collections import defaultdict

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from core.schema_store import SchemaStore
from core.vector_store import ValueVectorStore
from logger import logger
from utils.jira_utils import JiraUtils


class SQLResponse(BaseModel):
    sql: str


class ReviewedSQL(BaseModel):
    sql: str
    notes: str


class SQLRAGContext:
    def __init__(self, db_uri, openai_model):
        self.db = SQLDatabase.from_uri(db_uri)
        self.schema_store = SchemaStore(self.db)
        self.value_store = ValueVectorStore()
        self.llm = ChatOpenAI(model_name=openai_model, temperature=0)

    def initialize_indexes(self, per_column_limit=200):
        schema_rows = self.schema_store.fetch_schema()
        logger.info(f"{len(schema_rows)} columns found in schema.")
        text_cols = self.schema_store.text_like_columns(schema_rows)
        logger.info(f"{len(text_cols)} text-like columns found for indexing.")
        self.value_store.build_index(
            self.db, text_cols, per_column_limit=per_column_limit
        )

    def retrieve_relevant_values(
        self, user_text, k_values=30, max_cols=10, max_examples_per_col=10
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

        lines = [
            "Relevant columns (with illustrative values — do NOT filter unless explicitly requested in the Jira ticket):"
        ]
        for (table, col), examples in retrieved.items():
            ex_str = ", ".join(examples[:5])
            suffix = "" if len(examples) <= 5 else f" (+{len(examples)-5} more)"
            lines.append(f"- {table}.{col}: e.g. {ex_str}{suffix}")

        return f"""\
        Database tables & columns (compact):
        {schema_summary}

        Sample of data values in tables and columns:
        {chr(10).join(lines)}
        """


class SQLRAGAgent:
    def __init__(self, rag_ctx: SQLRAGContext):
        self.rag_ctx = rag_ctx
        self.llm = rag_ctx.llm
        self.generate_llm = self.llm.with_structured_output(SQLResponse)
        self.review_llm = self.llm.with_structured_output(ReviewedSQL)

    @staticmethod
    def validate_sql(query):
        pattern = re.compile(r"^\s*(WITH\b|SELECT\b)", re.IGNORECASE)
        if not pattern.match(query.strip()):
            return False

        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "CREATE",
            "EXEC",
            "GRANT",
        ]
        if any(word in query.upper() for word in forbidden):
            return False

        return True

    def generate_sql(self, jira_ticket, compact_context, full_schema):
        prompt = f"""
        
        Jira Ticket:
        {jira_ticket}

        Schema Context with example values- (GUIDE — columns likely relevant to this ticket):
        {compact_context}

        Full Schema - (All tables and columns):
        {full_schema}

        INSTRUCTIONS:
        - Carefully review the Jira ticket and understand what the ticket requires to be transformed into a SQL query.
        - Capture **all constraints** mentioned in the ticket (filters, groupings, breakdowns, date ranges, categories, limits).
        - The columns in the 'Relevant columns & sample values' section are **likely relevant** to the Jira ticket.
        - Use these columns as your **primary guide** when generating the SQL.
        - You may only use other columns if required for joins or aggregation, and only if they exist in the full schema reference.
        - Do NOT invent columns or tables not listed in the full schema reference.
        - Only include columns explicitly requested in the ticket unless necessary for joins/aggregations.

        FILTER RULES:
        - Only apply a filter if the Jira ticket explicitly mentions it.
        - Do NOT infer filters based solely on column names or example values.
        - For numeric/date columns, only filter if ticket specifies a range.
        - Ignore columns that are not relevant to the ticket.

        JOIN RULES:
        - Use JOINs if needed based on the schema.
        - Only include columns required by the ticket.

        OUTPUT RULES:
        - Include exactly the columns requested.
        - Return all rows unless the ticket specifies otherwise.
        - Return SQL as a JSON object:
        {{
            "sql" : "SELECT ...FROM ..."
        }}
        """

        return self.generate_llm.invoke(prompt)

    def review_sql(self, sql_query):
        prompt = f"""
        You are an SQL expert for PostgreSQL. Your task is to:

        - Fix any syntax errors for PostgreSQL.
        - Ensure the query is correct, efficient, and safe (no DROP/DELETE/UPDATE statements).
        - Make sure it will run successfully in PostgreSQL.
        - Only convert subqueries into CTEs if it meaningfully improves readability or simplifies the query.
        - Otherwise, keep the query structure as simple as possible.

        
        SQL query to review: 
        ```sql
        {sql_query}
        ```

        Return a JSON object:
        {{
            "sql": "SELECT ...",
        }}
        """

        return self.review_llm.invoke(prompt)

    def run(self, jira_ticket):
        retrieved = self.rag_ctx.retrieve_relevant_values(
            f"{jira_ticket}",
            k_values=30,
            max_cols=10,
            max_examples_per_col=10,
        )

        formatted_jira_ticket = JiraUtils.format_issue(jira_ticket)
        compact_ctx = self.rag_ctx.build_compact_context(retrieved)
        full_schema = self.rag_ctx.schema_store.fetch_schema()

        generated_sql_query: SQLResponse = self.generate_sql(
            formatted_jira_ticket, compact_ctx, full_schema
        )
        reviewed_sql_query: ReviewedSQL = self.review_sql(
            generated_sql_query.sql.strip()
        )
        sql_query = reviewed_sql_query.sql.strip()

        # Final validation
        if not self.validate_sql(sql_query):
            raise ValueError("Generated SQL is invalid or unsafe.")

        return sql_query

    def update_sql_with_feedback(
        self, current_sql, jira_ticket, chat_history, max_retries
    ):

        prompt = f"""
        You are an expert SQL assistant in PostgreSQL.

        Jira ticket summary:
        {jira_ticket}
        
        Current SQL:
        ```sql
        {current_sql}
        ```

        Feedback and chat history:
        {chat_history}

        Schema Context with example values - (GUIDE — columns likely relevant to this ticket):
        {self.rag_ctx.build_compact_context(self.rag_ctx.retrieve_relevant_values(jira_ticket))}

        Full Schema - (All tables and columns):
        {self.rag_ctx.schema_store.fetch_schema()}

        Rules:
        - Do NOT DROP, DELETE, UPDATE, ALTER, CREATE.
        - Keep all requested columns, filters, and groupings.
        - Provide reasoning before final SQL.

        Task:
        Update the SQL query to reflect the feedback and chat history.
        Return a JSON object with:
        {{
            "sql": "Updated SQL query here",
            "notes": "Explain what was changed and why"
        }}
        """

        for attempt in range(max_retries + 1):
            try:
                response = self.review_llm.invoke(prompt)
                updated_sql = response.sql.strip()
                notes = response.notes

                if not self.validate_sql(updated_sql):
                    raise ValueError("Updated SQL is invalid or unsafe.")

                logger.info(f"SQL updated for ticket '{jira_ticket}': {notes}")
                return ReviewedSQL(sql=updated_sql, notes=notes)

            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed: {e}")
                if attempt == max_retries:
                    return ReviewedSQL(
                        sql=current_sql, notes="No changes made due to repeated errors."
                    )
