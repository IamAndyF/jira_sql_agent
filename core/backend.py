import pandas as pd
import os
import tempfile
from sqlalchemy import text
from core.config import SQLALCHEMY_URL, Config
from core.jira_agent import JiraAgent
from core.jira_connector import JiraConnector
from core.sql_rag_agent import SQLRAGAgent, SQLRAGContext
from core.database_connector import Database
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

    # Generate SQL
    rag_ctx = SQLRAGContext(db_uri=SQLALCHEMY_URL, openai_model="gpt-4o")
    rag_ctx.initialize_indexes()
    agent = SQLRAGAgent(rag_ctx)
    raw_sql_query =  agent.run(issue, issue_summary)
    sql_query = agent.clean_sql_output(raw_sql_query)

    # Execute SQL
    db = Database(SQLALCHEMY_URL)
    with db.get_connection() as conn:
        result = conn.execute(text(sql_query)).fetchall()
        df = pd.DataFrame(result)
    
    if df.empty:
        jira_agent.post_comment(issue_key, "Generated SQL returned no results: \n```\n{sql-query}\n```")
        return sql_query
    
    tmp_dir = tempfile.gettempdir()
    csv_path = os.path.join(tmp_dir, f"{issue_key}_results.csv")
    df.to_csv(csv_path, index=False)

    jira_client.add_attachment(issue=issue, attachment=csv_path)

    jira_agent.post_comment(
        issue_key,
        f"Gnerated SQL query: \n```\n{sql_query}\n```\n"
         f"Results exported in and attached as: '{issue_key}_results.csv'."
        )
    
    os.remove(csv_path)

    return sql_query



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
