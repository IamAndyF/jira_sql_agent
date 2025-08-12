from core.config import Config, DATABASE_URL
from core.jira_connector import JiraConnector
from core.jira_agent import JiraAgent
from core.database_connector import DatabaseManager
from core.task_agent import TaskAgent
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
        return

    # Get Jira connection
    jira_connector = JiraConnector(config.jira)
    jira_client = jira_connector.get_connection()
    if not jira_client:
        raise RuntimeError("Failed to connect to Jira.")
    
    agent = JiraAgent(jira_client, config.jira.jira_project_key, config.openai.openai_api_key)
    issues = agent.get_issues()

    results = []
    for issue in issues:
        analysis = agent.analyse_issues(issue, db_schema)
        feasible = "Feasible: Yes" in analysis or "**Feasible:** Yes" in analysis

        results.append({
            "key": issue.key,
            "summary": issue.fields.summary,
            "feasible": feasible,
            "analysis": analysis
        })

    return results

def run_sql_task(issue_key):
    config = Config()
    db_manager = DatabaseManager()

    with db_manager.get_connection(DATABASE_URL) as connection:
        logger.info(f"Connected to DB, running SQL task for issue {issue_key}...")
        db_schema = db_manager.get_schema(connection)
            
        jira_connector = JiraConnector(config.jira)
        jira_client = jira_connector.get_connection()
        jira_agent = JiraAgent(jira_client, config.jira.jira_project_key, config.openai.openai_api_key)

        issue = jira_client.issue(issue_key)

        task_agent = TaskAgent(
            db_manager,
            config.openai.openai_api_key,
            jira_agent,
            model=config.openai.openai_model
        )

        return task_agent.execute_task(issue, db_schema, connection)