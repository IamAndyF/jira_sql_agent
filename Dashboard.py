import streamlit as st

from core.backend import analyse_issue_feasibility, get_in_progress, run_sql_task
from core.jira_agent import JiraAgent

st.set_page_config(page_title="Jira SQL Feasibility Dashboard", layout="wide")
st.title("Jira SQL Feasibility Dashboard")
st.caption("Automatically checks Jira issues for SQL feasibility using your JiraAgent.")


# Fetch in-progress issues from Jira
@st.cache_data(ttl=60)
def cached_get_in_progress():
    return get_in_progress()


with st.spinner("Fetching Jira issues and running analysis..."):
    try:
        analyzed_issues = analyse_issue_feasibility()
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()

# Separate into 3 lists
feasible_issues = [i for i in analyzed_issues if i["feasible"]]
not_feasible_issues = [i for i in analyzed_issues if not i["feasible"]]
in_progress_issues = cached_get_in_progress()

tab1, tab2, tab3 = st.tabs(["Feasible", "Not Feasible", "In Progress"])


with tab1:
    if feasible_issues:
        for issue in feasible_issues:
            with st.expander(f"{issue['key']}: {issue['summary']}"):
                st.markdown(issue["analysis"])
                if st.button(
                    f"Select {issue['key']} for processing", key=f"btn-{issue['key']}"
                ):
                    with st.spinner(f"Running SQL task for {issue['key']}..."):
                        output = run_sql_task(issue["key"], issue["summary"])
                        st.code(output, language="sql")

                    st.success(f"{issue['key']} selected for processing.")

                    # Clear Jira status so In Progress tab updates
                    cached_get_in_progress.clear()
                    st.rerun()

    else:
        st.info("No feasible issues found.")


with tab2:
    if not_feasible_issues:
        for issue in not_feasible_issues:
            with st.expander(f"{issue['key']}: {issue['summary']}"):
                st.markdown(issue["analysis"])
    else:
        st.info("No non-feasible issues found.")


with tab3:
    if in_progress_issues:
        for issue in in_progress_issues:
            with st.expander(f"{issue['key']}: {issue['summary']}"):
                st.write("Currently in progress")
    else:
        st.info("No issues in progress")
