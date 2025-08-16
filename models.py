from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True)
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(50), default="Parent")
    image = db.Column(db.String(255))
    push_token = db.Column(db.String(255))

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    def set_role(self, role):
        self.role = role


class Parent(db.Model):
    __tablename__ = 'parents'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(15))
    address = db.Column(db.String(255))
    occupation = db.Column(db.String(100))
    relationship = db.Column(db.String(50))
    image = db.Column(db.String(255))
    push_token = db.Column(db.String(255))
    user_email = db.Column(db.String(100), db.ForeignKey('users.email'), nullable=True)


class Kid(db.Model):
    __tablename__ = 'kids'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    grade = db.Column(db.String(20))
    school = db.Column(db.String(100))
    image = db.Column(db.String(255))
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'))
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())


class PickupPerson(db.Model):
    __tablename__ = 'pickup_persons'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(100))
    image = db.Column(db.String(255))
    pickup_id = db.Column(db.String(100))
    kid_id = db.Column(db.Integer, db.ForeignKey('kids.id'))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

class PickupJourney(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pickup_id = db.Column(db.String(36), nullable=False)
    parent_id = db.Column(db.String(36), nullable=False)
    child_id = db.Column(db.String(36), nullable=False)
    pickup_person_id = db.Column(db.String(36), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    dropoff_location = db.Column(db.String(255))
    dropoff_latitude = db.Column(db.Float)
    dropoff_longitude = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, server_default=func.current_timestamp())

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.String(36), unique=True, nullable=False)
    parent_id = db.Column(db.String(36), nullable=False)
    child_id = db.Column(db.String(36), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default="USD")
    status = db.Column(db.String(20), default="pending")  # pending, completed, failed, refunded
    payment_method = db.Column(db.String(50), default="card")  # card, cash, mobile_money
    description = db.Column(db.String(255))
    journey_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())    

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    attendance_id = db.Column(db.String(36), unique=True, nullable=False)
    child_id = db.Column(db.String(36), nullable=False)
    child_name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.String(36), nullable=False)
    parent_name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    check_in_time = db.Column(db.DateTime)
    check_out_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="present")  # present, absent, late, early_dismissal
    notes = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())


class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(36), unique=True, nullable=False)
    user_email = db.Column(db.String(100), db.ForeignKey('users.email'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=True)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default="general")  # general, technical, billing, service
    priority = db.Column(db.String(20), default="medium")  # low, medium, high, urgent
    status = db.Column(db.String(20), default="open")  # open, in_progress, closed
    assigned_to = db.Column(db.String(100), nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="admin")
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)


class Term(db.Model):
    __tablename__ = 'terms'
    id = db.Column(db.Integer, primary_key=True)
    term_code = db.Column(db.String(20), unique=True, nullable=False)
    term_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    subject_code = db.Column(db.String(20), unique=True, nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    class_code = db.Column(db.String(20), unique=True, nullable=False)
    class_name = db.Column(db.String(100), nullable=False)
    grade_level = db.Column(db.String(20))
    teacher_name = db.Column(db.String(100))
    room_number = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    kid_id = db.Column(db.Integer, db.ForeignKey('kids.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    remarks = db.Column(db.String(255))
    comments = db.Column(db.Text)
    date_recorded = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationship
    kid = db.relationship('Kid', backref='grades')
