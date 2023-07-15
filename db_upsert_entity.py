import psycopg2
from dateutil import parser
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os


# load the environment variables from the .env file
load_dotenv()

user=os.getenv('PGSQL_USER') 
password = os.getenv('PGSQL_PWD')

def create_connection():
    conn = psycopg2.connect(
        host='localhost',  # replace with your server host if different
        database='russian_poetry',  # replace with your database name
        user=user,  # replace with your username
        password=password  # replace with your password
    )
    return conn

def add_entry(text, entity, translation, author, link_to_source, rating, id, date_of_usage):

    if isinstance(date_of_usage, str):
        date_of_usage = parser.parse(date_of_usage)
    elif not isinstance(date_of_usage, datetime):
        raise ValueError("date_of_usage must be a string or datetime object")

    
    # Creating the connection
    conn = create_connection()
    
    # Creating the cursor object
    cursor = conn.cursor()
    
    # SQL query to add an entry to the database
    query = """
    INSERT INTO poems (id, text, entity, translation, author, link_to_source, rating, date_of_usage)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE
    SET text = excluded.text, 
        entity = excluded.entity, 
        translation = excluded.translation, 
        author = excluded.author, 
        link_to_source = excluded.link_to_source,
        rating = excluded.rating, 
        date_of_usage = excluded.date_of_usage;

    """
    
    # Execute the query and commit changes
    try:
        cursor.execute(query, (id, text, entity, translation, author, link_to_source, rating, date_of_usage))
        conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        # Close the connection
        cursor.close()
        conn.close()


def is_id_exist(id):
    # Creating the connection
    conn = create_connection()
    
    # Creating the cursor object
    cursor = conn.cursor()
    
    # SQL query to check if id exists in the database
    query = "SELECT EXISTS(SELECT 1 FROM poems WHERE id=%s);"
    
    # Execute the query and fetch result
    try:
        cursor.execute(query, (id,))
        exists = cursor.fetchone()[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        exists = False
    finally:
        # Close the connection
        cursor.close()
        conn.close()
    
    return exists

def get_poems():
    # Creating the connection
    conn = create_connection()

    # Creating the cursor object
    cursor = conn.cursor()

    # Get the datetime for one month ago
    one_month_ago = datetime.now() - timedelta(days=30)

    # SQL query to get all rows from the last month
    query = "SELECT * FROM poems WHERE date_of_usage < %s;"

    # Execute the query and fetch all results
    try:
        cursor.execute(query, (one_month_ago,))
        rows = cursor.fetchall()  # Fetch all rows
        columns = [desc[0] for desc in cursor.description]  # Get column names
        result = [dict(zip(columns, row)) for row in rows]  # Create a list of dictionaries
    except Exception as e:
        print(f"An error occurred: {e}")
        result = []
    finally:
        # Close the connection
        cursor.close()
        conn.close()

    return result
