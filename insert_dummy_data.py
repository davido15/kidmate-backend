from app import app, db
from models import AdminUser, Term, Subject, Class, Grade
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from datetime import date

def insert_dummy_data():
    with app.app_context():
        try:
            # Check and insert Admin Users (only if they don't exist)
            print("Checking admin users...")
            existing_admin = db.session.execute(text("SELECT COUNT(*) FROM admin_users")).scalar()
            if existing_admin == 0:
                print("Inserting admin users...")
                db.session.execute(text("""
                    INSERT INTO admin_users (username, email, password_hash, role) 
                    VALUES 
                    ('admin1', 'admin1@school.com', :hash1, 'admin'),
                    ('admin2', 'admin2@school.com', :hash2, 'admin'),
                    ('principal', 'principal@school.com', :hash3, 'principal')
                """), {
                    'hash1': generate_password_hash('password123'),
                    'hash2': generate_password_hash('password123'),
                    'hash3': generate_password_hash('password123')
                })
            else:
                print(f"Admin users already exist ({existing_admin} found)")
            
            # Check and insert Terms
            print("Checking terms...")
            existing_terms = db.session.execute(text("SELECT COUNT(*) FROM terms")).scalar()
            if existing_terms == 0:
                print("Inserting terms...")
                db.session.execute(text("""
                    INSERT INTO terms (term_code, term_name, start_date, end_date, is_active) 
                    VALUES 
                    ('2024-1', 'First Term 2024', '2024-09-01', '2024-12-15', TRUE),
                    ('2024-2', 'Second Term 2024', '2025-01-15', '2025-04-30', TRUE),
                    ('2024-3', 'Third Term 2024', '2025-05-15', '2025-08-31', FALSE)
                """))
            else:
                print(f"Terms already exist ({existing_terms} found)")
            
            # Check and insert Subjects
            print("Checking subjects...")
            existing_subjects = db.session.execute(text("SELECT COUNT(*) FROM subjects")).scalar()
            if existing_subjects == 0:
                print("Inserting subjects...")
                db.session.execute(text("""
                    INSERT INTO subjects (subject_code, subject_name, description, is_active) 
                    VALUES 
                    ('MATH', 'Mathematics', 'Core mathematics including algebra, geometry, and calculus', TRUE),
                    ('ENG', 'English Language', 'English language and literature studies', TRUE),
                    ('SCI', 'Science', 'General science including physics, chemistry, and biology', TRUE),
                    ('HIST', 'History', 'World history and social studies', TRUE),
                    ('GEO', 'Geography', 'Physical and human geography', TRUE),
                    ('ART', 'Art and Design', 'Creative arts and design studies', TRUE),
                    ('PE', 'Physical Education', 'Sports and physical fitness', TRUE),
                    ('MUSIC', 'Music', 'Music theory and performance', TRUE)
                """))
            else:
                print(f"Subjects already exist ({existing_subjects} found)")
            
            # Check and insert Classes
            print("Checking classes...")
            existing_classes = db.session.execute(text("SELECT COUNT(*) FROM classes")).scalar()
            if existing_classes == 0:
                print("Inserting classes...")
                db.session.execute(text("""
                    INSERT INTO classes (class_code, class_name, grade_level, teacher_name, room_number, is_active) 
                    VALUES 
                    ('GRADE1A', 'Grade 1A', 'Grade 1', 'Mrs. Johnson', 'Room 101', TRUE),
                    ('GRADE1B', 'Grade 1B', 'Grade 1', 'Mr. Smith', 'Room 102', TRUE),
                    ('GRADE2A', 'Grade 2A', 'Grade 2', 'Ms. Davis', 'Room 201', TRUE),
                    ('GRADE2B', 'Grade 2B', 'Grade 2', 'Mrs. Wilson', 'Room 202', TRUE),
                    ('GRADE3A', 'Grade 3A', 'Grade 3', 'Mr. Brown', 'Room 301', TRUE),
                    ('GRADE3B', 'Grade 3B', 'Grade 3', 'Ms. Taylor', 'Room 302', TRUE),
                    ('GRADE4A', 'Grade 4A', 'Grade 4', 'Mrs. Anderson', 'Room 401', TRUE),
                    ('GRADE4B', 'Grade 4B', 'Grade 4', 'Mr. Martinez', 'Room 402', TRUE),
                    ('GRADE5A', 'Grade 5A', 'Grade 5', 'Ms. Garcia', 'Room 501', TRUE),
                    ('GRADE5B', 'Grade 5B', 'Grade 5', 'Mrs. Rodriguez', 'Room 502', TRUE)
                """))
            else:
                print(f"Classes already exist ({existing_classes} found)")
            
            # Check and insert Grades (using actual kid IDs that exist)
            print("Checking grades...")
            existing_grades = db.session.execute(text("SELECT COUNT(*) FROM grades")).scalar()
            if existing_grades == 0:
                print("Inserting grades...")
                db.session.execute(text("""
                    INSERT INTO grades (kid_id, subject, grade, remarks, comments, date_recorded) 
                    VALUES 
                    (5, 'Mathematics', 'A', 'Excellent work', 'Shows strong problem-solving skills', '2024-12-10'),
                    (5, 'English Language', 'B+', 'Good progress', 'Reading comprehension is improving', '2024-12-10'),
                    (5, 'Science', 'A-', 'Very good', 'Demonstrates good understanding of concepts', '2024-12-10'),
                    (6, 'Mathematics', 'B', 'Satisfactory', 'Needs more practice with fractions', '2024-12-10'),
                    (6, 'English Language', 'A', 'Outstanding', 'Excellent writing skills', '2024-12-10'),
                    (6, 'Science', 'B+', 'Good work', 'Shows interest in experiments', '2024-12-10'),
                    (7, 'Mathematics', 'C+', 'Needs improvement', 'Requires additional support', '2024-12-10'),
                    (7, 'English Language', 'B', 'Satisfactory', 'Good oral communication', '2024-12-10'),
                    (7, 'Science', 'A', 'Excellent', 'Very creative in science projects', '2024-12-10'),
                    (8, 'Mathematics', 'A+', 'Exceptional', 'Advanced mathematical thinking', '2024-12-10'),
                    (8, 'English Language', 'A', 'Excellent', 'Strong vocabulary and grammar', '2024-12-10'),
                    (8, 'Science', 'A+', 'Outstanding', 'Excellent scientific reasoning', '2024-12-10'),
                    (9, 'Mathematics', 'B-', 'Satisfactory', 'Working on improving accuracy', '2024-12-10'),
                    (9, 'English Language', 'C+', 'Needs support', 'Requires reading intervention', '2024-12-10'),
                    (9, 'Science', 'B', 'Good progress', 'Shows improvement in understanding', '2024-12-10'),
                    (10, 'Mathematics', 'A', 'Very good', 'Consistent performance', '2024-12-10'),
                    (10, 'English Language', 'B+', 'Good work', 'Improving in writing', '2024-12-10'),
                    (10, 'Science', 'A-', 'Excellent', 'Shows great curiosity', '2024-12-10'),
                    (11, 'Mathematics', 'B+', 'Good progress', 'Working hard on concepts', '2024-12-10'),
                    (11, 'English Language', 'A-', 'Very good', 'Strong communication skills', '2024-12-10'),
                    (11, 'Science', 'B', 'Satisfactory', 'Participates well in experiments', '2024-12-10')
                """))
            else:
                print(f"Grades already exist ({existing_grades} found)")
            
            db.session.commit()
            print("✅ All dummy data inserted successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error inserting dummy data: {e}")

if __name__ == "__main__":
    insert_dummy_data() 