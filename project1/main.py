import json
import os
import sys

from langchain_openai import ChatOpenAI

from utility import clean_sql, ensure_read_only, get_connection, run_query

TABLE_METADATA = """
customers(customer_id int, first_name varchar(50), last_name varchar(50), email varchar(100), country varchar(50), signup_date date)
order_items(item_id int, order_id int, product_id int, quantity int, unit_price decimal(10,2))
orders(order_id int, customer_id int, order_date date, order_status varchar(20))
products(product_id int, product_name varchar(100), category varchar(50), price decimal(10,2), stock_quantity int)
sales_targets(target_id int, category varchar(50), target_year int, target_month int, monthly_target_revenue decimal(12,2))
"""


def ask_database(model, connection, question: str) -> str:
    sql_prompt = (
        "You are a MySQL expert. Write a read-only SELECT that answers the user's question "
        "using only the tables and columns in the schema below.\n"
        "Interpret the question yourself: decide which tables to join, how to aggregate, "
        "and how to filter. Return only the SQL statement, no explanation, no markdown. If you can't interpript then return NOT UNDERSTAND THE QUESTION\n\n"
        f"Schema:\n{TABLE_METADATA}\n"
        f"Question: {question}"
    )
    sql = clean_sql(model.invoke(sql_prompt).content)
    if sql == "NOT UNDERSTAND THE QUESTION":
        return "NOT UNDERSTAND THE QUESTION"
    print(f"\nGenerated SQL:\n{sql}\n")

    ensure_read_only(sql)
    rows = run_query(connection, sql)

    answer_prompt = (
        "Answer the question using only the query result below. "
        "If the result is empty, say no matching data was found.\n\n"
        f"Question: {question}\n"
        f"SQL: {sql}\n"
        f"Result (JSON): {json.dumps(rows, default=str)}"
    )

    #print(answer_prompt)

    return model.invoke(answer_prompt).content


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found. Check your .env file.")
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)
    connection = get_connection()
    try:
        while True:
            question = " ".join(sys.argv[1:]).strip() or input("Ask a question about the data: ").strip()
            if question == "exit":
                break
            print(ask_database(model, connection, question))
            if len(sys.argv) > 1:
                break
    finally:
        connection.close()

if __name__ == "__main__":
    main()
