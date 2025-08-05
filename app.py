import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_migrate import Migrate
import requests
import uuid
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@localhost:8889/kidmate_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads/images'

# JWT Configuration
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
from models import PickupJourney, db, User, Parent, Kid, PickupPerson, Payment, Attendance, Complaint  # Import db from models.py
db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

# --- Routes ---


SEQUENTIAL_STATUS_FLOW = {
    None: 'pending',
    'pending': 'picked',
    'picked': 'dropoff',
    'dropoff': 'completed'
}

FINAL_STATUSES = ['completed', 'cancelled']

@app.route('/')
def home():
    return jsonify({'message': 'Hello World'})

@app.route('/test')
def test():
    return jsonify({'message': 'Backend is working', 'timestamp': datetime.now().isoformat()})



@app.route('/api/register', methods=['POST'])
def register_user():
    try:
        # Log the incoming request
        print("=== REGISTER API REQUEST ===")
        print(f"Request Method: {request.method}")
        print(f"Request URL: {request.url}")
        print(f"Request Headers: {dict(request.headers)}")
        print(f"Request IP: {request.remote_addr}")
        print(f"Request User Agent: {request.user_agent}")
        
        data = request.get_json()
        print(f"Request Body: {data}")
        print("==========================")

        phone = data.get('phone')
        password = data.get('password')
        name = data.get('name')
        email = data.get('email')
        role = data.get('role', 'Parent')

        print(f"Extracted Data:")
        print(f"  - Phone: {phone}")
        print(f"  - Name: {name}")
        print(f"  - Email: {email}")
        print(f"  - Role: {role}")
        print(f"  - Password: {'*' * len(password) if password else 'None'}")

        # Validate required fields
        if not phone or not password:
            print("❌ VALIDATION ERROR: Phone and password are required")
            return jsonify({"msg": "Phone and password are required"}), 400

        # Check if user already exists by phone
        existing_user = User.query.filter_by(phone=phone).first()
        if existing_user:
            print(f"❌ USER EXISTS ERROR: User with phone {phone} already exists")
            return jsonify({"msg": "User already exists"}), 400

        print("✅ Validation passed, creating new user...")

        # Create new user
        user = User(name=name, phone=phone, email=email)
        user.set_password(password)  # Make sure this hashes the password internally
        user.set_role(role)          # Assign role if you have roles implemented

        print(f"✅ User object created with ID: {user.id}")

        # Save user to DB
        print("💾 Saving user to database...")
        db.session.add(user)
        db.session.commit()
        print(f"✅ User saved successfully with ID: {user.id}")

        # Create JWT token with user id as identity
        print("🔑 Creating JWT token...")
        token = create_access_token(identity={"id": user.id, "name": user.name, "role": user.role})
        print(f"✅ JWT token created for user: {user.name}")
        
        response_data = {"token": token}
        print(f"📤 Sending response: {response_data}")
        print("=== REGISTER API REQUEST COMPLETED ===")
        
        return jsonify(response_data), 201
        
    except Exception as e:
        print(f"❌ ERROR in register_user: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route('/update_status', methods=['POST'])
def update_status():
    data = request.get_json()

    # Log the incoming request data
    print("/update_status request data:", data)

    required_fields = ['pickup_id', 'parent_id', 'child_id', 'pickup_person_id', 'status']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    new_status = data['status']
    pickup_id = data['pickup_id']

    # Get the latest status for this pickup_id
    latest_entry = (PickupJourney.query
                    .filter_by(pickup_id=pickup_id)
                    .order_by(PickupJourney.timestamp.desc())
                    .first())

    previous_status = latest_entry.status if latest_entry else None

    # Log the status transition
    print(f"Previous status: {previous_status}, New status: {new_status}")

    if new_status == 'cancelled':
        if previous_status == 'completed':
            return jsonify({'error': 'Cannot cancel a completed journey'}), 400
    elif previous_status in FINAL_STATUSES:
        return jsonify({'error': f'Cannot update status after journey is {previous_status}'}), 400
    elif SEQUENTIAL_STATUS_FLOW.get(previous_status) != new_status:
        expected_next = SEQUENTIAL_STATUS_FLOW.get(previous_status)
        return jsonify({
            'error': f'Invalid status transition. Current: {previous_status or "none"}, expected: {expected_next}, received: {new_status}'
        }), 400

    # Log status
    journey = PickupJourney(
        pickup_id=pickup_id,
        parent_id=data['parent_id'],
        child_id=data['child_id'],
        pickup_person_id=data['pickup_person_id'],
        status=new_status
    )

    db.session.add(journey)
    db.session.commit()

    return jsonify({'message': f'Status updated to "{new_status}" for pickup {pickup_id}'}), 200



@app.route('/api/login', methods=['POST'])
def login_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    # Create token with email as identity (string)
    token = create_access_token(identity=user.email)
    return jsonify({
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    }), 200


@app.route('/api/me', methods=['GET'])
@jwt_required()
def get_user_info():
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get parent information if user is linked to a parent
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        parent_info = None
        if parent:
            parent_info = {
                'id': parent.id,
                'name': parent.name,
                'phone': parent.phone,
                'address': parent.address,
                'occupation': parent.occupation,
                'relationship': parent.relationship
            }
        
        return jsonify({
            "success": True,
            "user": {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'role': user.role,
                'image': user.image
            },
            "parent": parent_info
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def save_image(file):
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return file_path
    return None

@app.route('/api/add-parent', methods=['POST'])
def register_parent():
    data = request.form
    image_path = save_image(request.files.get('image'))

    parent = Parent(name=data['name'], phone=data['phone'], image=image_path)
    db.session.add(parent)
    db.session.commit()
    return jsonify({'parent_id': parent.id, 'image': image_path})

@app.route('/api/link-parent-to-user', methods=['POST'])
def link_parent_to_user():
    """Admin endpoint to link a parent to a user via email"""
    try:
        data = request.get_json()
        parent_id = data.get('parent_id')
        user_email = data.get('user_email')
        
        if not parent_id or not user_email:
            return jsonify({"error": "parent_id and user_email are required"}), 400
        
        # Check if parent exists
        parent = Parent.query.get(parent_id)
        if not parent:
            return jsonify({"error": "Parent not found"}), 404
        
        # Check if user exists
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Link parent to user
        parent.user_email = user_email
        db.session.commit()
        
        return jsonify({
            "message": f"Parent {parent.name} linked to user {user.name} ({user_email})",
            "parent_id": parent.id,
            "user_email": user_email
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-unlinked-parents', methods=['GET'])
def get_unlinked_parents():
    """Get all parents that are not linked to any user"""
    try:
        unlinked_parents = Parent.query.filter_by(user_email=None).all()
        parents_data = []
        
        for parent in unlinked_parents:
            parents_data.append({
                'id': parent.id,
                'name': parent.name,
                'phone': parent.phone,
                'image': parent.image
            })
        
        return jsonify({"unlinked_parents": parents_data}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-users', methods=['GET'])
def get_users():
    """Get all users for admin to link with parents"""
    try:
        users = User.query.all()
        users_data = []
        
        for user in users:
            users_data.append({
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'role': user.role
            })
        
        return jsonify({"users": users_data}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/add-kid', methods=['POST'])
def add_kid():
    data = request.form
    image_path = save_image(request.files.get('image'))

    kid = Kid(name=data['name'], parent_id=data['parent_id'], image=image_path)
    db.session.add(kid)
    db.session.commit()
    return jsonify({'kid_id': kid.id, 'image': image_path})

@app.route('/api/assign-pickup', methods=['POST'])
@jwt_required()
def assign_pickup():
    try:
        data = request.form
        image_file = request.files.get('image')

        app.logger.debug(f"Received form data: {data}")
        app.logger.debug(f"Received image file: {image_file}")

        # Assign defaults
        name = data.get('name', 'Unknown Person')
        pickup_id = data.get('pickup_id', '1234')
        kid_id = data.get('kid_id', '5')

        image_path = save_image(image_file)

        pickup_uuid = str(uuid.uuid4())

        person = PickupPerson(
            uuid=pickup_uuid,
            name=name,
            pickup_id=pickup_id,
            kid_id=kid_id,
            image=image_path
        )

        db.session.add(person)
        db.session.commit()

        pickup_url = f"https://5d4c3ae2bc3e.ngrok-free.app/pickup/{pickup_uuid}"

        app.logger.info(f"Pickup person added with UUID: {pickup_uuid}")
        return jsonify({
            'message': 'Pickup person assigned successfully',
            'pickup_url': pickup_url
        }), 200

    except Exception as e:
        app.logger.exception("Error assigning pickup:")
        return jsonify({'error': str(e)}), 500

@app.route('/api/register-token', methods=['POST'])
def register_token():
    data = request.get_json()
    parent = Parent.query.get(data['parent_id'])
    if parent:
        parent.push_token = data['token']
        db.session.commit()
        return jsonify({'message': 'Token registered'})
    return jsonify({'message': 'Parent not found'}), 404

@app.route('/api/scan-pickup', methods=['POST'])
def scan_pickup():
    data = request.get_json()
    person = PickupPerson.query.filter_by(pickup_id=data['pickup_id']).first()

    if not person:
        return jsonify({'message': 'Invalid pickup ID'}), 404

    kid = Kid.query.get(person.kid_id)
    parent = Parent.query.get(kid.parent_id)

    if parent and parent.push_token:
        send_notification(parent.push_token, f"{person.name} has {data['status']} for {kid.name}.")
        return jsonify({'message': f'{data["status"].capitalize()} notification sent.'})
    return jsonify({'message': 'Parent or token not found'}), 404

@app.route('/get_status', methods=['GET'])
def get_status():
    pickup_id = request.args.get('pickup_id')
    if not pickup_id:
        return jsonify({'error': 'pickup_id is required'}), 400

    latest_entry = (PickupJourney.query
                    .filter_by(pickup_id=pickup_id)
                    .order_by(PickupJourney.timestamp.desc())
                    .first())
    if not latest_entry:
        return jsonify({'status': None}), 200

    return jsonify({
        'status': latest_entry.status,
        'timestamp': latest_entry.timestamp.isoformat() if latest_entry.timestamp else None
    }), 200

@app.route('/get_all_journeys', methods=['GET'])
def get_all_journeys():
    try:
        # Get all unique pickup IDs with their latest status
        journeys = []
        unique_pickup_ids = db.session.query(PickupJourney.pickup_id).distinct().all()
        
        for (pickup_id,) in unique_pickup_ids:
            latest_journey = (PickupJourney.query
                             .filter_by(pickup_id=pickup_id)
                             .order_by(PickupJourney.timestamp.desc())
                             .first())
            
            if latest_journey:
                journeys.append({
                    'pickup_id': latest_journey.pickup_id,
                    'status': latest_journey.status,
                    'timestamp': latest_journey.timestamp.isoformat() if latest_journey.timestamp else None,
                    'parent_id': latest_journey.parent_id,
                    'child_id': latest_journey.child_id,
                    'pickup_person_id': latest_journey.pickup_person_id
                })
        
        return jsonify({'journeys': journeys}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_user_journeys', methods=['GET'])
def get_user_journeys():
    try:
        # For now, return all journeys since we're not using authentication
        print("Getting all journeys (no authentication required)")
        
        # Get all journeys
        journeys = []
        all_journeys = PickupJourney.query.order_by(PickupJourney.timestamp.desc()).all()
        
        print(f"Found {len(all_journeys)} total journeys")
        
        # Group by pickup_id and get latest status for each
        pickup_groups = {}
        for journey in all_journeys:
            if journey.pickup_id not in pickup_groups:
                pickup_groups[journey.pickup_id] = journey
            elif journey.timestamp > pickup_groups[journey.pickup_id].timestamp:
                pickup_groups[journey.pickup_id] = journey
        
        for pickup_id, latest_journey in pickup_groups.items():
            journeys.append({
                'pickup_id': latest_journey.pickup_id,
                'status': latest_journey.status,
                'timestamp': latest_journey.timestamp.isoformat() if latest_journey.timestamp else None,
                'parent_id': latest_journey.parent_id,
                'child_id': latest_journey.child_id,
                'pickup_person_id': latest_journey.pickup_person_id
            })
        
        return jsonify({'journeys': journeys}), 200
    except Exception as e:
        print(f"Error in get_user_journeys: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_dummy_payments', methods=['POST'])
def add_dummy_payments():
    try:
        # Create dummy payment data
        dummy_payments = [
            {
                'payment_id': str(uuid.uuid4()),
                'parent_id': 'parent-001',
                'child_id': 'child-001',
                'amount': 25.00,
                'currency': 'USD',
                'status': 'completed',
                'payment_method': 'card',
                'description': 'School pickup service - Week 1',
                'journey_date': datetime.now().date()
            },
            {
                'payment_id': str(uuid.uuid4()),
                'parent_id': 'parent-001',
                'child_id': 'child-001',
                'amount': 30.00,
                'currency': 'USD',
                'status': 'pending',
                'payment_method': 'mobile_money',
                'description': 'School pickup service - Week 2',
                'journey_date': datetime.now().date()
            },
            {
                'payment_id': str(uuid.uuid4()),
                'parent_id': 'parent-002',
                'child_id': 'child-002',
                'amount': 20.00,
                'currency': 'USD',
                'status': 'completed',
                'payment_method': 'cash',
                'description': 'After-school pickup',
                'journey_date': datetime.now().date()
            },
            {
                'payment_id': str(uuid.uuid4()),
                'parent_id': 'parent-001',
                'child_id': 'child-001',
                'amount': 35.00,
                'currency': 'USD',
                'status': 'failed',
                'payment_method': 'card',
                'description': 'Weekend pickup service',
                'journey_date': datetime.now().date()
            },
            {
                'payment_id': str(uuid.uuid4()),
                'parent_id': 'parent-003',
                'child_id': 'child-003',
                'amount': 40.00,
                'currency': 'USD',
                'status': 'refunded',
                'payment_method': 'card',
                'description': 'Holiday pickup service',
                'journey_date': datetime.now().date()
            }
        ]
        
        for payment_data in dummy_payments:
            payment = Payment(**payment_data)
            db.session.add(payment)
        
        db.session.commit()
        return jsonify({'message': 'Dummy payments added successfully', 'count': len(dummy_payments)}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/get_payments', methods=['GET'])
def get_payments():
    try:
        payments = Payment.query.order_by(Payment.created_at.desc()).all()
        
        payment_list = []
        for payment in payments:
            payment_list.append({
                'id': payment.id,
                'payment_id': payment.payment_id,
                'parent_id': payment.parent_id,
                'child_id': payment.child_id,
                'amount': payment.amount,
                'currency': payment.currency,
                'status': payment.status,
                'payment_method': payment.payment_method,
                'description': payment.description,
                'journey_date': payment.journey_date.isoformat() if payment.journey_date else None,
                'created_at': payment.created_at.isoformat() if payment.created_at else None,
                'updated_at': payment.updated_at.isoformat() if payment.updated_at else None
            })
        
        return jsonify({'payments': payment_list}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def send_notification(token, message):
    payload = {
        "to": token,
        "sound": "default",
        "title": "KidMate Notification",
        "body": message,
    }
    headers = {"Content-Type": "application/json"}
    requests.post("https://exp.host/--/api/v2/push/send", json=payload, headers=headers)

@app.route('/api/get-children', methods=['GET'])
@jwt_required()
def get_children():
    """Get all children for the authenticated parent user"""
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get parent associated with this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        
        if not parent:
            return jsonify({"error": "Parent not found for this user"}), 404
        
        # Get all children for this parent
        children = Kid.query.filter_by(parent_id=parent.id).all()
        
        children_list = []
        for child in children:
            child_data = {
                'id': child.id,
                'name': child.name,
                'age': child.age,
                'grade': child.grade,
                'school': child.school,
                'parent_id': child.parent_id,
                'created_at': child.created_at.isoformat() if child.created_at else None
            }
            children_list.append(child_data)
        
        return jsonify({
            "success": True,
            "children": children_list,
            "parent": {
                'id': parent.id,
                'name': parent.name,
                'phone': parent.phone,
                'address': parent.address,
                'occupation': parent.occupation,
                'relationship': parent.relationship
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-child-attendance/<int:child_id>', methods=['GET'])
@jwt_required()
def get_child_attendance(child_id):
    """Get attendance records for a specific child"""
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get parent associated with this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        
        if not parent:
            return jsonify({"error": "Parent not found for this user"}), 404
        
        # Verify the child belongs to this parent
        child = Kid.query.filter_by(id=child_id, parent_id=parent.id).first()
        
        if not child:
            return jsonify({"error": "Child not found or not authorized"}), 404
        
        # Get attendance records for this child
        import pymysql
        
        # Connect to database
        connection = pymysql.connect(
            host='localhost',
            port=8889,
            user='root',
            password='root',
            database='kidmate_db'
        )
        
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get attendance records for this child
            sql = """
                SELECT id, attendance_id, child_id, child_name, parent_id, parent_name, 
                       date, check_in_time, check_out_time, status, notes, created_at
                FROM attendance 
                WHERE child_id = %s OR child_name = %s
                ORDER BY date DESC, created_at DESC
            """
            cursor.execute(sql, (str(child_id), child.name))
            attendance_records = cursor.fetchall()
            
            # Convert datetime objects to strings
            for record in attendance_records:
                if record['created_at']:
                    record['created_at'] = record['created_at'].isoformat()
                if record['check_in_time']:
                    record['check_in_time'] = record['check_in_time'].isoformat()
                if record['check_out_time']:
                    record['check_out_time'] = record['check_out_time'].isoformat()
        
        connection.close()
        
        return jsonify({
            "success": True,
            "child": {
                'id': child.id,
                'name': child.name,
                'age': child.age,
                'grade': child.grade,
                'school': child.school
            },
            "attendance_records": attendance_records
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-child-grades/<int:child_id>', methods=['GET'])
@jwt_required()
def get_child_grades(child_id):
    """Get grade records for a specific child"""
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get parent associated with this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        
        if not parent:
            return jsonify({"error": "Parent not found for this user"}), 404
        
        # Verify the child belongs to this parent
        child = Kid.query.filter_by(id=child_id, parent_id=parent.id).first()
        
        if not child:
            return jsonify({"error": "Child not found or not authorized"}), 404
        
        # Get grade records for this child
        import pymysql
        
        # Connect to database
        connection = pymysql.connect(
            host='localhost',
            port=8889,
            user='root',
            password='root',
            database='kidmate_db'
        )
        
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get grade records for this child
            sql = """
                SELECT id, kid_id, subject, grade, remarks, comments, date_recorded, created_at
                FROM grades 
                WHERE kid_id = %s
                ORDER BY date_recorded DESC, created_at DESC
            """
            cursor.execute(sql, (child_id,))
            grade_records = cursor.fetchall()
            
            # Convert datetime objects to strings
            for record in grade_records:
                if record['created_at']:
                    record['created_at'] = record['created_at'].isoformat()
                if record['date_recorded']:
                    record['date_recorded'] = record['date_recorded'].isoformat()
        
        connection.close()
        
        return jsonify({
            "success": True,
            "child": {
                'id': child.id,
                'name': child.name,
                'age': child.age,
                'grade': child.grade,
                'school': child.school
            },
            "grade_records": grade_records
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-child-summary/<int:child_id>', methods=['GET'])
@jwt_required()
def get_child_summary(child_id):
    """Get comprehensive summary for a child including attendance and grades"""
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get parent associated with this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        
        if not parent:
            return jsonify({"error": "Parent not found for this user"}), 404
        
        # Verify the child belongs to this parent
        child = Kid.query.filter_by(id=child_id, parent_id=parent.id).first()
        
        if not child:
            return jsonify({"error": "Child not found or not authorized"}), 404
        
        # Get attendance and grades data
        import pymysql
        
        connection = pymysql.connect(
            host='localhost',
            port=8889,
            user='root',
            password='root',
            database='kidmate_db'
        )
        
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Get recent attendance (last 30 days)
            attendance_sql = """
                SELECT id, date, status, check_in_time, check_out_time, notes
                FROM attendance 
                WHERE (child_id = %s OR child_name = %s)
                AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                ORDER BY date DESC
                LIMIT 1
            """
            try:
                cursor.execute(attendance_sql, (str(child_id), child.name))
                recent_attendance = cursor.fetchall()
            except Exception as e:
                print(f"Error fetching attendance: {e}")
                recent_attendance = []
            
            # Get recent grades (last 6 months)
            grades_sql = """
                SELECT id, subject, grade, remarks, date_recorded
                FROM grades 
                WHERE kid_id = %s
                AND date_recorded >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                ORDER BY date_recorded DESC
                LIMIT 1
            """
            try:
                cursor.execute(grades_sql, (child_id,))
                recent_grades = cursor.fetchall()
            except Exception as e:
                print(f"Error fetching grades: {e}")
                recent_grades = []
            
            # Calculate attendance statistics
            attendance_stats_sql = """
                SELECT 
                    COUNT(*) as total_days,
                    SUM(CASE WHEN status IN ('Present', 'Checked In') THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
                    SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late_days
                FROM attendance 
                WHERE (child_id = %s OR child_name = %s)
                AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            """
            try:
                cursor.execute(attendance_stats_sql, (str(child_id), child.name))
                attendance_stats = cursor.fetchone()
            except Exception as e:
                print(f"Error calculating attendance stats: {e}")
                attendance_stats = {'total_days': 0, 'present_days': 0, 'absent_days': 0, 'late_days': 0}
            
            # Calculate grade statistics
            grades_stats_sql = """
                SELECT 
                    COUNT(*) as total_grades,
                    AVG(CAST(grade AS DECIMAL(5,2))) as average_grade,
                    MIN(grade) as lowest_grade,
                    MAX(grade) as highest_grade
                FROM grades 
                WHERE kid_id = %s
                AND date_recorded >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                AND grade REGEXP '^[0-9]+$'
            """
            try:
                cursor.execute(grades_stats_sql, (child_id,))
                grades_stats = cursor.fetchone()
            except Exception as e:
                print(f"Error calculating grades stats: {e}")
                grades_stats = {'total_grades': 0, 'average_grade': 0, 'lowest_grade': 0, 'highest_grade': 0}
        
        connection.close()
        
        # Calculate attendance percentage
        attendance_percentage = 0
        if attendance_stats and attendance_stats['total_days'] > 0:
            attendance_percentage = round((attendance_stats['present_days'] / attendance_stats['total_days']) * 100, 1)
        
        return jsonify({
            "success": True,
            "child": {
                'id': child.id,
                'name': child.name,
                'age': child.age,
                'grade': child.grade,
                'school': child.school
            },
            "recent_attendance": recent_attendance,
            "recent_grades": recent_grades,
            "attendance_stats": {
                'total_days': attendance_stats['total_days'] if attendance_stats else 0,
                'present_days': attendance_stats['present_days'] if attendance_stats else 0,
                'absent_days': attendance_stats['absent_days'] if attendance_stats else 0,
                'late_days': attendance_stats['late_days'] if attendance_stats else 0,
                'attendance_percentage': attendance_percentage
            },
            "grades_stats": {
                'total_grades': grades_stats['total_grades'] if grades_stats else 0,
                'average_grade': float(grades_stats['average_grade']) if grades_stats and grades_stats['average_grade'] else 0,
                'lowest_grade': grades_stats['lowest_grade'] if grades_stats else 0,
                'highest_grade': grades_stats['highest_grade'] if grades_stats else 0
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Complaints API endpoints
@app.route('/api/submit-complaint', methods=['POST'])
@jwt_required()
def submit_complaint():
    try:
        current_user_email = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        if not data.get('subject') or not data.get('description'):
            return jsonify({"error": "Subject and description are required"}), 400
        
        # Generate unique complaint ID
        import uuid
        complaint_id = str(uuid.uuid4())
        
        # Get parent information
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        parent_id = parent.id if parent else None
        
        # Create complaint
        complaint = Complaint(
            complaint_id=complaint_id,
            user_email=current_user_email,
            parent_id=parent_id,
            subject=data['subject'],
            description=data['description'],
            category=data.get('category', 'general'),
            priority=data.get('priority', 'medium')
        )
        
        db.session.add(complaint)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Complaint submitted successfully",
            "complaint_id": complaint_id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/api/get-complaints', methods=['GET'])
@jwt_required()
def get_complaints():
    try:
        current_user_email = get_jwt_identity()
        
        # Get complaints for the current user
        complaints = Complaint.query.filter_by(user_email=current_user_email).order_by(Complaint.created_at.desc()).all()
        
        complaints_list = []
        for complaint in complaints:
            complaints_list.append({
                'id': complaint.id,
                'complaint_id': complaint.complaint_id,
                'subject': complaint.subject,
                'description': complaint.description,
                'category': complaint.category,
                'priority': complaint.priority,
                'status': complaint.status,
                'assigned_to': complaint.assigned_to,
                'admin_notes': complaint.admin_notes,
                'created_at': complaint.created_at.isoformat() if complaint.created_at else None,
                'updated_at': complaint.updated_at.isoformat() if complaint.updated_at else None
            })
        
        return jsonify({
            "success": True,
            "complaints": complaints_list
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/get-complaint/<string:complaint_id>', methods=['GET'])
@jwt_required()
def get_complaint(complaint_id):
    try:
        current_user_email = get_jwt_identity()
        
        # Get specific complaint
        complaint = Complaint.query.filter_by(
            complaint_id=complaint_id,
            user_email=current_user_email
        ).first()
        
        if not complaint:
            return jsonify({"error": "Complaint not found"}), 404
        
        return jsonify({
            "success": True,
            "complaint": {
                'id': complaint.id,
                'complaint_id': complaint.complaint_id,
                'subject': complaint.subject,
                'description': complaint.description,
                'category': complaint.category,
                'priority': complaint.priority,
                'status': complaint.status,
                'assigned_to': complaint.assigned_to,
                'admin_notes': complaint.admin_notes,
                'created_at': complaint.created_at.isoformat() if complaint.created_at else None,
                'updated_at': complaint.updated_at.isoformat() if complaint.updated_at else None
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Admin endpoints for managing complaints
@app.route('/api/admin/complaints', methods=['GET'])
@jwt_required()
def admin_get_complaints():
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        # Check if user is admin
        if not user or user.role != 'admin':
            return jsonify({"error": "Unauthorized"}), 403
        
        # Get all complaints with user info
        complaints = db.session.query(Complaint, User.name.label('user_name')).join(
            User, Complaint.user_email == User.email
        ).order_by(Complaint.created_at.desc()).all()
        
        complaints_list = []
        for complaint, user_name in complaints:
            complaints_list.append({
                'id': complaint.id,
                'complaint_id': complaint.complaint_id,
                'user_email': complaint.user_email,
                'user_name': user_name,
                'subject': complaint.subject,
                'description': complaint.description,
                'category': complaint.category,
                'priority': complaint.priority,
                'status': complaint.status,
                'assigned_to': complaint.assigned_to,
                'admin_notes': complaint.admin_notes,
                'created_at': complaint.created_at.isoformat() if complaint.created_at else None,
                'updated_at': complaint.updated_at.isoformat() if complaint.updated_at else None
            })
        
        return jsonify({
            "success": True,
            "complaints": complaints_list
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/update-complaint/<string:complaint_id>', methods=['PUT'])
@jwt_required()
def admin_update_complaint(complaint_id):
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        # Check if user is admin
        if not user or user.role != 'admin':
            return jsonify({"error": "Unauthorized"}), 403
        
        data = request.get_json()
        
        # Get complaint
        complaint = Complaint.query.filter_by(complaint_id=complaint_id).first()
        if not complaint:
            return jsonify({"error": "Complaint not found"}), 404
        
        # Update fields
        if 'status' in data:
            complaint.status = data['status']
        if 'assigned_to' in data:
            complaint.assigned_to = data['assigned_to']
        if 'admin_notes' in data:
            complaint.admin_notes = data['admin_notes']
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Complaint updated successfully"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/get-pickup-persons', methods=['GET'])
@jwt_required()
def get_pickup_persons():
    try:
        current_user_email = get_jwt_identity()
        
        # Get the parent record for this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        if not parent:
            return jsonify({'error': 'Parent not found'}), 404
        
        # Get all kids for this parent
        kids = Kid.query.filter_by(parent_id=parent.id).all()
        if not kids:
            return jsonify({
                'success': True,
                'pickup_persons': [],
                'message': 'No children found for this parent'
            })
        
        # Get all pickup persons for these kids
        kid_ids = [kid.id for kid in kids]
        pickup_persons = PickupPerson.query.filter(PickupPerson.kid_id.in_(kid_ids)).all()
        
        pickup_persons_data = []
        for pickup_person in pickup_persons:
            # Get the kid information for this pickup person
            kid = Kid.query.get(pickup_person.kid_id)
            pickup_persons_data.append({
                'id': pickup_person.id,
                'name': pickup_person.name,
                'kid_name': kid.name if kid else 'Unknown',
                'kid_id': pickup_person.kid_id,
                'image_url': pickup_person.image,
                'pickup_id': pickup_person.pickup_id,
                'uuid': pickup_person.uuid
            })
        
        return jsonify({
            'success': True,
            'pickup_persons': pickup_persons_data
        })
        
    except Exception as e:
        app.logger.exception("Error fetching pickup persons:")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-journey-details/<string:pickup_id>', methods=['GET'])
@jwt_required()
def get_journey_details(pickup_id):
    try:
        current_user_email = get_jwt_identity()
        
        # Get the parent record for this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        if not parent:
            return jsonify({'error': 'Parent not found'}), 404
        
        # Get the pickup person for this journey
        pickup_person = PickupPerson.query.filter_by(pickup_id=pickup_id).first()
        if not pickup_person:
            return jsonify({'error': 'Pickup person not found for this journey'}), 404
        
        # Get the child information
        child = Kid.query.get(pickup_person.kid_id)
        if not child:
            return jsonify({'error': 'Child not found'}), 404
        
        # Verify the child belongs to this parent
        if child.parent_id != parent.id:
            return jsonify({'error': 'Unauthorized access to this journey'}), 403
        
        # Get journey status from PickupJourney table
        journey = PickupJourney.query.filter_by(pickup_id=pickup_id).first()
        
        journey_details = {
            'pickup_id': pickup_id,
            'child': {
                'id': child.id,
                'name': child.name,
                'age': child.age,
                'grade': child.grade,
                'school': child.school
            },
            'pickup_person': {
                'id': pickup_person.id,
                'name': pickup_person.name,
                'image_url': pickup_person.image,
                'uuid': pickup_person.uuid
            },
            'status': journey.status if journey else 'pending',
            'timestamp': journey.timestamp.isoformat() if journey and journey.timestamp else None
        }
        
        return jsonify({
            'success': True,
            'journey_details': journey_details
        })
        
    except Exception as e:
        app.logger.exception("Error fetching journey details:")
        return jsonify({'error': str(e)}), 500

# Run server
if __name__ == '__main__':
    app.run(debug=True)
