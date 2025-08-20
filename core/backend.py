from core.config import Config, DATABASE_URL
from core.jira_connector import JiraConnector
from core.jira_agent import JiraAgent
from core.database_connector import DatabaseManager
from core.sql_agent import SQLAgent
from logger import logger

def get_analysed_issues():
    config = Config()

    db_manager = DatabaseManager()
    try:
        with db_manager.get_connection(DATABASE_URL) as connection:
            logger.info(f"Connected to DB, retrieving schema...")
            db_schema = db_manager.get_schema(connection)
    except Exception as e:
        logger.error(f"Database connection error: {e}")

    # Get Jira connection
    logger.info("Initialising jira connector")
    jira_connector = JiraConnector(config.jira)
    logger.info("connecting to Jira")
    jira_client = jira_connector.get_connection()
    if not jira_client:
        raise RuntimeError("Failed to connect to Jira.")
    
    agent = JiraAgent(jira_client, config.jira.jira_project_key, config.openai.openai_api_key)
    issues = agent.get_issues()

    results = []
    for issue in issues:
        analysis = agent.analyse_issues(issue)
        feasible = "Feasible: Yes" in analysis or "**Feasible:** Yes" in analysis

        results.append({
            "key": issue.key,
            "summary": issue.fields.summary,
            "feasible": feasible,
            "analysis": analysis
        })

    return results

def run_sql_task(issue_key, issue_summary):
    config = Config()

    jira_connector = JiraConnector(config.jira)
    jira_client = jira_connector.get_connection()

    issue = jira_client.issue(issue_key)

    
    sql_agent = SQLAgent(
        config.openai.openai_model
    )

    return sql_agent.get_qeury(issue, issue_summary)