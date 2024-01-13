from multiprocessing import connection
from flask import Flask, request, jsonify, make_response
import MySQLdb
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from flask_mysqldb import MySQL
from flask_cors import CORS
from datetime import datetime, timedelta
import re


app = Flask(__name__)

CORS(app)

app.config['SECRET_KEY'] = 'V"}O1,(oWaNnpycz`B_/+\yo'

# Replace 'your_database_config' with your actual MySQL database configuration
db = MySQLdb.connect(host='localhost', user='root', password='', database='ims_db')
cursor = db.cursor()

mysql = MySQL(app)

def is_valid_barcode(barcode):
    # Check if the barcode is valid (alphanumeric with optional special characters) and does not start with zero
    if barcode and barcode[0] == '0':
        return False
    return bool(re.match(r'^[1-9a-zA-Z!@#$%^&*()-_+=~`[\]{}|:;"\',.<>?/\\]+$', barcode))

def verify_token(token):
    try:
        # Decode the token using the secret key
        print("hello")
        jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return True
    except jwt.ExpiredSignatureError:
        return False  # Token has expired
    except jwt.InvalidTokenError:
        return False  # Invalid token

@app.route('/auth_verify', methods=['GET'])
def auth_verify():
    try:

        # Extract the token from the request headers
        token = request.headers.get('Authorization')
        print("Token Verify",token)
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])

        if not token:
            return jsonify({'message': 'Token is missing'}), 401

        if 'usertype' in decoded_token and decoded_token['usertype'] == 'admin':
            return jsonify({'message': 'Admin token is valid','role':'Admin'}), 200
        elif 'usertype' in decoded_token and decoded_token['usertype'] == 'user':
            return jsonify({'message': 'User token is valid','role':'user'}), 200
        else:
            return jsonify({'message': 'Invalid role in token'}), 403

    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 400
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 402


