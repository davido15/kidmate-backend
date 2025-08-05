import pymysql

# Database connection
connection = pymysql.connect(
    host='localhost',
    port=8889,
    user='root',
    password='root',
    database='kidmate_db'
)

try:
    with connection.cursor() as cursor:
        # Check users table
        cursor.execute("SELECT id, name, email, phone FROM users LIMIT 5")
        users = cursor.fetchall()
        
        print("👥 Users in database:")
        for user in users:
            print(f"  - ID: {user[0]}, Name: {user[1]}, Email: {user[2]}, Phone: {user[3]}")
            
        # Check parents table
        cursor.execute("SELECT id, name, user_email FROM parents LIMIT 5")
        parents = cursor.fetchall()
        
        print("\n👨‍👩‍👧‍👦 Parents in database:")
        for parent in parents:
            print(f"  - ID: {parent[0]}, Name: {parent[1]}, User Email: {parent[2]}")
            
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    connection.close()
    print("🔌 Database connection closed") 