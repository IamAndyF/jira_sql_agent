from jira import JIRA, JIRAError

from core.config import JiraConfig
from logger import logger


class JiraConnector:
    def __init__(self, jira_config: JiraConfig):
        self.url = jira_config.url
        self.username = jira_config.username
        self.jira_api_token = jira_config.jira_api_token

    def get_jira_connection(self):
        try:
            jira_client = JIRA(
                server=self.url, basic_auth=(self.username, self.jira_api_token)
            )

            logger.info(f"Successfully connected to Jira")
            return jira_client

        except JIRAError as e:
            logger.info(f"Failed to connect to Jira: {e}")
            return None

    def progress_ticket(self, jira_client: JIRA, issue_key):
        try:
            transition = jira_client.transitions(issue_key)
            processing_transition = next(
                (t for t in transition if t["name"].lower() == "in progress"), None
            )
            if processing_transition:
                jira_client.transition_issue(issue_key, processing_transition["id"])
                logger.info(f"Issue {issue_key} moved to processing")
            else:
                logger.info(f"No processing stage avaialble for {issue_key}")
        except JIRAError as e:
            logger.info(f"Failed to move {issue_key} to processing: {e}")
