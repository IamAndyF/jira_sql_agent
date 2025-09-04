import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())  # Load environment variables from .env file


class DatabaseConfig:
    def __init__(self):
        # Configuration for the database connection
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = os.getenv("DB_PORT", "5432")
        self.dbname = os.getenv("DB_NAME", "tradeall")
        self.user = os.getenv("DB_USER", "jira_agent")
        self.password = os.getenv("DB_PASSWORD", "")

    @property
    def sqlalchemy_connection_string(self):
        """Returns a SQLAlchemy compatible connection string"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"


class JiraConfig:
    def __init__(self):
        self.url = os.getenv("JIRA_URL", "")
        self.username = os.getenv("JIRA_USERNAME", "")
        self.jira_api_token = os.getenv("JIRA_API_KEY", "")
        self.jira_project_key = os.getenv("JIRA_PROJECT_KEY", "Projects")


class OpenAIConfig:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


# Control panel for settings, container that holds all configurations
class Config:
    def __init__(self):
        self.database = DatabaseConfig()  # Creates database settings
        self.jira = JiraConfig()  # Creates jira settings
        self.openai = OpenAIConfig()  # Creates openai settings


config = Config()

SQLALCHEMY_URL = config.database.sqlalchemy_connection_string

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "data", "schema.json")
VECTOR_PATH = os.path.join(BASE_DIR, "data", "faiss_index")
