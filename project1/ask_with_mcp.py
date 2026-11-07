"""Answer a question the same way as main.py, but run the SQL through an MCP server.

Running this file starts a second process, this file with --server. That process is
the MCP server. Its only tool runs one read-only SELECT. The model still receives
the table metadata in the prompt and writes the query.
"""

import asyncio
import json
import os
import sys

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.mcpserver import MCPServer

from utility import clean_sql, ensure_read_only, get_connection, run_query

server = MCPServer("ecommerce-sales")


@server.tool()
def run_select_query(sql: str) -> str:
    """Run one read-only SELECT against ecommerce_sales and return the rows as JSON."""
    statement = clean_sql(sql)
    ensure_read_only(statement)
    connection = get_connection()
    try:
        rows = run_query(connection, statement)
    finally:
        connection.close()
    return json.dumps(rows, default=str)


@server.tool()
def answer_general_question(question: str) -> str:
    """Answer a question that is not about the ecommerce database."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "OPENAI_API_KEY is not set."
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
    reply = model.invoke(
        "Answer this general question in a short, direct way.\n\n"
        f"Question: {question}"
    )
    return reply.content

@server.tool()
def answer_Airline_reservations(question: str) -> str:
    """Answer questions about airline reservations, flights, and bookings."""
    return "it is for airlines reservations"
    
def serve() -> None:
    import logging

    logging.getLogger("mysql.connector").setLevel(logging.WARNING)
    server.run(transport="stdio")


def tool_text(result) -> str:
    parts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) if parts else str(result)


async def call_matching_tool(model, session: ClientSession, question: str) -> str:
    """Let the model pick a non-SQL MCP tool from the server's tool list."""
    listed = await session.list_tools()
    choices = [tool for tool in listed.tools if tool.name != "run_select_query"]
    bound = model.bind_tools(
        [
            {
                "name": tool.name,
                "description": tool.description or tool.name,
                "parameters": tool.input_schema.model_dump(by_alias=True, exclude_none=True)
                if hasattr(tool.input_schema, "model_dump")
                else tool.input_schema,
            }
            for tool in choices
        ]
    )
    reply = bound.invoke(
        "Call the one tool whose description matches this question.\n"
        f"Question: {question}"
    )
    if reply.tool_calls:
        call = reply.tool_calls[0]
        name = call["name"]
        args = call.get("args") or {"question": question}
    else:
        name = "answer_general_question"
        args = {"question": question}
    if "question" not in args:
        args["question"] = question
    print(f"\nCalled MCP tool: {name}\n")
    result = await session.call_tool(name, args)
    return tool_text(result)


async def ask_database(model, session: ClientSession, question: str) -> str:
    from main import TABLE_METADATA

    sql_prompt = (
        "You are a MySQL expert. Write a read-only SELECT that answers the user's question "
        "using only the tables and columns in the schema below.\n"
        "Interpret the question yourself: decide which tables to join, how to aggregate, "
        "and how to filter. Return only the SQL statement, no explanation, no markdown. If you can't interpript then return NOT UNDERSTAND THE QUESTION\n\n"
        f"Schema:\n{TABLE_METADATA}\n"
        f"Question: {question}"
    )
    sql = clean_sql(model.invoke(sql_prompt).content)
    if sql == "NOT UNDERSTAND THE QUESTION" or not sql.lower().startswith("select"):
        return await call_matching_tool(model, session, question)
    print(f"\nGenerated SQL:\n{sql}\n")

    result = await session.call_tool("run_select_query", {"sql": sql})
    rows_json = tool_text(result)
    if getattr(result, "isError", False):
        return f"Query failed: {rows_json}"

    answer_prompt = (
        "Answer the question using only the query result below. "
        "If the result is empty, say no matching data was found.\n\n"
        f"Question: {question}\n"
        f"SQL: {sql}\n"
        f"Result (JSON): {rows_json}"
    )
    return model.invoke(answer_prompt).content


async def client() -> None:
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found. Check your .env file.")
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)

    here = os.path.dirname(os.path.abspath(__file__))
    params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.abspath(__file__), "--server"],
        cwd=here,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            while True:
                question = " ".join(sys.argv[1:]).strip() or input("Ask a question about the data: ").strip()
                if question == "exit":
                    break
                print(await ask_database(model, session, question))
                if len(sys.argv) > 1:
                    break


if __name__ == "__main__":
    if "--server" in sys.argv:
        serve()
    else:
        asyncio.run(client())
