from jira import JIRA, JIRAError
import openai
from openai import OpenAIError
from langchain.prompts import PromptTemplate
from logger import logger

class JiraAgent:
    def __init__(self, jira_client: JIRA, project_key, openai_api_key):
        self.jira = jira_client
        self.jira_project_key = project_key
        self.openai_api_key = openai_api_key

     
    def get_issues(self, jql=None):
        if jql is None:
            jql = f"project={self.jira_project_key} AND status='To Do'"
        return self.jira.search_issues(jql)
    
    def post_comment(self, issue_key, comment):
        try:
            self.jira.add_comment(issue_key, comment)
            logger.info(f"Comment posted to issue {issue_key}")
        except JIRAError as e:
            logger.error(f"Failed to post comment to issue {issue_key}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error posting comment to issue {issue_key}: {e}")

        
    def analyse_issues(self, issue, db_schema):    
        formatted_issue = "\n".join([f"{issue.key}: {issue.fields.summary}\nDescription: {issue.fields.description or 'No description'}"])

        prompt = PromptTemplate(
            input_variables=["db_schema", "issue"],
            template="""
            You are a senior database developer and SQL expert with 10+ years of experience in enterprise data systems.

            ## Your Role & Constraints
            - Evaluate Jira issues for SQL implementation feasibility
            - You can ONLY work with existing database schema (no DDL operations allowed)
            - Focus on data retrieval, filtering, aggregation, and reporting tasks
            - Reject any requests requiring schema modifications, user management, or system administration

            ## Database Schema
            {db_schema}

            ## Security & Performance Constraints
            - Maximum query execution time: 30 seconds
            - No operations on tables with >10M rows without explicit approval
            - No schema modifications (CREATE, ALTER, DROP)
            - Read-only access only

            ## Jira Issues to Evaluate
            {issues}

            ## Complexity Assessment Criteria
            Simple tasks (ACCEPT):
            - Single table queries with basic WHERE clauses
            - Simple JOINs (2-3 tables max)
            - Basic aggregations (COUNT, SUM, AVG)
            - Standard reporting queries
            - Data exports with filtering

            Complex tasks (REJECT):
            - Multi-step data transformations
            - Complex subqueries with multiple CTEs
            - Cross-database operations
            - Performance-critical queries requiring optimization
            - Tasks requiring >5 table JOINs

            ## Vagueness Assessment
            **Specific field names or column names mentioned** (not just "data", "information", "reports")
            **Exact output format stated** (CSV export, dashboard view, summary table, etc.)
            **Clear business metrics or aggregations defined** (COUNT of X, SUM of Y, etc.)

            **CRITICAL EXAMPLES OF REQUESTS THAT MUST BE REJECTED:**
            - "Generate Interaction Reports" (no fields specified, no output format)
            - "Generate sales report" (no specific fields, no metrics)
            - "Create customer analysis" (no fields, no output format, no metrics)
            - "Build reporting functionality" (completely vague)
            - "Develop dashboard for interactions" (no specific data points)

            If the request is vague reject with:
            - **Feasible:** No
            - **Reasoning:** "Request lacks sufficient technical specifications. Missing: [list missing elements]"
            - **Required Information:** [list what stakeholder needs to provide]

            ## Required Output Format
            For each issue, provide:

            **Issue Key: [JIRA-XXXX] - [Jira-Summary] **
            - **Feasible:** Yes/No
            - **Confidence:** High/Medium/Low
            - **Complexity Score:** 1-10 (where 1=simple SELECT, 10=complex multi-table analysis)
            - **Reasoning:** [2-3 sentences explaining your decision based on schema analysis]
            - **Required Tables/Fields:** [if feasible, list specific tables.columns needed]
            - **Missing Information:** [if vague, list what needs clarification]
            - **Estimated Query Complexity:** [Simple SELECT / JOIN operation / Aggregation / etc.]
            - **Potential Risks:** [any performance or data access concerns]
            - **Recommended Priority:** [Low/Medium/High based on business impact vs complexity]

            ## Decision Framework

            1. First check that the request is not vague
            2. Verify all required data exists in the provided schema
            3. Assess if relationships between tables are clear and properly defined
            4. Evaluate query complexity against your capabilities
            5. Consider potential performance implications
            6. Confirm no schema modifications are required

            ## Edge Cases to Reject
            - Requests that involve any schema modifications (CREATE, ALTER, DROP)
            - Tasks requiring data from external systems not in schema
            - Any mention of user permissions, access control, or system administration
            - Real-time processing or streaming data requirements

            Be conservative in your assessments. When in doubt, reject and explain why the task exceeds simple SQL operations.
            """
        )
        
        full_prompt = prompt.format(db_schema=db_schema, issues=formatted_issue)
        client = openai.Client(api_key=self.openai_api_key)

        try: 
            response = client.chat.completions.create(
                model = 'gpt-3.5-turbo',
                messages = [
                    {"role": "system", "content": "You are an AI backend engineer."},
                    {"role": "user", "content":full_prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )

            return response.choices[0].message.content.strip()
        
        except OpenAIError as e:
            return f"OpenAI API Error: {e}"
            