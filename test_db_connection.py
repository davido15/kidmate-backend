#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify database connection
"""
import pymysql
import os
from urllib.parse import quote_plus

def test_connection(host, port, user, password, database=None):
    """Test MySQL connection with given parameters"""
    try:
        if database:
            print("Testing connection to {}:{} with user {} to database {}...".format(host, port, user, database))
        else:
            print("Testing connection to {}:{} with user {} (no database)...".format(host, port, user))
        
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=10
        )
        print("SUCCESS: Connection successful!")
        connection.close()
        return True
    except Exception as e:
        print("FAILED: Connection failed: {}".format(e))
        return False

def main():
    # Connection parameters
    host = '109.106.246.51'
    user = 'u632760522_kidmate'
    password = 'mIN?mQ]S5'
    database = 'u632760522_kidmate'
    
    print("Testing database connections...")
    print("=" * 50)
    
    # Test 1: Connect without database name (just to test authentication)
    print("\n--- Test 1: Connect without database ---")
    test_connection(host, 3306, user, password, None)
    
    # Test 2: Try different password variations
    print("\n--- Test 2: Try different password encodings ---")
    
    # Original password
    test_connection(host, 3306, user, password, database)
    
    # URL-encoded password
    encoded_password = quote_plus(password)
    test_connection(host, 3306, user, encoded_password, database)
    
    # Try with single quotes around password
    quoted_password = "'" + password + "'"
    test_connection(host, 3306, user, quoted_password, database)
    
    # Test 3: Try different user formats
    print("\n--- Test 3: Try different user formats ---")
    
    # Try with host specification
    user_with_host = user + '@' + host
    test_connection(host, 3306, user_with_host, password, database)
    
    # Try with localhost
    user_with_localhost = user + '@localhost'
    test_connection(host, 3306, user_with_localhost, password, database)

if __name__ == "__main__":
    main() 