#!/usr/bin/env python3
"""
Test script to verify MySQL database connection through ngrok
"""

import pymysql
import sys

def test_mysql_connection():
    """Test connection to MySQL database via ngrok"""
    
    # Connection parameters from your connection string
    host = '4.tcp.eu.ngrok.io'
    port = 16396
    user = 'root'
    password = 'root'
    database = 'kidmate_db'
    
    try:
        print("Attempting to connect to MySQL via ngrok...")
        print("   Host: {}".format(host))
        print("   Port: {}".format(port))
        print("   Database: {}".format(database))
        print("   User: {}".format(user))
        
        # Establish connection
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=10
        )
        
        print("SUCCESS: Connected to MySQL database!")
        
        # Test a simple query
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print("MySQL Version: {}".format(version[0]))
            
            # Test if we can see tables
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print("Found {} tables:".format(len(tables)))
            for table in tables:
                print("   - {}".format(table[0]))
        
        connection.close()
        print("Connection closed successfully")
        return True
        
    except pymysql.Error as e:
        print(f"MySQL Error: {e}")
        return False
    except Exception as e:
        print(f"General Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing MySQL Connection via ngrok...")
    success = test_mysql_connection()
    
    if success:
        print("\nDatabase connection test PASSED!")
        sys.exit(0)
    else:
        print("\nDatabase connection test FAILED!")
        sys.exit(1) 