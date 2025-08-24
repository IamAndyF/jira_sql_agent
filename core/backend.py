from core.config import SQLALCHEMY_URL, Config
from core.jira_agent import JiraAgent
from core.jira_connector import JiraConnector
from core.sql_rag_agent import SQLRAGAgent, SQLRAGContext
from logger import logger


def get_analysed_issues():
    config = Config()

    # Get Jira connection
    logger.info("Initialising jira connector")
    jira_connector = JiraConnector(config.jira)
    logger.info("connecting to Jira")
    jira_client = jira_connector.get_jira_connection()
    if not jira_client:
        raise RuntimeError("Failed to connect to Jira.")

    agent = JiraAgent(
        jira_client, config.jira.jira_project_key, config.openai.openai_api_key
    )
    issues = agent.get_issues("To Do")

    results = []
    for issue in issues:
        analysis = agent.analyse_issues(issue)
        feasible = "Feasible: Yes" in analysis or "**Feasible:** Yes" in analysis

        results.append(
            {
                "key": issue.key,
                "summary": issue.fields.summary,
                "feasible": feasible,
                "analysis": analysis,
            }
        )

    return results


def run_sql_task(issue_key, issue_summary):
    config = Config()

    jira_connector = JiraConnector(config.jira)
    jira_client = jira_connector.get_jira_connection()
    jira_agent = JiraAgent(
        jira_client, config.jira.jira_project_key, config.openai.openai_api_key
    )

    issue = jira_client.issue(issue_key)
    jira_agent.assign_to_self(issue_key)
    jira_connector.progress_ticket(jira_client, issue_key)

    rag_ctx = SQLRAGContext(db_uri=SQLALCHEMY_URL, openai_model="gpt-4o-mini")
    rag_ctx.initialize_indexes()
    agent = SQLRAGAgent(rag_ctx)

    return agent.run(issue, issue_summary)


def get_in_progress():
    config = Config()
    # Get Jira connection
    logger.info("Initialising jira connector")
    jira_connector = JiraConnector(config.jira)
    logger.info("connecting to Jira")
    jira_client = jira_connector.get_jira_connection()
    if not jira_client:
        raise RuntimeError("Failed to connect to Jira.")

    agent = JiraAgent(
        jira_client, config.jira.jira_project_key, config.openai.openai_api_key
    )
    issues = agent.get_issues("In Progress")
    logger.info(f"Found {len(issues)} issues in progress")

    return [
        {
            "key": issue.key,
            "summary": issue.fields.summary,
            "status": issue.fields.status.name,
        }
        for issue in issues
    ]
