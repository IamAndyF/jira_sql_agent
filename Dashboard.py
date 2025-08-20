import streamlit as st
import streamlit as st
from core.backend import get_analysed_issues, run_sql_task

st.set_page_config(page_title="Jira SQL Feasibility Dashboard", layout="wide")

st.title("Jira SQL Feasibility Dashboard")
st.caption("Automatically checks Jira issues for SQL feasibility using your JiraAgent.")

with st.spinner("Fetching Jira issues and running analysis..."):
    try:
        analyzed_issues = get_analysed_issues()
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()

# Separate into two lists
feasible_issues = [i for i in analyzed_issues if i["feasible"]]
not_feasible_issues = [i for i in analyzed_issues if not i["feasible"]]

tab1, tab2 = st.tabs(["Feasible", "Not Feasible"])

with tab1:
    if feasible_issues:
        for issue in feasible_issues:
            with st.expander(f"{issue['key']}: {issue['summary']}"):
                st.markdown(issue["analysis"])
                if st.button(f"Select {issue['key']} for processing", key=f"btn-{issue['key']}"):
                    with st.spinner(f"Running SQL task for {issue['key']}..."):
                        output = run_sql_task(issue['key'], issue['summary'])
                        st.code(output["sql"], language="sql")
                        st.write(output["results"])
                    st.success(f"{issue['key']} selected for processing.")
                    
    else:
        st.info("No feasible issues found.")

with tab2:
    if not_feasible_issues:
        for issue in not_feasible_issues:
            with st.expander(f"{issue['key']}: {issue['summary']}"):
                st.markdown(issue["analysis"])
    else:
        st.info("No non-feasible issues found.")