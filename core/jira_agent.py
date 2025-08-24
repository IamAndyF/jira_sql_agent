import openai
from jira import JIRA, JIRAError
from openai import OpenAIError

from logger import logger


class JiraAgent:
    def __init__(self, jira_client: JIRA, project_key, openai_api_key):
        self.jira = jira_client
        self.jira_project_key = project_key
        self.openai_api_key = openai_api_key

    def get_issues(self, status, jql=None):
        if jql is None:
            if status == "In Progress":
                jql = f'project="{self.jira_project_key}" AND status="{status}" AND assignee=currentUser()'
            else:
                jql = f'project="{self.jira_project_key}" AND status="{status}"'

        return self.jira.search_issues(jql)

    def post_comment(self, issue_key, comment):
        try:
            self.jira.add_comment(issue_key, comment)
            logger.info(f"Comment posted to issue {issue_key}")
        except JIRAError as e:
            logger.error(f"Failed to post comment to issue {issue_key}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error posting comment to issue {issue_key}: {e}")

    def assign_to_self(self, issue_key):
        try:
            current_user_id = self.jira.current_user()
            issue = self.jira.issue(issue_key)
            issue.update(assignee={"id": current_user_id})
            logger.info(f"Issue {issue_key} assigned to self")
        except JIRAError as e:
            logger.info(f"Failed to assign issue {issue_key} to self: {e}")

    def analyse_issues(self, issue):
        formatted_issue = "\n".join(
            [
                f"{issue.key}: {issue.fields.summary}\nDescription: {issue.fields.description or 'No description'}"
            ]
        )

        prompt = f"""
        
            ## Your Role & Constraints
            - Evaluate Jira issues for SQL implementation feasibility
            - Focus on data retrieval, filtering, aggregation, and reporting tasks
            - Reject any requests requiring schema modifications (CREATE, ALTER, DROP), user management, or system administration

            ## Jira Issues to Evaluate
            {formatted_issue}


            ## Reject any tasks that require:
            - Requests that involve any schema modifications (CREATE, ALTER, DROP)
            - Data from external APIs or feeds
            - Manual file uploads from external systems
            - Streaming or live data not stored in our database
            - Access to third-party SaaS or cloud services

            **CRITICAL EXAMPLES OF REQUESTS THAT MUST BE REJECTED:**
            - "Generate Interaction Reports" (no fields specified, no output format)
            - "Generate sales report" (no specific fields, no metrics)
            - "Create customer analysis" (no fields, no output format, no metrics)
            - "Build reporting functionality" (completely vague)
            - "Develop dashboard for interactions" (no specific data points)

            ## Vagueness Assessment
            **Specific field names or column names mentioned** (not just "data", "information", "reports")
            **Exact output format stated** (CSV export, dashboard view, summary table, etc.)
            **Clear business metrics or aggregations defined** (COUNT of X, SUM of Y, etc.)

            If the request is vague reject with:
            - **Feasible:** No
            - **Reasoning:** "Request lacks sufficient technical specifications. Missing: [list missing elements]"
            - **Required Information:** [list what stakeholder needs to provide]

            ## Required Output Format
            For each issue, return in this EXACT format below:

            **Issue Key: [JIRA-XXXX] - [Jira-Summary] **
            - **Feasible:** Yes/No
            - **Confidence:** High/Medium/Low
            - **Complexity Score:** 1-10 (where 1=simple SELECT, 10=complex multi-table analysis)
            - **Reasoning:** [2-3 sentences explaining your decision]
            - **Missing Information:** [if vague, list what needs clarification]
            - **Potential Risks:** [any performance or data access concerns]

            Be conservative in your assessments. When in doubt, reject and explain why the task exceeds simple SQL operations.
            """

        role_prompt = f"""
            You are an expert AI backend engineer and SQL data extraction specialist.
            Your job is to read Jira tickets and determine if they describe a task
            that involves extracting and/or transforming data from SQL databases.
        """
        client = openai.Client(api_key=self.openai_api_key)

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": role_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=2000,
            )

            return response.choices[0].message.content.strip()

        except OpenAIError as e:
            return f"OpenAI API Error: {e}"
