import openai
import json
from jira import JIRA
from openai import OpenAIError
from utils.jira_utils import JiraUtils
from logger import logger


class JiraAgent:
    def __init__(self, jira_client: JIRA, project_key, openai_api_key, openai_model):
        self.jira = jira_client
        self.jira_project_key = project_key
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model


    def analyse_issues(self, issue):
        formatted_issue = JiraUtils.format_issue(issue)

        prompt = f"""
        
            ## Your Role & Constraints
            - Evaluate Jira issues for SQL implementation feasibility
            - Focus on data retrieval, filtering, aggregation, and reporting tasks
            - Reject any requests requiring schema modifications (CREATE, ALTER, DROP), user management, or system administration

            ## Jira Issue to Evaluate
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
            Return the result in **strict JSON** with this exact structure:

            {{
                "issue_key": "{issue.key}",
                "summary": "{issue.fields.summary}",
                "feasible": true/false,
                "confidence": "High" | "Medium" | "Low",
                "complexity_score": integer between 1 and 10,
                "reasoning": "2-3 sentences explaining your decision",
                "missing_information": ["list", "of", "strings"],
                "potential_risks": ["list", "of", "strings"]
            }}

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
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": role_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            return result

        except OpenAIError as e:
            return {
                "issue_key": issue.key,
                "summary": issue.fields.summary,
                "feasible": False,
                "confidence": "Low",
                "complexity_score": 0,
                "reasoning": f"OpenAI API Error: {e}",
                "missing_information": [],
                "potential_risks": []
            }
