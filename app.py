import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, jwt_required, get_jwt_identity, get_jwt
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_migrate import Migrate
import requests
import uuid
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging for production
if not app.debug:
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    # Configure file handler for production logging
    file_handler = RotatingFileHandler('logs/kidmate.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    # Set app logger level
    app.logger.setLevel(logging.INFO)
    app.logger.info('KidMate startup')

# Configuration
# Load environment variables (no defaults)
DATABASE_URL = os.getenv('DATABASE_URL_LOCAL', 'mysql+pymysql://root:root@4.tcp.eu.ngrok.io:16396/kidmate_db')
SECRET_KEY = os.getenv('SECRET_KEY')
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')



# Validate required environment variables
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is required")

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Security configuration
app.config['SECRET_KEY'] = SECRET_KEY
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY

# Upload configuration
app.config['UPLOAD_FOLDER'] = 'uploads/images'

# JWT Configuration
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)  # Set token expiration to 30 minutes
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)  # Set refresh token expiration to 30 days

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Email configuration
MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.hostinger.com')
MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'schoolapp@outrankconsult.com')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'Gq]PxrqB#sC2')
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'schoolapp@outrankconsult.com')

app.config['MAIL_SERVER'] = MAIL_SERVER
app.config['MAIL_PORT'] = MAIL_PORT
app.config['MAIL_USE_TLS'] = MAIL_USE_TLS
app.config['MAIL_USE_SSL'] = MAIL_USE_SSL
app.config['MAIL_USERNAME'] = MAIL_USERNAME
app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = MAIL_DEFAULT_SENDER

# Initialize extensions
from models import PickupJourney, db, User, Parent, Kid, PickupPerson, Payment, Attendance, Complaint, AdminUser, Term, Subject, Class, Grade  # Import db from models.py
from email_service import mail, EmailService
db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
mail.init_app(app)

# Request logging middleware
@app.before_request
def log_request():
    """Log all incoming requests"""
    app.logger.info("Request: {} {} from IP: {} - User-Agent: {}".format(
        request.method, 
        request.url, 
        request.remote_addr,
        request.user_agent.string if request.user_agent else 'Unknown'
    ))

@app.after_request
def log_response(response):
    """Log all responses"""
    app.logger.info("Response: {} {} - Status: {}".format(
        request.method, 
        request.url, 
        response.status_code
    ))
    return response

@app.errorhandler(Exception)
def log_error(error):
    """Log all unhandled exceptions"""
    app.logger.error("Unhandled exception: {} - URL: {} - Method: {}".format(
        str(error), 
        request.url, 
        request.method
    ))
    return jsonify({"error": "Internal server error"}), 500

# --- Routes ---


SEQUENTIAL_STATUS_FLOW = {
    None: 'pending',
    'pending': 'departed',
    'departed': 'picked',
    'picked': 'arrived',
    'arrived': 'completed'
}

FINAL_STATUSES = ['completed', 'cancelled']

@app.route('/')
def home():
    app.logger.info("Home endpoint accessed")
    return jsonify({'message': 'Hello World'})

@app.route('/test')
def test():
    app.logger.info("Test endpoint accessed")
    return jsonify({'message': 'Backend is working', 'timestamp': datetime.now().isoformat()})



@app.route('/api/register', methods=['POST'])
def register_user():
    try:
        # Log the incoming request
        app.logger.info("Register API request received from IP: {}".format(request.remote_addr))
        
        data = request.get_json()
        if not data:
            app.logger.warning("Register request with no JSON data")
            return jsonify({"msg": "Invalid request data"}), 400

        phone = data.get('phone')
        password = data.get('password')
        name = data.get('name')
        email = data.get('email')
        role = data.get('role', 'Parent')

        app.logger.info("Registration attempt for phone: {}, email: {}, role: {}".format(phone, email, role))

        # Validate required fields
        if not phone or not password:
            app.logger.warning("Registration failed: Missing phone or password")
            return jsonify({"msg": "Phone and password are required"}), 400

        # Check if user already exists by phone
        existing_user = User.query.filter_by(phone=phone).first()
        if existing_user:
            app.logger.warning("Registration failed: User with phone {} already exists".format(phone))
            return jsonify({"msg": "User already exists"}), 400

        app.logger.info("Validation passed, creating new user")

        # Create new user
        user = User(name=name, phone=phone, email=email)
        user.set_password(password)
        user.set_role(role)

        app.logger.info("User object created with ID: {}".format(user.id))

        # Save user to DB
        db.session.add(user)
        db.session.commit()
        app.logger.info("User saved successfully with ID: {}".format(user.id))

        # Send welcome email if email is provided
        if email:
            try:
                EmailService.send_welcome_email(email, name or "User")
                app.logger.info("Welcome email sent to: {}".format(email))
                
                # Also send notification to daviddors12@gmail.com for monitoring
                EmailService.send_welcome_email("daviddors12@gmail.com", "Admin")
                app.logger.info("Welcome email notification sent to daviddors12@gmail.com")
            except Exception as e:
                app.logger.error("Failed to send welcome email: {}".format(str(e)))

        # Create JWT access and refresh tokens with user id as identity
        access_token = create_access_token(identity={"id": user.id, "name": user.name, "role": user.role})
        refresh_token = create_refresh_token(identity={"id": user.id, "name": user.name, "role": user.role})
        app.logger.info("JWT tokens created for user: {}".format(user.name))
        
        response_data = {
            "token": access_token,
            "refresh_token": refresh_token
        }
        app.logger.info("Registration completed successfully for user ID: {}".format(user.id))
        
        return jsonify(response_data), 201
        
    except Exception as e:
        app.logger.error("Error in register_user: {} - Type: {}".format(str(e), type(e).__name__))
        import traceback
        app.logger.error("Full traceback: {}".format(traceback.format_exc()))
        return jsonify({"error": "Internal server error"}), 500

