# Jira SQL AI Agent

Automatically converts Jira tickets into actionable SQL queries using a multi-AI agent workflow.

---

## Overview

Jira tickets for SQL tasks vary in clarity — some are straightforward, others vague or infeasible. This project demonstrates how AI agents can automate feasibility checking, SQL generation, and iterative refinement.

---

## How It Works

1️⃣ **Feasibility Check**: GPT evaluates if a ticket can be solved with SQL, providing reasoning and a confidence score.  

2️⃣ **Semantic Column Analysis (FAISS)**: Ticket descriptions are embedded and compared against schema + sample values in a FAISS vector store to surface the most relevant columns.  

3️⃣ **Schema-Aware SQL Generation**: Relevant columns are ranked and combined with full schema context. A LangChain-powered RAG workflow generates SQL grounded in real data.  

4️⃣ **Guardrails & Review**: Destructive queries are filtered; a reviewer agent validates and optimizes the SQL.  

5️⃣ **Feedback Loop**: Users can review and refine queries iteratively directly in Jira.

---

## Setup

```bash
git clone https://github.com/IamAndyF/jira_sql_agent.git
cd jira_sql_agent
pip install -r requirements.txt


setup .env file
DB_HOST=...
DB_PORT=...
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
JIRA_URL=...
JIRA_USERNAME=...
JIRA_API_KEY=...
OPENAI_API_KEY=...

This builds the database schema reference and value vector stores used for semantic SQL generation.
python initialise_index.py 

streamlit run app.py
