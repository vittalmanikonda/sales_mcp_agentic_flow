import mysql.connector
from mysql.connector import Error

def fetch_sales_data():
    connection = None
    try:
        # Establish connection to your Docker MySQL setup
        connection = mysql.connector.connect(
            host='127.0.0.1',            # Use localhost or 127.0.0.1
            port=3306,
            database='ecommerce_sales',   # The database we created
            user='root',
            password='mysql'      # Your root password
        )

        if connection.is_connected():
            print("--- Connected to Docker MySQL Successfully ---\n")
            
            cursor = connection.cursor(dictionary=True) # Returns rows as dictionaries (great for AI parsing)
            
            # Relational query matching customer orders to products
            query = """
            SELECT 
                CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
                p.product_name,
                oi.quantity,
                (oi.quantity * oi.unit_price) AS total_spend
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN products p ON oi.product_id = p.product_id
            """
            
            cursor.execute(query)
            records = cursor.fetchall()
            
            # Print table headers
            print(f"{'Customer Name':<20} {'Product':<20} {'Qty':<5} {'Total Spend':<10}")
            print("-" * 60)
            
            # Process and print out the results
            for row in records:
                print(f"{row['customer_name']:<20} {row['product_name']:<20} {row['quantity']:<5} ${row['total_spend']:<10.2f}")
                
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        
    finally:
        # Always close the connection safely
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("\n--- MySQL connection closed ---")

if __name__ == "__main__":
    fetch_sales_data()
