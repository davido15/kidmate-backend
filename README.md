# KidMate Backend

A Flask-based REST API for the KidMate child pickup management system.

## Features

- User authentication and authorization
- Child and parent management
- Pickup person management
- Journey tracking with drop-off location
- Payment processing
- Real-time status updates
- Database migrations with Alembic

## Tech Stack

- **Framework**: Flask
- **Database**: MySQL
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Authentication**: JWT
- **CORS**: Flask-CORS

## Setup

### Prerequisites

- Python 3.8+
- MySQL 8.0+
- pip

### Installation

1. Clone the repository:
```bash
git clone https://github.com/davido15/kidmate-backend.git
cd kidmate-backend
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the root directory:
```
FLASK_APP=app.py
FLASK_ENV=development
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/kidmate_db
JWT_SECRET_KEY=your_jwt_secret_key
```

5. Set up the database:
```bash
# Initialize migrations
flask db init

# Create initial migration
flask db migrate -m "Initial migration"

# Apply migrations
flask db upgrade
```

6. Run the application:
```bash
flask run
```

## API Endpoints

### Authentication
- `POST /api/login` - User login
- `POST /api/register` - User registration
- `POST /api/refresh` - Refresh JWT token

### Pickup Management
- `POST /api/assign-pickup` - Create pickup person
- `GET /api/get-pickup-persons` - Get pickup persons
- `PUT /api/toggle-pickup-person-status/<id>` - Toggle pickup person status

### Journey Management
- `POST /api/create-journey` - Create new journey with drop-off location
- `POST /update_status` - Update journey status
- `GET /get_user_journeys` - Get user journeys
- `GET /api/get-journey-details/<pickup_id>` - Get journey details

### Children Management
- `POST /api/add-kid` - Add child
- `GET /api/get-children` - Get children

## Database Schema

### Key Models

**PickupPerson:**
- Basic person information (name, phone, image)
- Associated with child via kid_id
- No longer contains drop-off location

**PickupJourney:**
- Journey tracking with status updates
- Contains drop-off location (name, coordinates)
- Links parent, child, and pickup person

## Security

- JWT-based authentication
- Environment variables for sensitive data
- CORS configuration
- Input validation and sanitization

## Development

### Running Migrations

```bash
# Create new migration
flask db migrate -m "Description of changes"

# Apply migrations
flask db upgrade

# Rollback migration
flask db downgrade
```

### Testing

```bash
# Run tests
python -m pytest

# Run with coverage
python -m pytest --cov=app
```

## Deployment

1. Set production environment variables
2. Configure production database
3. Set up reverse proxy (nginx)
4. Use production WSGI server (gunicorn)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License. 