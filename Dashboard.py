import streamlit as st

from core.config import Config
from core.backend import Services

st.set_page_config(page_title="Jira SQL Feasibility Dashboard", layout="wide")
st.title("Jira SQL Feasibility Dashboard")
st.caption("Automatically checks Jira issues for SQL feasibility using your JiraAgent.")


config = Config()
services = Services(config)


# Fetch in-progress issues from Jira
@st.cache_data(ttl=60)
def cached_get_in_progress():
    return services.get_in_progress()


with st.spinner("Fetching Jira issues and running analysis..."):
    try:
        analysed_issues = services.analyse_issue_feasibility()
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()

# Separate into 3 lists
in_progress_issues = cached_get_in_progress()

tab1, tab2, tab3 = st.tabs(["Feasible", "Not Feasible", "In Progress"])


with tab1:
    feasible_issues = [issue for issue in analysed_issues if issue["feasible"]]

    if feasible_issues:
        for issue in feasible_issues:
            with st.expander(f"{issue['issue_key']}: {issue['summary']}"):
                st.markdown(f"**Confidence:** {issue['confidence']}")
                st.markdown(f"**Complexity Score:** {issue['complexity_score']}")
                st.markdown(f"**Reasoning:** {issue['reasoning']}")

                if issue["potential_risks"]:
                    st.warning("**Potential Risks:** " + ", ".join(issue["potential_risks"]))

                if st.button(
                    f"Select {issue['issue_key']} for processing", key=f"btn-{issue['issue_key']}"
                ):
                    with st.spinner(f"Running SQL task for {issue['issue_key']}..."):
                        st.success(f"{issue['issue_key']} selected for processing.")
                        output = services.run_sql_task(issue["issue_key"], issue["summary"])

                        if output["status"] == "success":
                            st.code(output["sql"], language="sql")
                            st.success("SQL task completed successfully.")

                        elif output["status"] == "empty":
                            st.code(output["sql"], language="sql")
                            st.warning("Generated SQL returned no results.")

                        elif output["status"] == "invalid":
                            st.error(f"SQL validation failed — unsafe or disallowed query blocked.")
                        
                        if output.get("sql"):
                            st.code(output["sql"], language="sql")
                            
                    # Clear Jira status so In Progress tab updates
                    cached_get_in_progress.clear()
                    st.rerun()

    else:
        st.info("No feasible issues found.")


with tab2:
    non_feasible_issues = [issue for issue in analysed_issues if not issue["feasible"]]
    if non_feasible_issues:
        for issue in non_feasible_issues:
            with st.expander(f"{issue['issue_key']}: {issue["summary"]}"):
                st.markdown(f"**Reasoning:** {issue["reasoning"]}")
                if issue["missing_information"]:
                    st.info("**Missing Information:** " + ", ".join(issue["missing_information"]))
    else:
        st.info("No non-feasible issues found.")


with tab3:
    if in_progress_issues:
        for issue in in_progress_issues:
            with st.expander(f"{issue['issue_key']}: {issue['summary']}"):
                st.write("Currently in progress")
    else:
        st.info("No issues in progress")