@app.route('/update_status', methods=['POST'])
def update_status():
    app.logger.info("🔧 BACKEND - Status Update Request Received")
    app.logger.info("🔧 Request Headers: %s", dict(request.headers))
    app.logger.info("🔧 Request Content-Type: %s", request.content_type)
    
    data = request.get_json()
    app.logger.info("🔧 Raw request data: %s", data)

    # Log the incoming request data
    app.logger.info("Update status request received for pickup_id: {}".format(data.get('pickup_id') if data else 'None'))

    # Only require pickup_id and status - backend will get the rest from database
    required_fields = ['pickup_id', 'status']
    if not all(field in data for field in required_fields):
        app.logger.warning("Update status failed: Missing required fields")
        return jsonify({'error': 'Missing pickup_id or status'}), 400

    new_status = data['status']
    pickup_id = data['pickup_id']
    
    app.logger.info("🔧 Parsed data:")
    app.logger.info("🔧   Pickup ID: %s (type: %s)", pickup_id, type(pickup_id))
    app.logger.info("🔧   Status: %s (type: %s)", new_status, type(new_status))

    # Get the latest status for this pickup_id
    latest_entry = (PickupJourney.query
                    .filter_by(pickup_id=pickup_id)
                    .order_by(PickupJourney.timestamp.desc())
                    .first())

    previous_status = latest_entry.status if latest_entry else None

    # Log the status transition
    app.logger.info("Status transition for pickup_id {}: {} -> {}".format(pickup_id, previous_status, new_status))

    if new_status == 'cancelled':
        if previous_status == 'completed':
            app.logger.warning("Cannot cancel completed journey for pickup_id: {}".format(pickup_id))
            return jsonify({'error': 'Cannot cancel a completed journey'}), 400
    elif previous_status in FINAL_STATUSES:
        app.logger.warning("Cannot update status after journey is {} for pickup_id: {}".format(previous_status, pickup_id))
        return jsonify({'error': 'Cannot update status after journey is {}'.format(previous_status)}), 400
    elif SEQUENTIAL_STATUS_FLOW.get(previous_status) != new_status:
        expected_next = SEQUENTIAL_STATUS_FLOW.get(previous_status)
        app.logger.warning("Invalid status transition for pickup_id {}: {} -> {} (expected: {})".format(pickup_id, previous_status, new_status, expected_next))
        return jsonify({
            'error': 'Invalid status transition. Current: {}, expected: {}, received: {}'.format(previous_status or "none", expected_next, new_status)
        }), 400

    # Get the existing journey to get the data
    existing_journey = PickupJourney.query.filter_by(pickup_id=pickup_id).first()
    if not existing_journey:
        app.logger.error("🔧 Journey not found for pickup_id: %s", pickup_id)
        return jsonify({'error': 'Journey not found'}), 404
    
    app.logger.info("🔧 Found existing journey: parent_id=%s, child_id=%s, pickup_person_id=%s", 
                   existing_journey.parent_id, existing_journey.child_id, existing_journey.pickup_person_id)
    
    # Create new journey record with data from existing journey
    journey = PickupJourney(
        pickup_id=pickup_id,
        parent_id=existing_journey.parent_id,
        child_id=existing_journey.child_id,
        pickup_person_id=existing_journey.pickup_person_id,
        status=new_status,
        dropoff_location=existing_journey.dropoff_location,
        dropoff_latitude=existing_journey.dropoff_latitude,
        dropoff_longitude=existing_journey.dropoff_longitude
    )

    db.session.add(journey)
    db.session.commit()

    # Send email notifications for all status changes
    try:
        app.logger.info("Starting email notification process for status: {}".format(new_status))
        
        # Get parent and child information for email notifications from the existing journey
        parent = None
        child = None
        pickup_person = None
        
        # Get parent from the journey data
        try:
            parent_id = int(existing_journey.parent_id) if existing_journey.parent_id.isdigit() else existing_journey.parent_id
            if isinstance(parent_id, int):
                parent = User.query.filter_by(id=parent_id).first()
            else:
                # If it's a string ID, try to find by email
                parent = User.query.filter_by(email="daviddors12@gmail.com").first()
        except (ValueError, TypeError):
            parent = User.query.filter_by(email="daviddors12@gmail.com").first()
        
        if not parent:
            # Create a placeholder parent for email notifications
            parent = User(
                id=999,
                name="Parent",
                email="daviddors12@gmail.com",
                phone="1234567890"
            )
        
        # Get child from the journey data
        try:
            child_id = int(existing_journey.child_id) if existing_journey.child_id.isdigit() else existing_journey.child_id
            if isinstance(child_id, int):
                child = Kid.query.filter_by(id=child_id).first()
        except (ValueError, TypeError):
            pass
        
        if not child:
            # Create a placeholder child for email notifications
            child = Kid(
                id=999,
                name="Child",
                parent_id=parent.id if parent else 999
            )
        
        # Get pickup person from the journey data
        try:
            pickup_person_id = int(existing_journey.pickup_person_id) if existing_journey.pickup_person_id.isdigit() else existing_journey.pickup_person_id
            if isinstance(pickup_person_id, int):
                pickup_person = PickupPerson.query.filter_by(id=pickup_person_id).first()
            else:
                # If it's a string ID, try to find by UUID
                pickup_person = PickupPerson.query.filter_by(uuid=pickup_person_id).first()
        except (ValueError, TypeError):
            pickup_person = PickupPerson.query.filter_by(uuid=existing_journey.pickup_person_id).first()
        
        if not pickup_person:
            # Create a placeholder pickup person for email notifications
            pickup_person = PickupPerson(
                id=999,
                name="Pickup Person",
                phone="0987654321",
                uuid="placeholder-uuid"
            )
        
        app.logger.info("🔧 Database lookup results:")
        app.logger.info("🔧   Parent: %s (ID: %s, Email: %s)", 
                       parent.name if parent else "None",
                       parent.id if parent else "None",
                       parent.email if parent else "None")
        app.logger.info("🔧   Child: %s (ID: %s)", 
                       child.name if child else "None",
                       child.id if child else "None")
        app.logger.info("🔧   PickupPerson: %s (ID: %s, UUID: %s)", 
                       pickup_person.name if pickup_person else "None",
                       pickup_person.id if pickup_person else "None",
                       pickup_person.uuid if pickup_person else "None")
        
        if parent and parent.email and child:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pickup_person_name = pickup_person.name if pickup_person else "Pickup Person"
            
            app.logger.info("Sending email to parent: {} ({})".format(parent.name, parent.email))
            
            # Send comprehensive status notification for all status changes
            parent_email_result = EmailService.send_journey_status_notification(
                parent.email,
                parent.name or "Parent",
                child.name,
                pickup_person_name,
                new_status,
                current_time,
                data.get('additional_info')  # For cancelled/delayed statuses
            )
            
            app.logger.info("Parent email result: {}".format(parent_email_result))
            
            app.logger.info("Sending email to admin: daviddors12@gmail.com")
            
            # Also send notification to daviddors12@gmail.com for monitoring
            admin_email_result = EmailService.send_journey_status_notification(
                "daviddors12@gmail.com",
                "Admin",
                child.name,
                pickup_person_name,
                new_status,
                current_time,
                f"Parent: {parent.name} ({parent.email}) - {data.get('additional_info', '')}"
            )
            
            app.logger.info("Admin email result: {}".format(admin_email_result))
            app.logger.info("Journey status notification emails sent to: {} and daviddors12@gmail.com for status: {}".format(parent.email, new_status))
        else:
            app.logger.warning("Cannot send emails - missing data: parent={}, parent.email={}, child={}".format(
                parent is not None, 
                parent.email if parent else "None",
                child is not None
            ))
                
    except Exception as e:
        app.logger.error("Failed to send email notification: {}".format(str(e)))
        import traceback
        app.logger.error("Email error traceback: {}".format(traceback.format_exc()))

    app.logger.info("Status updated successfully for pickup_id {}: {}".format(pickup_id, new_status))
    return jsonify({'message': 'Status updated to "{}" for pickup {}'.format(new_status, pickup_id)}), 200



