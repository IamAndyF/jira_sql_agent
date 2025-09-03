from core.config import SCHEMA_PATH, SQLALCHEMY_URL, VECTOR_PATH
from core.sql_rag_agent import SQLRAGContext
from logger import logger
from utils.json_utils import save_to_json

try:
    db_uri = SQLALCHEMY_URL
    ctx = SQLRAGContext(db_uri, openai_model="gpt-4o")
    # Fetch schema
    schema_rows = ctx.schema_store.fetch_schema()
    save_to_json(schema_rows, SCHEMA_PATH)

    # Build vector store
    ctx.initialize_indexes(per_column_limit=200)
    ctx.value_store.vs.save_local(VECTOR_PATH)

    logger.info("Initialised schema and vector index")
except Exception as e:
    logger.error(f"Failed to initialise schema and vector index: {e}", exc_info=True)
