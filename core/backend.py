import pandas as pd
import os
import tempfile
from sqlalchemy import text
from core.config import SQLALCHEMY_URL, Config
from core.jira_agent import JiraAgent
from core.jira_connector import JiraConnector
from core.sql_rag_agent import SQLRAGAgent
from core.database_connector import Database
from core.context_loader import load_context
from utils.jira_utils import JiraUtils
from logger import logger

class Services:
    def __init__(self, config: Config):
        self.config = config
        self.jira_client = JiraConnector(config.jira).get_jira_connection()
        self.jira_utils = JiraUtils(self.jira_client, config.jira.jira_project_key)
        self.jira_agent = JiraAgent(self.jira_client, config.jira.jira_project_key, config.openai.openai_api_key)
        self.db = Database(SQLALCHEMY_URL)

    def analyse_issue_feasibility(self):

        issues = self.jira_utils.get_issues("To Do")

        results = []
        for issue in issues:
            analysis = self.jira_agent.analyse_issues(issue)
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


    def run_sql_task(self, issue_key, issue_summary):

        issue = self.jira_client.issue(issue_key)
        self.jira_utils.assign_to_self(issue_key)
        self.jira_utils.progress_ticket(issue_key)

        # Generate SQL
        ctx = load_context("gpt-4o")
        agent = SQLRAGAgent(ctx)
        raw_sql_query =  agent.run(issue)
        sql_query = agent.clean_sql_output(raw_sql_query)

        # Execute SQL
        db = Database(SQLALCHEMY_URL)
        with db.get_connection() as conn:
            result = conn.execute(text(sql_query)).fetchall()
            df = pd.DataFrame(result)
        
        if df.empty:
            self.jira_utils.post_comment(issue_key, "Generated SQL returned no results: \n```\n{sql-query}\n```")
            return sql_query
        
        tmp_dir = tempfile.gettempdir()
        csv_path = os.path.join(tmp_dir, f"{issue_key}_results.csv")
        df.to_csv(csv_path, index=False)

        self.jira_client.add_attachment(issue=issue, attachment=csv_path)

        self.jira_utils.post_comment(
            issue_key,
            f"Gnerated SQL query: \n```\n{sql_query}\n```\n"
            f"Results exported in and attached as: '{issue_key}_results.csv'."
            )
        
        os.remove(csv_path)

        return sql_query


    def get_in_progress(self):
        
        issues = self.jira_utils.get_issues("In Progress")
        logger.info(f"Found {len(issues)} issues in progress")

        return [
            {
                "key": issue.key,
                "summary": issue.fields.summary,
                "status": issue.fields.status.name,
            }
            for issue in issues
        ]
