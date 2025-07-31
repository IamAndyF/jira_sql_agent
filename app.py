from core.config import Config, DATABASE_URL, SAFE_DATABASE_URL
from core.jira_connector import JiraConnector
from core.jira_agent import JiraAgent
from core.database_connector import DatabaseManager
from logger import setup_logger

logger = setup_logger(__name__)

def main():
    config = Config()
        
    db_manager = DatabaseManager()
    try:
        with db_manager.get_connection(DATABASE_URL) as connection:
            logger.info(f"Connected to DB, retrieving schema...")
            db_schema = db_manager.get_schema(connection)
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return


    jira_connector = JiraConnector(config.jira)
    jira_client = jira_connector.get_connection()

    if not jira_client:
        logger.error("Failed to connect to Jira. Please check your configuration.")

    agent = JiraAgent(jira_client, config.jira.jira_project_key, config.openai.openai_api_key)
    issues = agent.get_issues()
    for issue in issues:
        analysis_prompt = agent.analyse_issues(issue, db_schema)
        print("\n=== Generated Prompt ===")
        print(analysis_prompt)
    else:
        logger.info("Failed to establish a connection to Jira. Please check your configuration.")

if __name__ == "__main__":
    main()
