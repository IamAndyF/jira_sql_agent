from contextlib import contextmanager

from sqlalchemy import create_engine

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
