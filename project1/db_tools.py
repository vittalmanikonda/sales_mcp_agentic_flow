"""Database tools the model can call."""

import json

from langchain_core.tools import tool

from utility import clean_sql, ensure_read_only, get_schema, run_query


def build_tools(connection, model):
    @tool
    def get_database_schema() -> str:
        """Return every table and its columns. Call this before writing SQL."""
        return get_schema(connection)

    @tool
    def run_select_query(sql: str) -> str:
        """Run one read-only SELECT and return the rows as JSON."""
        statement = clean_sql(sql)
        ensure_read_only(statement)
        print(f"\nGenerated SQL:\n{statement}\n")
        rows = run_query(connection, statement)
        return json.dumps(rows, default=str)

    @tool
    def answer_general_question(question: str) -> str:
        """Answer a question that is not about the database.but limit to 5 words"""
        print("\nCalled tool: answer_general_question\n")
        reply = model.invoke(
            "Answer this general question in a short, direct way. max 5 words\n\n"
            f"Question: {question}"
        )
        return reply.content

    @tool
    def answer_Airlines_query():
        """Answer a question about the Airlines."""
        ## place holder for the airlines queries, just all any API which will give airline data
        return "I can answer the airline Queries"

    return [get_database_schema, run_select_query, answer_general_question,answer_Airlines_query]