@app.route('/api/login', methods=['POST'])
def login_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    app.logger.info("Login attempt for email: {}".format(email))

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        app.logger.warning("Login failed for email: {} - Invalid credentials".format(email))
        return jsonify({"error": "Invalid credentials"}), 401

    # Create access and refresh tokens with email as identity (string)
    access_token = create_access_token(identity=user.email)
    refresh_token = create_refresh_token(identity=user.email)
    app.logger.info("Login successful for user: {} (ID: {})".format(user.name, user.id))
    
    return jsonify({
        "token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    }), 200


@app.route('/api/refresh', methods=['POST'])
@jwt_required()
def refresh_token():
    """Refresh access token using refresh token"""
    try:
        jwt_data = get_jwt()
        if jwt_data.get('type') != 'refresh':
            app.logger.warning("Invalid token type for refresh")
            return jsonify({"error": "Invalid token type"}), 401
            
        current_user = get_jwt_identity()
        app.logger.info("Token refresh requested for user: {}".format(current_user))
        
        # Create new access token
        new_access_token = create_access_token(identity=current_user)
        app.logger.info("New access token created for user: {}".format(current_user))
        
        return jsonify({
            "token": new_access_token
        }), 200
        
    except Exception as e:
        app.logger.error("Error refreshing token: {} - User: {}".format(str(e), current_user))
        return jsonify({"error": "Token refresh failed"}), 500


@app.route('/api/me', methods=['GET'])
@jwt_required()
def get_user_info():
    try:
        current_user_email = get_jwt_identity()
        app.logger.info("User info request for email: {}".format(current_user_email))
        
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            app.logger.warning("User not found for email: {}".format(current_user_email))
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
        
        app.logger.info("User info retrieved successfully for user: {} (ID: {})".format(user.name, user.id))
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
        app.logger.error("Error in get_user_info: {} - Email: {}".format(str(e), current_user_email))
        return jsonify({"error": "Internal server error"}), 500

def save_image(file, parent_id=None, kid_name=None, timestamp=None):
    if file:
        if parent_id and kid_name and timestamp:
            # For pickup uploads, create custom filename
            file_extension = os.path.splitext(file.filename)[1]
            filename = f"pickup_parent{parent_id}_{kid_name}_{timestamp}{file_extension}"
            filename = secure_filename(filename)
        else:
            # For other uploads, use original filename
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
            "message": "Parent {} linked to user {} ({})".format(parent.name, user.name, user_email),
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

        app.logger.debug("Received form data: {}".format(data))
        app.logger.debug("Received image file: {}".format(image_file))

        # Assign defaults
        name = data.get('name', 'Unknown Person')
        pickup_id = data.get('pickup_id', '1234')
        kid_id = data.get('kid_id', '5')
        phone = data.get('phone', '')

        # Get kid and parent information for filename
        kid = Kid.query.get(kid_id)
        if kid:
            parent_id = kid.parent_id
            kid_name = kid.name
        else:
            parent_id = 'unknown'
            kid_name = 'unknown'

        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save image with custom naming
        image_path = save_image(image_file, parent_id, kid_name, timestamp)

        pickup_uuid = str(uuid.uuid4())

        person = PickupPerson(
            uuid=pickup_uuid,
            name=name,
            pickup_id=pickup_id,
            kid_id=kid_id,
            phone=phone,
            image=image_path,
            is_active=True
        )

        db.session.add(person)
        db.session.commit()

        pickup_url = "https://bdf1812b29eb.ngrok-free.app/pickup/{}".format(pickup_uuid)

        app.logger.info("Pickup person added with UUID: {}".format(pickup_uuid))
        return jsonify({
            'message': 'Pickup person created successfully',
            'pickup_person_uuid': pickup_uuid,
            'pickup_url': pickup_url
        }), 200

    except Exception as e:
        app.logger.exception("Error assigning pickup:")
        return jsonify({'error': str(e)}), 500

@app.route('/api/record-departure', methods=['POST'])
@jwt_required()
def record_departure():
    try:
        data = request.get_json()
        pickup_id = data.get('pickup_id')
        
        if not pickup_id:
            return jsonify({'error': 'pickup_id is required'}), 400
        
        # Get the latest journey for this pickup_id
        latest_journey = (PickupJourney.query
                         .filter_by(pickup_id=pickup_id)
                         .order_by(PickupJourney.timestamp.desc())
                         .first())
        
        if not latest_journey:
            return jsonify({'error': 'Journey not found'}), 404
        
        # Check if current status is pending
        if latest_journey.status != 'pending':
            return jsonify({'error': 'Can only record departure from pending status'}), 400
        
        # Create new journey record with departed status
        new_journey = PickupJourney(
            pickup_id=pickup_id,
            parent_id=latest_journey.parent_id,
            child_id=latest_journey.child_id,
            pickup_person_id=latest_journey.pickup_person_id,
            status='departed',
            dropoff_location=latest_journey.dropoff_location,
            dropoff_latitude=latest_journey.dropoff_latitude,
            dropoff_longitude=latest_journey.dropoff_longitude
        )
        
        db.session.add(new_journey)
        db.session.commit()
        
        app.logger.info("Departure recorded successfully for pickup_id: {}".format(pickup_id))
        return jsonify({'message': 'Departure recorded successfully', 'status': 'departed'}), 200
        
    except Exception as e:
        app.logger.exception("Error recording departure:")
        return jsonify({'error': str(e)}), 500

@app.route('/api/create-journey', methods=['POST'])
@jwt_required()
def create_journey():
    try:
        app.logger.info("🔧 BACKEND - Create Journey Request Received")
        app.logger.info("🔧 Request Headers: %s", dict(request.headers))
        app.logger.info("🔧 Request Content-Type: %s", request.content_type)
        
        data = request.get_json()
        app.logger.info("🔧 Raw request data: %s", data)
        
        # Get current user (parent)
        current_user_email = get_jwt_identity()
        app.logger.info("🔧 Current user email: %s", current_user_email)
        
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        app.logger.info("🔧 Parent found: %s (ID: %s)", parent.name if parent else "None", parent.id if parent else "None")
        
        if not parent:
            app.logger.error("🔧 Parent not found for email: %s", current_user_email)
            return jsonify({'error': 'Parent not found'}), 404
        
        # Extract journey data
        pickup_person_id = data.get('pickup_person_id')
        child_id = data.get('child_id')
        dropoff_location = data.get('dropoff_location', '')
        dropoff_latitude = data.get('dropoff_latitude')
        dropoff_longitude = data.get('dropoff_longitude')
        
        app.logger.info("🔧 Extracted journey data:")
        app.logger.info("🔧   Pickup Person ID: %s (type: %s)", pickup_person_id, type(pickup_person_id))
        app.logger.info("🔧   Child ID: %s (type: %s)", child_id, type(child_id))
        app.logger.info("🔧   Dropoff Location: %s", dropoff_location)
        app.logger.info("🔧   Dropoff Latitude: %s (type: %s)", dropoff_latitude, type(dropoff_latitude))
        app.logger.info("🔧   Dropoff Longitude: %s (type: %s)", dropoff_longitude, type(dropoff_longitude))
        
        # Validate required fields
        if not pickup_person_id or not child_id:
            app.logger.error("🔧 Missing required fields: pickup_person_id=%s, child_id=%s", pickup_person_id, child_id)
            return jsonify({'error': 'Pickup person ID and child ID are required'}), 400
        
        # Verify the child belongs to this parent
        child = Kid.query.get(child_id)
        app.logger.info("🔧 Child lookup: ID=%s, Found=%s, Parent_ID=%s, Expected_Parent_ID=%s", 
                       child_id, child is not None, child.parent_id if child else "None", parent.id)
        
        if not child or child.parent_id != parent.id:
            app.logger.error("🔧 Child not found or unauthorized: child_id=%s, child_parent_id=%s, current_parent_id=%s", 
                           child_id, child.parent_id if child else "None", parent.id)
            return jsonify({'error': 'Child not found or unauthorized'}), 404
        
        # Verify the pickup person exists
        pickup_person = PickupPerson.query.filter_by(uuid=pickup_person_id).first()
        app.logger.info("🔧 Pickup person lookup: UUID=%s, Found=%s, Name=%s", 
                       pickup_person_id, pickup_person is not None, pickup_person.name if pickup_person else "None")
        
        if not pickup_person:
            app.logger.error("🔧 Pickup person not found: UUID=%s", pickup_person_id)
            return jsonify({'error': 'Pickup person not found'}), 404
        
        # Generate unique pickup ID for this journey
        pickup_id = str(uuid.uuid4())[:8].upper()
        app.logger.info("🔧 Generated pickup ID: %s", pickup_id)
        
        # Create the journey
        journey = PickupJourney(
            pickup_id=pickup_id,
            parent_id=str(parent.id),
            child_id=str(child_id),
            pickup_person_id=pickup_person_id,
            status='pending',
            dropoff_location=dropoff_location,
            dropoff_latitude=float(dropoff_latitude) if dropoff_latitude else None,
            dropoff_longitude=float(dropoff_longitude) if dropoff_longitude else None
        )
        
        app.logger.info("🔧 Creating journey with data:")
        app.logger.info("🔧   Pickup ID: %s", pickup_id)
        app.logger.info("🔧   Parent ID: %s (type: %s)", str(parent.id), type(str(parent.id)))
        app.logger.info("🔧   Child ID: %s (type: %s)", str(child_id), type(str(child_id)))
        app.logger.info("🔧   Pickup Person ID: %s (type: %s)", pickup_person_id, type(pickup_person_id))
        app.logger.info("🔧   Status: pending")
        
        db.session.add(journey)
        db.session.commit()
        
        app.logger.info("🔧 Journey created successfully with pickup_id: %s", pickup_id)
        return jsonify({
            'message': 'Journey created successfully',
            'pickup_id': pickup_id,
            'journey_id': journey.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Error creating journey:")
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
        send_notification(parent.push_token, "{} has {} for {}.".format(person.name, data['status'], kid.name))
        return jsonify({'message': '{} notification sent.'.format(data["status"].capitalize())})
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
                    'pickup_person_id': latest_journey.pickup_person_id,
                    'dropoff_location': latest_journey.dropoff_location,
                    'dropoff_latitude': latest_journey.dropoff_latitude,
                    'dropoff_longitude': latest_journey.dropoff_longitude
                })
        
        return jsonify({'journeys': journeys}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_user_journeys', methods=['GET'])
def get_user_journeys():
    try:
        # For now, return all journeys since we're not using authentication
        app.logger.info("Getting all journeys (no authentication required)")
        
        # Get all journeys
        journeys = []
        all_journeys = PickupJourney.query.order_by(PickupJourney.timestamp.desc()).all()
        
        app.logger.info("Found {} total journeys".format(len(all_journeys)))
        
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
                'pickup_person_id': latest_journey.pickup_person_id,
                'dropoff_location': latest_journey.dropoff_location,
                'dropoff_latitude': latest_journey.dropoff_latitude,
                'dropoff_longitude': latest_journey.dropoff_longitude
            })
        
        return jsonify({'journeys': journeys}), 200
    except Exception as e:
        app.logger.error("Error in get_user_journeys: {}".format(str(e)))
        return jsonify({'error': 'Internal server error'}), 500

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

@app.route('/api/get-children', methods=['GET', 'POST'])
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
                app.logger.error("Error fetching attendance: {}".format(e))
                recent_attendance = []
            
            # Get average grade summary
            grades_sql = """
                SELECT 
                    'Average' as subject,
                    CONCAT(ROUND(AVG(
                        CASE 
                            WHEN grade = 'A+' THEN 4.0
                            WHEN grade = 'A' THEN 4.0
                            WHEN grade = 'A-' THEN 3.7
                            WHEN grade = 'B+' THEN 3.3
                            WHEN grade = 'B' THEN 3.0
                            WHEN grade = 'B-' THEN 2.7
                            WHEN grade = 'C+' THEN 2.3
                            WHEN grade = 'C' THEN 2.0
                            WHEN grade = 'C-' THEN 1.7
                            WHEN grade = 'D+' THEN 1.3
                            WHEN grade = 'D' THEN 1.0
                            WHEN grade = 'D-' THEN 0.7
                            WHEN grade = 'F' THEN 0.0
                            ELSE NULL
                        END
                    ), 1), '/4.0') as grade,
                    CAST(CONCAT(COUNT(*), ' subjects') AS CHAR) as remarks,
                    MAX(date_recorded) as date_recorded
                FROM grades 
                WHERE kid_id = %s
                AND grade IN ('A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F')
            """
            
            # Get highest grade
            highest_grade_sql = """
                SELECT 
                    subject,
                    grade,
                    remarks,
                    date_recorded
                FROM grades 
                WHERE kid_id = %s
                ORDER BY 
                    CASE 
                        WHEN grade = 'A+' THEN 1
                        WHEN grade = 'A' THEN 2
                        WHEN grade = 'A-' THEN 3
                        WHEN grade = 'B+' THEN 4
                        WHEN grade = 'B' THEN 5
                        WHEN grade = 'B-' THEN 6
                        WHEN grade = 'C+' THEN 7
                        WHEN grade = 'C' THEN 8
                        WHEN grade = 'C-' THEN 9
                        WHEN grade = 'D+' THEN 10
                        WHEN grade = 'D' THEN 11
                        WHEN grade = 'D-' THEN 12
                        WHEN grade = 'F' THEN 13
                        ELSE 14
                    END ASC,
                    date_recorded DESC
                LIMIT 1
            """
            try:
                cursor.execute(grades_sql, (child_id,))
                average_grade = cursor.fetchone()
                app.logger.info("Average grade fetched successfully: {}".format(average_grade))
            except Exception as e:
                app.logger.error("Error fetching average grade: {}".format(e))
                app.logger.error("SQL query: {}".format(grades_sql))
                app.logger.error("Child ID: {}".format(child_id))
                average_grade = None
                
            try:
                cursor.execute(highest_grade_sql, (child_id,))
                highest_grade = cursor.fetchone()
                app.logger.info("Highest grade fetched successfully: {}".format(highest_grade))
            except Exception as e:
                app.logger.error("Error fetching highest grade: {}".format(e))
                app.logger.error("SQL query: {}".format(highest_grade_sql))
                app.logger.error("Child ID: {}".format(child_id))
                highest_grade = None
                
            # Only return the highest grade
            recent_grades = []
            if highest_grade:
                recent_grades.append(highest_grade)
            
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
                app.logger.error("Error calculating attendance stats: {}".format(e))
                attendance_stats = {'total_days': 0, 'present_days': 0, 'absent_days': 0, 'late_days': 0}
            
            # Calculate grade statistics
            grades_stats_sql = """
                SELECT 
                    COUNT(*) as total_grades,
                    AVG(
                        CASE 
                            WHEN grade = 'A+' THEN 4.0
                            WHEN grade = 'A' THEN 4.0
                            WHEN grade = 'A-' THEN 3.7
                            WHEN grade = 'B+' THEN 3.3
                            WHEN grade = 'B' THEN 3.0
                            WHEN grade = 'B-' THEN 2.7
                            WHEN grade = 'C+' THEN 2.3
                            WHEN grade = 'C' THEN 2.0
                            WHEN grade = 'C-' THEN 1.7
                            WHEN grade = 'D+' THEN 1.3
                            WHEN grade = 'D' THEN 1.0
                            WHEN grade = 'D-' THEN 0.7
                            WHEN grade = 'F' THEN 0.0
                            ELSE NULL
                        END
                    ) as average_grade,
                    MIN(grade) as lowest_grade,
                    MAX(grade) as highest_grade
                FROM grades 
                WHERE kid_id = %s
                AND grade IN ('A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F')
            """
            try:
                cursor.execute(grades_stats_sql, (child_id,))
                grades_stats = cursor.fetchone()
            except Exception as e:
                app.logger.error("Error calculating grades stats: {}".format(e))
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
                'uuid': pickup_person.uuid,
                'is_active': pickup_person.is_active,
                'created_at': pickup_person.created_at.isoformat() if pickup_person.created_at else None,
                'updated_at': pickup_person.updated_at.isoformat() if pickup_person.updated_at else None
            })
        
        return jsonify({
            'success': True,
            'pickup_persons': pickup_persons_data
        })
        
    except Exception as e:
        app.logger.exception("Error fetching pickup persons:")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toggle-pickup-person-status/<int:pickup_person_id>', methods=['PUT'])
