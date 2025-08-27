from typing import Optional
from sqlalchemy import text

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.utilities import SQLDatabase
from logger import logger

class ValueVectorStore:
    def __init__(self, embedding_model = "text-embedding-3-small"):
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        self.vs: Optional[FAISS] = None

    def build_index(self, db: SQLDatabase, text_columns, per_column_limit = 200):
        docs, metas = [], []
        for table, col in text_columns:
            sql = f'SELECT DISTINCT "{col}" FROM "{table}" LIMIT {per_column_limit};'
            try:
                with db._engine.connect() as conn:
                    rows = conn.execute(text(sql)).fetchall()
                logger.info(f"Fetched {len(rows)} rows from {table}.{col}")
            except Exception as e:
                rows = []
                logger.warning(f"Failed to fetch from {table}.{col}: {e}")
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

    def search_values(self, text, k = 8):
        if not self.vs:
            return []
        return self.vs.similarity_search_with_score(text, k=k)