"""Answer a question by letting the model call database tools.

The model decides when to read the schema and when to run a SELECT.
main.py still asks for SQL in one prompt. This file does the same job with tools.
"""

import os
import sys

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from db_tools import build_tools
from utility import get_connection

SYSTEM = (
    "You answer questions by calling tools. Never answer before a tool has been called.\n"
    "If the question is about the database, call get_database_schema first, then "
    "call run_select_query with one read-only SELECT, and answer from those rows.\n"
    "If the question is not about the database, call answer_general_question "
    "and give that tool's reply as the answer.\n"
    "Do not reply NOT UNDERSTAND THE QUESTION."
    "if it is related to airlines, call answer_Airlines_query"
)


def ask_with_tools(model, tools, question: str) -> str:
    tool_map = {item.name: item for item in tools}
    bound = model.bind_tools(tools)
    messages = [SystemMessage(SYSTEM), HumanMessage(question)]
    used_tool = False

    for _ in range(6):
        reply = bound.invoke(messages)
        messages.append(reply)
        if not reply.tool_calls:
            if not used_tool:
                return str(tool_map["answer_general_question"].invoke({"question": question}))
            return reply.content or ""
        used_tool = True
        for call in reply.tool_calls:
            try:
                result = tool_map[call["name"]].invoke(call["args"])
            except Exception as error:
                result = f"Tool error: {error}"
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    return "The model kept calling tools without giving an answer."


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found. Check your .env file.")

    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
    connection = get_connection()
    tools = build_tools(connection, model)
    try:
        while True:
            question = " ".join(sys.argv[1:]).strip() or input("Ask a question about the data: ").strip()
            if question == "exit":
                break
            print(ask_with_tools(model, tools, question))
            if len(sys.argv) > 1:
                break
    finally:
        connection.close()


if __name__ == "__main__":
    main()
