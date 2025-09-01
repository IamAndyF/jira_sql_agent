from logger import logger
from jira import JIRA, JIRAError

class JiraUtils:
    def __init__(self, jira_client: JIRA, jira_project_key):
        self.jira = jira_client
        self.jira_project_key = jira_project_key


    def get_issues(self, status, jql=None):
        if jql is None:
            if status == "In Progress":
                jql = f'project="{self.jira_project_key}" AND status="{status}" AND assignee=currentUser()'
            else:
                jql = f'project="{self.jira_project_key}" AND status="{status}"'

        return self.jira.search_issues(jql)


    def progress_ticket(self, issue_key):
        try:
            transition = self.jira.transitions(issue_key)
            processing_transition = next(
                (t for t in transition if t["name"].lower() == "in progress"), None
            )
            if processing_transition:
                self.jira.transition_issue(issue_key, processing_transition["id"])
                logger.info(f"Issue {issue_key} moved to processing")
            else:
                logger.warning(f"No processing stage avaialble for {issue_key}")
        except JIRAError as e:
            logger.error(f"Failed to move {issue_key} to processing: {e}")


    def get_ticket_comments(self, issue_key):
        issue = self.jira.issue(issue_key)
        comments = self.jira.comments(issue)

        results = [
            {
            "id": comment.id,
            "author": comment.author.displayName,
            "body": comment.body,
            "created": comment.created
            }
            for comment in comments
        ]

        return results


    def post_comment(self, issue_key, comment):
            try:
                self.jira.add_comment(issue_key, comment)
                logger.info(f"Comment posted to issue {issue_key}")
            except JIRAError as e:
                logger.error(f"Failed to post comment to issue {issue_key}: {e}")
            except Exception as e:
                logger.critical(f"Unexpected error posting comment to issue {issue_key}: {e}")


    def assign_to_self(self, issue_key):
        try:
            current_user_id = self.jira.current_user()
            issue = self.jira.issue(issue_key)
            issue.update(assignee={"id": current_user_id})
            logger.info(f"Issue {issue_key} assigned to self")
        except JIRAError as e:
            logger.error(f"Failed to assign issue {issue_key} to self: {e}")


    @staticmethod
    def format_issue(issue):
        formatted_issue = "\n".join(
            [
                f"{issue.key}: {issue.fields.summary}\nDescription: {issue.fields.description or 'No description'}"
            ]
        )
        return formatted_issue