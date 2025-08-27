from core.sql_rag_agent import SQLRAGContext
from core.config import SQLALCHEMY_URL, SCHEMA_PATH, VECTOR_PATH
from utils.json_utils import save_to_json
from logger import logger



try:
    db_uri = SQLALCHEMY_URL
    ctx = SQLRAGContext(db_uri, openai_model="gpt-4o-mini")
    # Fetch schema 
    schema_rows = ctx.schema_store.fetch_schema()
    save_to_json(schema_rows, SCHEMA_PATH)

    # Build vector store 
    ctx.initialize_indexes(per_column_limit=200)
    ctx.value_store.vs.save_local(VECTOR_PATH)

    logger.info("Initialised schema and vector index")
except Exception as e:
    logger.error(f"Failed to initialise schema and vector index: {e}", exc_info=True)


