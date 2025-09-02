import streamlit as st
import re
from core.config import Config
from core.backend import Services

st.set_page_config(page_title="Jira SQL Feasibility Dashboard", layout="wide")
st.title("Jira SQL Feasibility Dashboard")
st.caption("Automatically checks Jira issues for SQL feasibility using your JiraAgent.")


config = Config()
services = Services(config)


# Fetch in-progress issues from Jira
@st.cache_data(ttl=5)
def cached_get_in_progress():
    return services.get_in_progress()

if "analysed_issues" not in st.session_state:
    with st.spinner("Fetching Jira issues and running analysis..."):
        try:
            st.session_state.analysed_issues = services.analyse_issue_feasibility()
        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

analysed_issues = st.session_state.analysed_issues

# Separate into 3 lists
in_progress_issues = cached_get_in_progress()

tab1, tab2, tab3 = st.tabs(["Feasible", "Not Feasible", "In Progress"])


with tab1:
    feasible_issues = [issue for issue in analysed_issues if issue["feasible"]]

    if feasible_issues:
        for issue in feasible_issues:
            with st.expander(f"{issue["issue_key"]}: {issue["summary"]}"):
                st.markdown(f"**Confidence:** {issue["confidence"]}")
                st.markdown(f"**Complexity Score:** {issue["complexity_score"]}")
                st.markdown(f"**Reasoning:** {issue["reasoning"]}")

                if issue["potential_risks"]:
                    st.warning("**Potential Risks:** " + ", ".join(issue["potential_risks"]))

                if st.button(
                    f"Select {issue["issue_key"]} for processing", key=f"btn-{issue["issue_key"]}"
                ):
                    with st.spinner(f"Running SQL task for {issue["issue_key"]}..."):
                        st.success(f"{issue["issue_key"]} selected for processing.")
                        output = services.run_sql_task(issue["issue_key"])

                        st.session_state.analysed_issues = [
                            i for i in st.session_state.analysed_issues
                            if i["issue_key"] != issue["issue_key"]
                        ]

                        cached_get_in_progress.clear()
                        st.session_state.in_progress_issues = cached_get_in_progress()

                        if output["status"] == "success":
                            st.code(output["sql"], language="sql")
                            st.success("SQL task completed successfully.")

                        elif output["status"] == "empty":
                            st.code(output["sql"], language="sql")
                            st.warning("Generated SQL returned no results.")

                        elif output["status"] == "invalid":
                            st.error(f"SQL validation failed — unsafe or disallowed query blocked.")

                        if output.get("sql"):
                            st.session_state[f"{issue['issue_key']}_sql"] = output["sql"].strip()
                            st.code(st.session_state[f"{issue['issue_key']}_sql"], language="sql")
                            
                        st.rerun()

    else:
        st.info("No feasible issues found.")


with tab2:
    non_feasible_issues = [issue for issue in analysed_issues if not issue["feasible"]]
    if non_feasible_issues:
        for issue in non_feasible_issues:
            with st.expander(f"{issue["issue_key"]}: {issue["summary"]}"):
                st.markdown(f"**Reasoning:** {issue["reasoning"]}")
                if issue["missing_information"]:
                    st.info("**Missing Information:** " + ", ".join(issue["missing_information"]))
    else:
        st.info("No non-feasible issues found.")


with tab3:
    if in_progress_issues:
        for issue in in_progress_issues:
            issue_key = issue["issue_key"]
            with st.expander(f"{issue_key}: {issue["summary"]}"):
                st.markdown(f"**Ticket description:** {issue['description']}")

                if f"{issue_key}_sql" not in st.session_state:
                    st.session_state[f"{issue_key}_sql"] = ""

                    jira_comments = services.jira_utils.get_ticket_comments(issue_key)
                    bot_sql_comments = [
                        c["body"] for c in jira_comments if "```" in c["body"]
                    ]
                    if bot_sql_comments:
                        latest_sql = bot_sql_comments[-1]
                        match = re.search(r"```\n(.*?)\n```", latest_sql, re.S)
                        if match:
                            st.session_state[f"{issue_key}_sql"] = match.group(1).strip()


                if f"{issue_key}_chat" not in st.session_state:
                    st.session_state[f"{issue_key}_chat"] = []
                    jira_comments = services.jira_utils.get_ticket_comments(issue_key)
                    for comment in jira_comments:
                        st.session_state[f"{issue_key}_chat"].append({"role": "user", "content": comment["body"]})


                if st.session_state[f"{issue_key}_sql"]:
                    st.markdown("**Current SQL:**")
                    st.code(st.session_state[f"{issue_key}_sql"], language="sql")

                user_feedback = st.text_area(f"Add feedback / instructions for {issue_key}", key=f"feedback_{issue_key}")

                if st.button(f"Update SQL with feedback", key=f"update_{issue_key}"):
                    if user_feedback.strip():
                        st.session_state[f"{issue_key}_chat"].append({"role": "user", "content": user_feedback.strip()})
                        updated_sql = services.run_updated_sql_with_feedback(
                        current_sql=st.session_state[f"{issue_key}_sql"],
                        jira_ticket=issue['summary'],
                        chat_history=st.session_state[f"{issue_key}_chat"],
                        max_retries=1
                    )
                         
                        st.session_state[f"{issue_key}_sql"] = updated_sql.sql.strip()

                        # Show results
                        st.success("SQL updated based on feedback.")
                        st.code(st.session_state[f"{issue_key}_sql"], language="sql")
                        st.rerun()

    else:
        st.info("No issues in progress")
