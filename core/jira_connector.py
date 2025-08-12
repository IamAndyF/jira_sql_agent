from jira import JIRA, JIRAError
from core.config import JiraConfig

from logger import logger

class JiraConnector:
    def __init__(self, jira_config: JiraConfig):
        self.url = jira_config.url
        self.username = jira_config.username
        self.jira_api_token = jira_config.jira_api_token

    def get_connection(self):
        try:
            jira_client = JIRA(
                server=self.url,
                basic_auth=(self.username, self.jira_api_token)
            )
        
            logger.info(f"Successfully connected to Jira")
            return jira_client

        except JIRAError as e:
            logger.info(f"Failed to connect to Jira: {e}")
            return None



# Testing 
# jira_config = JiraConfig()
# jira_connector = JiraConnector(jira_config)
# x = jira_connector.get_connection()