@app.route('/register_admin', methods=['POST'])
def register_admin():
    try:

        data = request.get_json()

        username = data.get('username')
        password = generate_password_hash(data.get('password'), method='pbkdf2:sha256')
        email = data.get('email')

        # Insert the new user into the user table with the 'user' role
        insert_query = "INSERT INTO user_list (username, password, email, usertype) VALUES (%s, %s, %s, %s)"
        values = (username, password, email, 'admin')
        cursor.execute(insert_query, values)

        # Commit the changes to the database
        db.commit()

        return jsonify({"status": "success", "message": "Admin registered successfully"}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401
    except Exception as e:
        # Rollback the changes if there is an error
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM user_list WHERE username=%s", (username,))
        user = cursor.fetchone()

    print("User from database:", user)  # Add this line for debugging

    if user and check_password_hash(user[2], password):
        expiration_time = datetime.utcnow() + timedelta(minutes=10)
        auth_token = jwt.encode(
            {'user_id': user[0], 'usertype': user[3], 'iat': datetime.utcnow(), 'exp': expiration_time},
            app.config['SECRET_KEY'], algorithm='HS256')

        print("Generated token:", auth_token)  # Add this line for debugging

        return jsonify({'status':'success','message': 'Login successful', 'auth_token': auth_token,'usertype': user[3]}), 200
    else:
        return jsonify({'message': 'Invalid credentials'}), 401


@app.route('/register_user', methods=['POST'])
def register_user():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_role = decoded_token.get('usertype', 'user')  # Default to 'user' role if not present

        if user_role != 'admin':
            return jsonify({"status": "error", "message": "Permission denied"}), 403

        # The user making the request is an admin, proceed with registration
        data = request.get_json()

        username = data.get('username')
        password = generate_password_hash(data.get('password'), method='pbkdf2:sha256')  # Hash the password
        email = data.get('email')

        # Insert the new user into the user table with the 'user' role
        insert_query = "INSERT INTO user_list (username, password, email, usertype) VALUES (%s, %s, %s, %s)"
        values = (username, password, email, 'user')
        cursor.execute(insert_query, values)

        # Commit the changes to the database
        db.commit()

        return jsonify({"status": "success", "message": "User registered successfully"}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401
    except Exception as e:
        # Rollback the changes if there is an error
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/add_supplier', methods=['POST'])
def add_supplier():
    print('Request received at /add_supplier')
    try:
        # Get data from the request
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            data = request.json  # Access JSON data
            print(data)

            # Check if the supplier already exists
            existing_query = "SELECT * FROM supplier_list WHERE email = %s"
            cursor.execute(existing_query, (data['email'],))
            existing_supplier = cursor.fetchone()

            print("Existing Supplier:", existing_supplier)

            if existing_supplier:
                return jsonify({"status": "error", "message": "Supplier already exists"}), 400

            # Execute SQL query to insert a new supplier
            insert_query = "INSERT INTO supplier_list (name, address, phone_number, email, city) VALUES (%s, %s, %s, %s, %s)"
            values = (data['name'], data['address'], data['phone_number'], data['email'], data['city'])
            cursor.execute(insert_query, values)

            # Commit the changes to the database
            db.commit()

            return jsonify({"status": "success", "message": "Supplier added successfully"}), 200
    except Exception as e:
        # Rollback the changes if there is an error
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


# Update the get_suppliers route
@app.route('/get_suppliers', methods=['GET'])
def get_suppliers():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            # Execute SQL query to get all suppliers
            query = "SELECT * FROM supplier_list"
            cursor.execute(query)
            suppliers = cursor.fetchall()

            # Convert data to a list of dictionaries
            supplier_list = []
            columns = [col[0] for col in cursor.description]
            for supplier in suppliers:
                supplier_dict = dict(zip(columns, supplier))
                supplier_list.append(supplier_dict)
            print(supplier_list)
            return jsonify({"status": "success", "data": supplier_list}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/add_product', methods=['POST'])
def add_product():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            # Get data from the request
            data = request.json  # Access JSON data

            if not is_valid_barcode(data['barcode']):
                print()
                return jsonify({"status": "error", "message": "Invalid barcode format"}), 300

            # Check if the barcode already exists in the database
            check_query = "SELECT * FROM item_list WHERE barcode = %s"
            cursor.execute(check_query, (data['barcode'],))
            existing_product = cursor.fetchone()

            if existing_product:
                return jsonify({"status": "error", "message": "Product with the given barcode already exists"}), 400

            # Execute SQL query to insert a new product
            insert_query = "INSERT INTO item_list (barcode, itemname, suppliername, stylecode, ARTNo, colour, size, rack, cost) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            values = (
                data['barcode'],
                data['itemname'],
                data['suppliername'],
                data['stylecode'],
                data['ARTNo'],
                data['colour'],
                data['size'],
                data['rack'],
                data['cost']
            )
            cursor.execute(insert_query, values)

            # Commit the changes to the database
            db.commit()

            return jsonify({"status": "success", "message": "Product added successfully"}), 200
    except Exception as e:
        # Rollback the changes if there is an error
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/get_products', methods=['GET'])
def get_products():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            # Execute SQL query to get all products
            query = "SELECT * FROM item_list"
            cursor.execute(query)
            products = cursor.fetchall()

            # Convert data to a list of dictionaries
            item_list = []
            columns = [col[0] for col in cursor.description]
            for product in products:
                product_dict = dict(zip(columns, product))
                item_list.append(product_dict)

            return jsonify({"status": "success", "data": item_list}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/get_product_by_barcode', methods=['GET'])
def get_product_by_barcode():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            barcode = request.args.get('barcode')

            # Execute SQL query to get product details by barcode
            query = f"SELECT suppliername, itemname FROM item_list WHERE barcode = '{barcode}'"
            cursor.execute(query)
            product_details = cursor.fetchone()

            if product_details:
                supplier_name, item_name = product_details
                return jsonify({"status": "success", "supplierName": supplier_name, "itemName": item_name}), 200
            else:
                return jsonify({"status": "error", "message": "Product not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/get_cost_by_barcode', methods=['GET'])
def get_cost_by_barcode():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            barcode = request.args.get('barcode')

            # Execute SQL query to get the cost by barcode
            query = f"SELECT cost FROM item_list WHERE barcode = '{barcode}'"
            cursor.execute(query)
            cost = cursor.fetchone()

            if cost:
                return jsonify({"status": "success", "cost": cost[0]}), 200
            else:
                return jsonify({"status": "error", "message": "Cost not found for the provided barcode"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/add_purchase', methods=['POST'])
def add_purchase():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            data = request.get_json()
            app.logger.info(f"Received data: {data}")

            # Check if 'purchaseList' is in the data
            if 'purchaseList' in data:
                purchase_list = data['purchaseList']

                # Process the purchase list data and insert into 'purchase_list' and 'stock_list'
                for purchase_data in purchase_list:
                    barcode = purchase_data['barcode']
                    supplier_name = purchase_data['supplierName']
                    item_name = purchase_data['itemName']
                    quantity = purchase_data['quantity']
                    cost = purchase_data['cost']
                    total = purchase_data['total']

                    # Example SQL statement to insert data into 'purchase_list' table
                    purchase_sql = "INSERT INTO purchase_list (barcode, supplier_name, item_name, quantity, cost, total) VALUES (%s, %s, %s, %s, %s, %s)"
                    purchase_values = (barcode, supplier_name, item_name, quantity, cost, total)
                    cursor.execute(purchase_sql, purchase_values)

                    # Example SQL statement to update or insert data into 'stock_list' table
                    stock_sql = "INSERT INTO stock_list (barcode, item_name,cost, quantity, status) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE quantity = quantity + %s, status = %s"
                    stock_values = (barcode, item_name, cost, quantity, 1, quantity, 1)
                    cursor.execute(stock_sql, stock_values)

                    db.commit()

                return jsonify({'success': True, 'message': 'Purchase data added successfully'}), 200

            else:
                return jsonify({'success': False, 'message': 'Invalid request format'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 401


@app.route('/get_purchase', methods=['GET'])
def get_purchase():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            # Execute SQL query to get all products
            query = "SELECT * FROM purchase_list"
            cursor.execute(query)
            items = cursor.fetchall()

            # Convert data to a list of dictionaries
            purchase_list = []
            columns = [col[0] for col in cursor.description]
            for product in items:
                product_dict = dict(zip(columns, product))
                purchase_list.append(product_dict)

            return jsonify({"status": "success", "data": purchase_list}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/add_sale', methods=['POST'])
def add_sale():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            data = request.get_json()
            app.logger.info(f"Received data: {data}")

            # Check if 'saleList' is in the data
            if 'saleList' in data:
                sale_list = data['saleList']

                # Process the sale list data and insert into 'sale_list' and update 'stock_list'
                for sale_data in sale_list:
                    barcode = sale_data['barcode']
                    customer_name = sale_data['customerName']
                    item_name = sale_data['itemName']
                    quantity = sale_data['quantity']
                    cost = sale_data['cost']
                    total = sale_data['total']

                    # Example SQL statement to insert data into 'sale_list' table
                    sale_sql = "INSERT INTO sale_list (barcode, customer_name, item_name, quantity, cost, total) VALUES (%s, %s, %s, %s, %s, %s)"
                    sale_values = (barcode, customer_name, item_name, quantity, cost, total)
                    cursor.execute(sale_sql, sale_values)

                    stock_sql = "INSERT INTO stock_list (barcode, item_name,cost, quantity, status) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE quantity = quantity + %s, status = %s"
                    stock_values = (barcode, item_name, cost, quantity, 2, quantity, 2)
                    cursor.execute(stock_sql, stock_values)

                    db.commit()

                return jsonify({'success': True, 'message': 'Sale data added successfully'}), 200

            else:
                return jsonify({'success': False, 'message': 'Invalid request format'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 401


@app.route('/get_sale', methods=['GET'])
def get_sale():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            # Execute SQL query to get all products
            query = "SELECT * FROM sale_list"
            cursor.execute(query)
            items = cursor.fetchall()

            # Convert data to a list of dictionaries
            purchase_list = []
            columns = [col[0] for col in cursor.description]
            for product in items:
                product_dict = dict(zip(columns, product))
                purchase_list.append(product_dict)

            return jsonify({"status": "success", "data": purchase_list}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/add_purchase_return', methods=['POST'])
def add_purchase_return():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            data = request.get_json()
            app.logger.info(f"Received data: {data}")

            # Check if 'saleList' is in the data
            if 'saleList' in data:
                sale_list = data['saleList']

                # Process the sale list data and insert into 'sale_list' and update 'stock_list'
                for sale_data in sale_list:
                    barcode = sale_data['barcode']
                    customer_name = sale_data['customerName']
                    item_name = sale_data['itemName']
                    quantity = sale_data['quantity']
                    cost = sale_data['cost']
                    total = sale_data['total']

                    # Example SQL statement to insert data into 'sale_list' table
                    sale_sql = "INSERT INTO return_list (barcode, customer_name, item_name, quantity, cost, total,status) VALUES (%s, %s, %s, %s, %s, %s,%s)"
                    sale_values = (barcode, customer_name, item_name, quantity, cost, total, 1)
                    cursor.execute(sale_sql, sale_values)

                    stock_sql = "INSERT INTO stock_list (barcode, item_name,cost, quantity, status) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE quantity = quantity + %s, status = %s"
                    stock_values = (barcode, item_name, cost, quantity, 2, quantity, 2)
                    cursor.execute(stock_sql, stock_values)

                    db.commit()

                return jsonify({'success': True, 'message': 'Sale data added successfully'}), 200

            else:
                return jsonify({'success': False, 'message': 'Invalid request format'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 401


@app.route('/add_sale_return', methods=['POST'])
def add_sale_return():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            data = request.get_json()
            app.logger.info(f"Received data: {data}")

            # Check if 'saleList' is in the data
            if 'saleList' in data:
                sale_list = data['saleList']

                # Process the sale list data and insert into 'sale_list' and update 'stock_list'
                for sale_data in sale_list:
                    barcode = sale_data['barcode']
                    customer_name = sale_data['customerName']
                    item_name = sale_data['itemName']
                    quantity = sale_data['quantity']
                    cost = sale_data['cost']
                    total = sale_data['total']

                    # Example SQL statement to insert data into 'sale_list' table
                    sale_sql = "INSERT INTO return_list (barcode, customer_name, item_name, quantity, cost, total,status) VALUES (%s, %s, %s, %s, %s, %s,%s)"
                    sale_values = (barcode, customer_name, item_name, quantity, cost, total, 2)
                    cursor.execute(sale_sql, sale_values)

                    stock_sql = "INSERT INTO stock_list (barcode, item_name,cost, quantity, status) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE quantity = quantity + %s, status = %s"
                    stock_values = (barcode, item_name, cost, quantity, 1, quantity, 1)
                    cursor.execute(stock_sql, stock_values)

                    db.commit()

                return jsonify({'success': True, 'message': 'Sale data added successfully'}), 200

        else:
            return jsonify({'success': False, 'message': 'Invalid request format'}), 400

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 401

    # @app.route('/get_stock', methods=['GET'])


# def get_stock():
#     try:
#         cursor = db.cursor()
#         cursor.execute("SELECT barcode, item_name,cost, SUM(CASE WHEN status = 1 THEN quantity ELSE -quantity END) as net_quantity FROM stock_list GROUP BY barcode, item_name")
#         data = cursor.fetchall()

#         if data:
#             columns = [col[0] for col in cursor.description]
#             result = [dict(zip(columns, row)) for row in data]
#             return jsonify(result)
#         else:
#             return jsonify({'message': 'No data found.'}), 404

#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

@app.route('/get_stock', methods=['GET'])
def get_stock():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
            # Execute SQL query to get all products
            query = "SELECT barcode, item_name,cost, SUM(CASE WHEN status = 1 THEN quantity ELSE -quantity END) as net_quantity FROM stock_list GROUP BY barcode, item_name"
            cursor.execute(query)
            items = cursor.fetchall()

            # Convert data to a list of dictionaries
            purchase_list = []
            columns = [col[0] for col in cursor.description]
            for product in items:
                product_dict = dict(zip(columns, product))
                purchase_list.append(product_dict)

            return jsonify({"status": "success", "data": purchase_list}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get_total', methods=['GET'])
def get_total():
   # cur = mysql.connection.cursor()

    # Calculate total sales
    cursor.execute("SELECT SUM(total) FROM sale_list")
    total_sales = cursor.fetchone()[0] or 0

    # Calculate total purchases
    cursor.execute("SELECT SUM(total) FROM purchase_list")
    total_purchases = cursor.fetchone()[0] or 0

    # Calculate total sales returns where status=1
    cursor.execute("SELECT SUM(total) FROM return_list WHERE status = 1")
    total_sale_returns = cursor.fetchone()[0] or 0

    #cursor.close()

    return jsonify({
        'total_sales': total_sales,
        'total_purchases': total_purchases,
        'total_sale_returns': total_sale_returns
    })

@app.route('/get_user', methods=['GET'])
def get_user():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
        # Execute SQL query to get all products
            query = "SELECT * FROM user_list"
            cursor.execute(query)
            items = cursor.fetchall()

            # Convert data to a list of dictionaries
            purchase_list = []
            columns = [col[0] for col in cursor.description]
            for product in items:
                product_dict = dict(zip(columns, product))
                purchase_list.append(product_dict)

            return jsonify({"status": "success", "data": purchase_list}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/get_return', methods=['GET'])
def get_return():
    try:
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 440

        if not verify_token(token):
            return jsonify({'error': 'Invalid token'}), 401

        if verify_token(token):
        # Execute SQL query to get all products
            query = "SELECT * FROM return_list"
            cursor.execute(query)
            items = cursor.fetchall()

            # Convert data to a list of dictionaries
            purchase_list = []
            columns = [col[0] for col in cursor.description]
            for product in items:
                product_dict = dict(zip(columns, product))
                purchase_list.append(product_dict)

            return jsonify({"status": "success", "data": purchase_list}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    # Run the Flask app on port 8000
    app.run(host='0.0.0.0', port=8000,debug=True)
