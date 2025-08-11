import sqlite3
import sys

def migrate_database():
    db_path = 'openrouter_proxy.db'
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of columns in api_keys table
    cursor.execute("PRAGMA table_info(api_keys)")
    columns = [column[1] for column in cursor.fetchall()]
    
    print(f"Existing columns in 'api_keys': {columns}")

    # Add 'daily_limit' column if it doesn't exist
    if 'daily_limit' not in columns:
        print("Adding 'daily_limit' column with default value 500...")
        try:
            cursor.execute("ALTER TABLE api_keys ADD COLUMN daily_limit INTEGER DEFAULT 500")
            print("'daily_limit' column added successfully.")
        except sqlite3.OperationalError as e:
            print(f"Error adding 'daily_limit' column: {e}", file=sys.stderr)

    # Add 'daily_usage' column if it doesn't exist
    if 'daily_usage' not in columns:
        print("Adding 'daily_usage' column with default value 0...")
        try:
            cursor.execute("ALTER TABLE api_keys ADD COLUMN daily_usage INTEGER DEFAULT 0")
            print("'daily_usage' column added successfully.")
        except sqlite3.OperationalError as e:
            print(f"Error adding 'daily_usage' column: {e}", file=sys.stderr)

    # Add 'last_reset_time' column if it doesn't exist
    if 'last_reset_time' not in columns:
        print("Adding 'last_reset_time' column...")
        try:
            cursor.execute("ALTER TABLE api_keys ADD COLUMN last_reset_time TIMESTAMP")
            print("'last_reset_time' column added successfully.")
        except sqlite3.OperationalError as e:
            print(f"Error adding 'last_reset_time' column: {e}", file=sys.stderr)
    
    # Set default value for existing rows where daily_limit might be NULL
    print("Updating existing NULL 'daily_limit' values to 500...")
    try:
        cursor.execute("UPDATE api_keys SET daily_limit = 500 WHERE daily_limit IS NULL")
        print(f"{cursor.rowcount} rows updated.")
    except sqlite3.OperationalError as e:
        print(f"Error updating NULL 'daily_limit' values: {e}", file=sys.stderr)


    conn.commit()
    conn.close()
    print("Database migration check completed.")

if __name__ == "__main__":
    migrate_database()