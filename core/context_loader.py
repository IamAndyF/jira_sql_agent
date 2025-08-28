
from core.sql_rag_agent import SQLRAGContext
from core.config import SQLALCHEMY_URL, SCHEMA_PATH, VECTOR_PATH
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
import json


def load_context(openai_model="gpt-4o-mini"):
    ctx = SQLRAGContext(SQLALCHEMY_URL, openai_model)

    # Load schema snapshot
    with open(SCHEMA_PATH, "r") as f:
        cached_schema = json.load(f)

    ctx.schema_store.fetch_schema = lambda: cached_schema

    # Load vector index
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    ctx.value_store.vs = FAISS.load_local(VECTOR_PATH, embeddings, allow_dangerous_deserialization=True)

    return ctx
