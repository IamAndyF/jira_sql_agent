from openai import OpenAI
from core.jira_agent import JiraAgent
from core.database_connector import DatabaseManager


class TaskAgent:
    def __init__(self, db_manager, openai_api_key, jira_agent, model="gpt-4o-mini"):
        self.db_manager = db_manager
        self.openai_api_key = openai_api_key
        self.jira_agent = jira_agent
        self.model = model
    
    def execute_task(self, issue, db_schema, conn):
        client = OpenAI(api_key=self.openai_api_key)

        prompt=f"""
        You are a task agent that executes tasks based on the provided issue and database schema.You are an expert SQL developer.
        Database schema: {db_schema}
        Task: {issue.fields.summary}
        Description: {issue.fields.description or 'No description provided'}

        Rules:
        - PostgreSQL syntax only.
        - SELECT queries only (read-only).
        - Include LIMIT 1000 to avoid huge outputs.
        - Return only the SQL code without explanations.
        """

        sql_response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You write safe SQL."},
                {"role": "user", "content": prompt}     
            ],
            temperature=0,
            max_tokens=300
        )

        sql_query = sql_response.choices[0].message.content.strip()

        results = self.db_manager.execute_query(sql_query, conn)

        comment = f"""
            Task executed successfully. 
            *SQL Query:*
            ```sql
            {sql_query}
            ```
            *Results:*
            {results} # Showing first few rows
        """

        self.jira_agent.post_comment(issue.key, comment)

        return {
        "sql": sql_query,
        "results": results
    }

