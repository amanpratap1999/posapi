from flask import Flask, request, jsonify
from pbkdf2 import PBKDF2
import hashlib
import os
import MySQLdb  # Assuming you have the MySQLdb library installed

app = Flask(__name__)

# Replace 'your_database_config' with your actual MySQL database configuration
db = MySQLdb.connect(host='localhost', user='root', password='', database='ims_db')
cursor = db.cursor()

@app.route('/register_admin', methods=['POST'])
def register_admin():
    try:
        data = request.get_json()

        # Extract registration data
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')

        # Check if the username or email already exists in the database
        cursor.execute("SELECT * FROM user_list WHERE username=%s OR email=%s", (username, email))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({"status": "error", "message": "Username or email already exists"}), 400

        # Hash the password using PBKDF2-HMAC-SHA256
        salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
        password_hash = PBKDF2(hashlib.sha256, password.encode('utf-8'), salt, 600000).hexread(32)

        # Insert the new admin into the user_list table with the 'admin' role
        insert_query = "INSERT INTO user_list (username, password, email, usertype) VALUES (%s, %s, %s, %s)"
        values = (username, password_hash, email, 'admin')
        cursor.execute(insert_query, values)

        # Commit the changes to the database
        db.commit()

        return jsonify({"status": "success", "message": "Admin registered successfully"}), 200

    except Exception as e:
        # Rollback the changes if there is an error
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Run the Flask app on port 8000
    app.run(host='0.0.0.0', port=2000,debug=True)