@jwt_required()
def toggle_pickup_person_status(pickup_person_id):
    try:
        current_user_email = get_jwt_identity()
        
        # Get the parent record for this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        if not parent:
            return jsonify({'error': 'Parent not found'}), 404
        
        # Get the pickup person
        pickup_person = PickupPerson.query.get(pickup_person_id)
        if not pickup_person:
            return jsonify({'error': 'Pickup person not found'}), 404
        
        # Verify the pickup person belongs to a kid of this parent
        kid = Kid.query.get(pickup_person.kid_id)
        if not kid or kid.parent_id != parent.id:
            return jsonify({'error': 'Unauthorized access to this pickup person'}), 403
        
        # Toggle the active status
        pickup_person.is_active = not pickup_person.is_active
        db.session.commit()
        
        app.logger.info("Pickup person {} status toggled to {} by user {}".format(
            pickup_person.name, 
            "active" if pickup_person.is_active else "inactive",
            current_user_email
        ))
        
        return jsonify({
            'success': True,
            'message': 'Pickup person status updated successfully',
            'pickup_person': {
                'id': pickup_person.id,
                'name': pickup_person.name,
                'is_active': pickup_person.is_active,
                'updated_at': pickup_person.updated_at.isoformat() if pickup_person.updated_at else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Error toggling pickup person status:")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-journey-details/<string:pickup_id>', methods=['GET'])
@jwt_required()
def get_journey_details(pickup_id):
    try:
        app.logger.info("🔧 BACKEND - Get Journey Details Request for pickup_id: %s", pickup_id)
        
        current_user_email = get_jwt_identity()
        app.logger.info("🔧 Current user email: %s", current_user_email)
        
        # Get the parent record for this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        if not parent:
            app.logger.error("🔧 Parent not found for email: %s", current_user_email)
            return jsonify({'error': 'Parent not found'}), 404
        
        app.logger.info("🔧 Parent found: %s (ID: %s)", parent.name, parent.id)
        
        # Get journey directly from PickupJourney table
        journey = PickupJourney.query.filter_by(pickup_id=pickup_id).first()
        if not journey:
            app.logger.error("🔧 Journey not found for pickup_id: %s", pickup_id)
            return jsonify({'error': 'Journey not found'}), 404
        
        app.logger.info("🔧 Journey found: parent_id=%s, child_id=%s, pickup_person_id=%s", 
                       journey.parent_id, journey.child_id, journey.pickup_person_id)
        
        # Get the child information
        child = Kid.query.get(journey.child_id)
        if not child:
            app.logger.error("🔧 Child not found for child_id: %s", journey.child_id)
            return jsonify({'error': 'Child not found'}), 404
        
        app.logger.info("🔧 Child found: %s (ID: %s, Parent ID: %s)", child.name, child.id, child.parent_id)
        
        # Verify the child belongs to this parent
        if str(child.parent_id) != str(parent.id):
            app.logger.error("🔧 Unauthorized access: child_parent_id=%s, current_parent_id=%s", 
                           child.parent_id, parent.id)
            return jsonify({'error': 'Unauthorized access to this journey'}), 403
        
        # Get the pickup person information
        pickup_person = PickupPerson.query.filter_by(uuid=journey.pickup_person_id).first()
        if not pickup_person:
            app.logger.error("🔧 Pickup person not found for uuid: %s", journey.pickup_person_id)
            return jsonify({'error': 'Pickup person not found'}), 404
        
        app.logger.info("🔧 Pickup person found: %s (ID: %s, UUID: %s)", 
                       pickup_person.name, pickup_person.id, pickup_person.uuid)
        
        journey_details = {
            'pickup_id': pickup_id,
            'parent_id': journey.parent_id,
            'child_id': journey.child_id,
            'pickup_person_id': journey.pickup_person_id,
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
            'timestamp': journey.timestamp.isoformat() if journey and journey.timestamp else None,
            'dropoff_location': journey.dropoff_location if journey else None,
            'dropoff_latitude': journey.dropoff_latitude if journey else None,
            'dropoff_longitude': journey.dropoff_longitude if journey else None
        }
        
        app.logger.info("🔧 Journey details response: %s", journey_details)
        
        return jsonify({
            'success': True,
            'journey_details': journey_details
        })
        
    except Exception as e:
        app.logger.exception("Error fetching journey details:")
        return jsonify({'error': str(e)}), 500

# Parent Payment Routes
@app.route('/api/parent/pending-payments', methods=['GET'])
@jwt_required()
def get_parent_pending_payments():
    try:
        current_user_email = get_jwt_identity()
        
        # Get the parent record for this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        if not parent:
            return jsonify({'error': 'Parent not found'}), 404
        
        # Get pending payments directly by parent_id
        pending_payments = Payment.query.filter(
            Payment.parent_id == str(parent.id),
            Payment.status == 'pending'
        ).order_by(Payment.created_at.desc()).all()
        
        payment_list = []
        for payment in pending_payments:
            # Get child information
            child = Kid.query.get(payment.child_id)
            payment_list.append({
                'id': payment.id,
                'payment_id': payment.payment_id,
                'child_name': child.name if child else 'Unknown',
                'child_id': payment.child_id,
                'amount': payment.amount,
                'currency': payment.currency,
                'status': payment.status,
                'description': payment.description,
                'journey_date': payment.journey_date.isoformat() if payment.journey_date else None,
                'created_at': payment.created_at.isoformat() if payment.created_at else None,
                'payment_link': "https://outrankconsult.com/payment/KidMate/pay.php?link={}".format(payment.payment_id)
            })
        
        return jsonify({
            'success': True,
            'pending_payments': payment_list
        })
        
    except Exception as e:
        app.logger.exception("Error fetching parent pending payments:")
        return jsonify({'error': str(e)}), 500

@app.route('/api/parent/all-payments', methods=['GET'])
@jwt_required()
def get_parent_all_payments():
    """Get all payments (pending, completed, failed) for the authenticated parent"""
    try:
        current_user_email = get_jwt_identity()
        
        # Get the parent record for this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        if not parent:
            return jsonify({'error': 'Parent not found'}), 404
        
        # Get all payments for this parent (all statuses)
        all_payments = Payment.query.filter(
            Payment.parent_id == str(parent.id)
        ).order_by(Payment.created_at.desc()).all()
        
        payment_list = []
        for payment in all_payments:
            # Get child information
            child = Kid.query.get(payment.child_id)
            payment_list.append({
                'id': payment.id,
                'payment_id': payment.payment_id,
                'child_name': child.name if child else f"Child ID: {payment.child_id}",
                'child_id': payment.child_id,
                'amount': payment.amount,
                'currency': payment.currency,
                'status': payment.status,
                'description': payment.description,
                'journey_date': payment.journey_date.isoformat() if payment.journey_date else None,
                'created_at': payment.created_at.isoformat() if payment.created_at else None,
                'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
                'payment_method': payment.payment_method,
                'payment_link': "https://outrankconsult.com/payment/KidMate/pay.php?link={}".format(payment.payment_id)
            })
        
        return jsonify({
            'success': True,
            'payments': payment_list,
            'total_count': len(payment_list)
        })
        
    except Exception as e:
        app.logger.exception("Error fetching parent all payments:")
        return jsonify({'error': str(e)}), 500

@app.route('/api/parent/payment-details/<string:payment_id>', methods=['GET'])
@jwt_required()
def get_payment_details(payment_id):
    try:
        current_user_email = get_jwt_identity()
        
        # Get the parent record for this user
        parent = Parent.query.filter_by(user_email=current_user_email).first()
        if not parent:
            return jsonify({'error': 'Parent not found'}), 404
        
        # Get the payment
        payment = Payment.query.filter_by(payment_id=payment_id).first()
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Verify the payment belongs to this parent
        if payment.parent_id != str(parent.id):
            return jsonify({'error': 'Unauthorized access to this payment'}), 403
        
        # Get child information
        child = Kid.query.get(payment.child_id)
        if not child:
            return jsonify({'error': 'Child not found'}), 404
        
        payment_details = {
            'id': payment.id,
            'payment_id': payment.payment_id,
            'child_name': child.name,
            'child_id': payment.child_id,
            'amount': payment.amount,
            'currency': payment.currency,
            'status': payment.status,
            'description': payment.description,
            'journey_date': payment.journey_date.isoformat() if payment.journey_date else None,
            'created_at': payment.created_at.isoformat() if payment.created_at else None,
            'payment_link': "https://outrankconsult.com/payment/KidMate/pay.php?link={}".format(payment.payment_id)
        }
        
        return jsonify({
            'success': True,
            'payment_details': payment_details
        })
        
    except Exception as e:
        app.logger.exception("Error fetching payment details:")
        return jsonify({'error': str(e)}), 500

@app.route('/emailtest', methods=['GET', 'POST'])
def test_email():
    """Test endpoint to send sample emails"""
    try:
        # Handle GET request for testing
        if request.method == 'GET':
            return jsonify({
                "success": True,
                "message": "Email test endpoint is working!",
                "available_types": ["welcome", "pickup", "dropoff", "payment", "attendance"],
                "email_config": {
                    "server": app.config.get('MAIL_SERVER'),
                    "port": app.config.get('MAIL_PORT'),
                    "username": app.config.get('MAIL_USERNAME'),
                    "use_tls": app.config.get('MAIL_USE_TLS'),
                    "use_ssl": app.config.get('MAIL_USE_SSL')
                }
            })
        
        # Log the request details for debugging
        app.logger.info(f"Email test request received from IP: {request.remote_addr}")
        app.logger.info(f"Request headers: {dict(request.headers)}")
        app.logger.info(f"Request content type: {request.content_type}")
        
        # Handle both JSON and form data
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
        else:
            # Try to parse form data
            data = request.form.to_dict() if request.form else {}
            if not data:
                data = request.args.to_dict()
        
        app.logger.info(f"Parsed data: {data}")
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        email_type = data.get('type', 'welcome')
        recipient_email = data.get('email', 'daviddors12@gmail.com')
        recipient_name = data.get('name', 'David')
        
        app.logger.info(f"Testing email type: {email_type} to: {recipient_email}")
        
        if email_type == 'welcome':
            success = EmailService.send_welcome_email(recipient_email, recipient_name)
        elif email_type == 'pickup':
            success = EmailService.send_pickup_notification(
                recipient_email, 
                recipient_name, 
                "Test Child", 
                "Test Pickup Person", 
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        elif email_type == 'dropoff':
            success = EmailService.send_dropoff_notification(
                recipient_email,
                recipient_name,
                "Test Child",
                "Test Location",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        elif email_type == 'payment':
            success = EmailService.send_payment_confirmation(
                recipient_email,
                recipient_name,
                50.00,
                "TEST_PAYMENT_123",
                datetime.now().strftime("%Y-%m-%d")
            )
        elif email_type == 'attendance':
            success = EmailService.send_attendance_notification(
                recipient_email,
                recipient_name,
                "Test Child",
                datetime.now().strftime("%Y-%m-%d"),
                "Present"
            )
        elif email_type == 'journey_status':
            success = EmailService.send_journey_status_notification(
                recipient_email,
                recipient_name,
                "Test Child",
                "Test Pickup Person",
                "departed",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        elif email_type == 'status_pending':
            success = EmailService.send_journey_status_notification(
                recipient_email,
                recipient_name,
                "Test Child",
                "Test Pickup Person",
                "pending",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        elif email_type == 'status_departed':
            success = EmailService.send_journey_status_notification(
                recipient_email,
                recipient_name,
                "Test Child",
                "Test Pickup Person",
                "departed",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        elif email_type == 'status_picked':
            success = EmailService.send_journey_status_notification(
                recipient_email,
                recipient_name,
                "Test Child",
                "Test Pickup Person",
                "picked",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        else:
            return jsonify({"error": "Invalid email type. Use: welcome, pickup, dropoff, payment, attendance, journey_status, status_pending, status_departed, status_picked"}), 400

        if success:
            return jsonify({
                "success": True,
                "message": f"{email_type} email sent successfully to {recipient_email}",
                "email_type": email_type,
                "recipient": recipient_email
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": f"Failed to send {email_type} email to {recipient_email}",
                "email_type": email_type,
                "recipient": recipient_email
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error in email test: {str(e)}")
        return jsonify({"error": f"Email test failed: {str(e)}"}), 500

@app.route('/test_email_direct', methods=['POST'])
def test_email_direct():
    """Test email sending with hardcoded data"""
    try:
        app.logger.info("Starting direct email test...")
        
        # Test email sending with hardcoded data
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        app.logger.info("Calling EmailService.send_journey_status_notification...")
        
        # Send test email directly
        success = EmailService.send_journey_status_notification(
            "daviddors12@gmail.com",
            "Test Parent",
            "Test Child",
            "Test Pickup Person",
            "departed",
            current_time,
            "Direct test from backend"
        )
        
        app.logger.info(f"Email service returned: {success}")
        
        if success:
            return jsonify({
                "success": True,
                "message": "Test email sent directly to daviddors12@gmail.com",
                "timestamp": current_time
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Failed to send test email"
            }), 500
            
    except Exception as e:
        app.logger.error(f"Direct email test failed: {str(e)}")
        import traceback
        app.logger.error(f"Direct email test traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Email test failed: {str(e)}"}), 500

@app.route('/test_simple', methods=['GET'])
def test_simple():
    """Simple test endpoint"""
    try:
        app.logger.info("Simple test endpoint called")
        return jsonify({
            "success": True,
            "message": "Simple test working",
            "email_service_imported": "EmailService" in globals(),
            "mail_imported": "mail" in globals()
        }), 200
    except Exception as e:
        app.logger.error(f"Simple test failed: {str(e)}")
        return jsonify({"error": f"Simple test failed: {str(e)}"}), 500

@app.route('/create_test_data', methods=['POST'])
def create_test_data():
    """Create test data for mobile app"""
    try:
        app.logger.info("Creating test data for mobile app...")
        
        # Create test parent
        test_parent = User(
            id="parent-001",
            name="Test Parent",
            email="daviddors12@gmail.com",
            phone="1234567890"
        )
        
        # Create test child
        test_child = Kid(
            id="child-001",
            name="Test Child",
            parent_id="parent-001"
        )
        
        # Create test pickup person
        test_pickup_person = PickupPerson(
            id="person-001",
            name="Test Pickup Person",
            phone="0987654321"
        )
        
        # Add to database
        db.session.add(test_parent)
        db.session.add(test_child)
        db.session.add(test_pickup_person)
        db.session.commit()
        
        app.logger.info("Test data created successfully")
        
        return jsonify({
            "success": True,
            "message": "Test data created successfully",
            "parent_id": "parent-001",
            "child_id": "child-001", 
            "pickup_person_id": "person-001"
        }), 200
        
    except Exception as e:
        app.logger.error(f"Failed to create test data: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"Failed to create test data: {str(e)}"}), 500

@app.route('/api/check_data', methods=['GET'])
def check_data():
    """Check what data exists in the database"""
    try:
        app.logger.info("Checking database data...")
        
        # Get all users
        users = User.query.all()
        user_data = []
        for user in users:
            user_data.append({
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'role': user.role
            })
        
        # Get all kids
        kids = Kid.query.all()
        kid_data = []
        for kid in kids:
            kid_data.append({
                'id': kid.id,
                'name': kid.name,
                'age': kid.age,
                'grade': kid.grade,
                'school': kid.school,
                'parent_id': kid.parent_id
            })
        
        # Get all pickup persons
        pickup_persons = PickupPerson.query.all()
        pickup_data = []
        for person in pickup_persons:
            pickup_data.append({
                'id': person.id,
                'name': person.name,
                'phone': person.phone,
                'uuid': person.uuid,
                'is_active': person.is_active
            })
        
        # Get all journeys
        journeys = PickupJourney.query.all()
        journey_data = []
        for journey in journeys:
            journey_data.append({
                'pickup_id': journey.pickup_id,
                'parent_id': journey.parent_id,
                'child_id': journey.child_id,
                'pickup_person_id': journey.pickup_person_id,
                'status': journey.status,
                'timestamp': journey.timestamp.isoformat() if journey.timestamp else None
            })
        
        return jsonify({
            'success': True,
            'users': user_data,
            'kids': kid_data,
            'pickup_persons': pickup_data,
            'journeys': journey_data,
            'counts': {
                'users': len(user_data),
                'kids': len(kid_data),
                'pickup_persons': len(pickup_data),
                'journeys': len(journey_data)
            }
        }), 200
        
    except Exception as e:
        app.logger.error(f"Failed to check data: {str(e)}")
        return jsonify({"error": f"Failed to check data: {str(e)}"}), 500

@app.route('/api/create_real_user', methods=['POST'])
def create_real_user():
    """Create a real user for mobile app testing"""
    try:
        data = request.get_json()
        
        # Create a real parent user
        parent = User(
            name=data.get('name', 'Real Parent'),
            email=data.get('email', 'realparent@example.com'),
            phone=data.get('phone', '1234567890'),
            role='Parent'
        )
        
        # Create a real child
        child = Kid(
            name=data.get('child_name', 'Real Child'),
            age=data.get('child_age', 8),
            grade=data.get('child_grade', '3rd Grade'),
            school=data.get('child_school', 'Elementary School'),
            parent_id=parent.id
        )
        
        # Create a real pickup person
        pickup_person = PickupPerson(
            name=data.get('pickup_name', 'Real Pickup Person'),
            phone=data.get('pickup_phone', '0987654321'),
            uuid=data.get('pickup_uuid', 'real-uuid-123'),
            is_active=True
        )
        
        # Add to database
        db.session.add(parent)
        db.session.add(child)
        db.session.add(pickup_person)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Real user data created successfully',
            'data': {
                'parent_id': parent.id,
                'child_id': child.id,
                'pickup_person_id': pickup_person.id,
                'parent_name': parent.name,
                'child_name': child.name,
                'pickup_name': pickup_person.name
            }
        }), 200
        
    except Exception as e:
        app.logger.error(f"Failed to create real user: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"Failed to create real user: {str(e)}"}), 500

@app.route('/api/get_existing_user', methods=['GET'])
def get_existing_user():
    """Get existing user data for mobile app"""
    try:
        # Find the existing user
        user = User.query.filter_by(email='test22@gmail.com').first()
        
        if not user:
            return jsonify({"error": "User test22@gmail.com not found"}), 404
        
        # Find associated kids
        kids = Kid.query.filter_by(parent_id=user.id).all()
        kid_data = []
        for kid in kids:
            kid_data.append({
                'id': kid.id,
                'name': kid.name,
                'age': kid.age,
                'grade': kid.grade,
                'school': kid.school
            })
        
        # Find pickup persons
        pickup_persons = PickupPerson.query.filter_by(is_active=True).all()
        pickup_data = []
        for person in pickup_persons:
            pickup_data.append({
                'id': person.id,
                'name': person.name,
                'phone': person.phone,
                'uuid': person.uuid
            })
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'role': user.role
            },
            'kids': kid_data,
            'pickup_persons': pickup_data,
            'mobile_app_data': {
                'parent_id': str(user.id),  # Convert to string for mobile app
                'child_id': str(kids[0].id) if kids else None,
                'pickup_person_id': str(pickup_persons[0].id) if pickup_persons else None
            }
        }), 200
        
    except Exception as e:
        app.logger.error(f"Failed to get existing user: {str(e)}")
        return jsonify({"error": f"Failed to get existing user: {str(e)}"}), 500

@app.route('/api/setup_mobile_data', methods=['POST'])
def setup_mobile_data():
    """Setup real data for mobile app testing"""
    try:
        # Get existing user
        user = User.query.filter_by(email='test22@gmail.com').first()
        
        if not user:
            return jsonify({"error": "User test22@gmail.com not found"}), 404
        
        # Create a child for this user if it doesn't exist
        child = Kid.query.filter_by(parent_id=user.id).first()
        if not child:
            child = Kid(
                name="Test Child",
                age=10,
                grade="5th Grade",
                school="Elementary School",
                parent_id=user.id
            )
            db.session.add(child)
            db.session.commit()
        
        # Create a pickup person if it doesn't exist
        pickup_person = PickupPerson.query.filter_by(is_active=True).first()
        if not pickup_person:
            pickup_person = PickupPerson(
                name="Test Driver",
                phone="1234567890",
                uuid="driver-uuid-123",
                is_active=True
            )
            db.session.add(pickup_person)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Mobile app data setup complete',
            'data': {
                'parent_id': str(user.id),
                'child_id': str(child.id),
                'pickup_person_id': str(pickup_person.id),
                'parent_name': user.name,
                'child_name': child.name,
                'pickup_name': pickup_person.name,
                'parent_email': user.email
            }
        }), 200
        
    except Exception as e:
        app.logger.error(f"Failed to setup mobile data: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"Failed to setup mobile data: {str(e)}"}), 500

# Run server

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)    
