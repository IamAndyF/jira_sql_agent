# SQL agent
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from core.config import SQLALCHEMY_URL

class SQLAgent:
    def __init__(self, model):
        self.model = model
        self.client = ChatOpenAI(model_name=self.model, temperature=0)
        self.agent = create_sql_agent(
            llm=self.client,
            db=SQLDatabase.from_uri(SQLALCHEMY_URL),
            agent_type="openai-tools",
            verbose=True,
            allow_dangerous_requests=False
        )


    def get_qeury(self, jira_ticket, analysis_summary):

        combined_prompt = (
            f"Jira Ticket: \n{jira_ticket}\n\n"
            f"Feasiblilty study: \n{analysis_summary}\n\n"
            f"Generate an SQL query for the Jira Ticket, Feasiblity study returned from pre processing ai agent to determine if this is an SQL request can be used if required"
        )

        response = self.agent.invoke({"input": combined_prompt})
        sql_text = response["output"].strip()
        return {"sql": sql_text}
    

