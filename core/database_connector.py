
import psycopg2
from psycopg2.extras import RealDictCursor
from core.config import DATABASE_URL, SAFE_DATABASE_URL
from contextlib import contextmanager
from sqlalchemy import create_engine, text

from logger import logger

class Database:
    def __init__(self, database_url):
        self.engine = create_engine(database_url, pool_pre_ping=True)

    @contextmanager
    def get_connection(self):
        conn = self.engine.connect()
        try: 
            yield conn
        finally:
            conn.close()

    def execute_query(self, query, conn, params=None):
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()

            return [dict(row) for row in results]
            
        except Exception as e:
            logger.info(f"Database query error: {e}")
            conn.rollback()
            return None

    def get_schema(self, conn):
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
        """)

        rows = cursor.fetchall()
        schema = {}
        for row in rows:
            table, column, dtype = row['table_name'], row['column_name'], row['data_type']
            schema.setdefault(table, []).append((column, dtype))
        return schema
    
    def get_connection_depreceated(self, database_url):
        conn = None
        try:
            conn = psycopg2.connect(
                database_url,
                cursor_factory=RealDictCursor
            )
            logger.info(f"Successfully connected to the database")
            yield conn
        
        except Exception as e:
            logger.info(f"Database connection error: {e}")
            if conn: 
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
                logger.info(f"Database connection closed.")
