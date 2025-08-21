# SQL agent
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from core.config import SQLALCHEMY_URL

class SQLAgent:
    def __init__(self, model):
        self.model = model
        self.client = ChatOpenAI(model_name=self.model, temperature=0)
        self.db = SQLDatabase.from_uri(SQLALCHEMY_URL)
        self.agent = create_sql_agent(
            llm=self.client,
            db=self.db,
            agent_type="openai-tools",
            verbose=True,
            allow_dangerous_requests=False
        )


    def get_text_columns(self):
        query = f"""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND data_type IN ('character varying', 'text', 'char', 'varchar')
            ORDER BY table_name, column_name;
        """
        try: 
            rows = self.db.run(query)
            return [(row[0], row[1]) for row in rows]
        except Exception as e:
            return []
    

    def get_distinct_values(self, table, column, limit=100):
        try:
            query = f'SELECT DISTINCT "{column}" FROM "{table}" LIMIT {limit};'
            rows = self.db.run(query)
            return [row[0] for row in rows if row[0] is not None]
        except Exception:
            return []
        

    def collect_distinct_values(self):
        distinct_values = {}
        for table, col in self.get_text_columns():
            values = self.get_distinct_values(table, col)
            if values:
                distinct_values[f"{table}.{col}"] = values
        return distinct_values


    def get_qeury(self, jira_ticket, analysis_summary):
        distinct_info = self.collect_distinct_values()
        enriched_context = "\n".join(f"{col}: {values}" for col, values in distinct_info.items())

        combined_prompt = f"""

        Jira Ticket: 
        {jira_ticket}

        Feasiblilty study: 
        {analysis_summary}

        Here are the distinct values categorical columns in the database:
        {enriched_context}

        Before returning the final SQL query output, if there are columns you are not sure about, reference it against the categorical columns in the database provide and check that the filtering makes sense.
        Do not hallucinate columns or field, if there is missing information then return "Unable to generate SQL query"
        """

        response = self.agent.invoke({"input": combined_prompt})
        sql_text = response["output"].strip()
        return {"sql": sql_text}
    

