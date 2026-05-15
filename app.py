import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Use SQLite locally, Railway Postgres in production
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', 'super-secret-key-change-me')

db = SQLAlchemy(app)
jwt = JWTManager(app)

# --- MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='To Do') # To Do, In Progress, Done
    priority = db.Column(db.String(20), default='Medium')
    due_date = db.Column(db.DateTime)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))

# Create tables
with app.app_context():
    db.create_all()

# --- ROUTES ---
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    hashed_pw = generate_password_hash(data['password'], method='pbkdf2:sha256')
    new_user = User(name=data['name'], email=data['email'], password=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        token = create_access_token(identity=user.id)
        return jsonify(access_token=token, role="Admin") # Simplified for speed
    return jsonify({"message": "Invalid credentials"}), 401

@app.route('/api/projects', methods=['POST', 'GET'])
@jwt_required()
def projects():
    current_user_id = get_jwt_identity()
    if request.method == 'POST':
        data = request.json
        new_project = Project(name=data['name'], admin_id=current_user_id)
        db.session.add(new_project)
        db.session.commit()
        return jsonify({"message": "Project created", "id": new_project.id}), 201
    
    # GET: Return user's projects
    projs = Project.query.filter_by(admin_id=current_user_id).all()
    return jsonify([{"id": p.id, "name": p.name} for p in projs]), 200

# --- TASK AND DASHBOARD ROUTES ---

@app.route('/api/tasks', methods=['POST'])
@jwt_required()
def create_task():
    data = request.json
    new_task = Task(
        title=data['title'],
        description=data.get('description', ''),
        priority=data.get('priority', 'Medium'),
        project_id=data['project_id'],
        # Skipping assigned_to for MVP speed
    )
    db.session.add(new_task)
    db.session.commit()
    return jsonify({"message": "Task created"}), 201

@app.route('/api/tasks/<int:project_id>', methods=['GET'])
@jwt_required()
def get_tasks(project_id):
    tasks = Task.query.filter_by(project_id=project_id).all()
    return jsonify([{
        "id": t.id, "title": t.title, "status": t.status, 
        "priority": t.priority
    } for t in tasks]), 200

@app.route('/api/tasks/<int:task_id>/status', methods=['PUT'])
@jwt_required()
def update_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    task.status = request.json.get('status', task.status)
    db.session.commit()
    return jsonify({"message": "Status updated"}), 200

@app.route('/api/dashboard', methods=['GET'])
@jwt_required()
def dashboard():
    # Calculate stats required for the assignment
    total = Task.query.count()
    todo = Task.query.filter_by(status='To Do').count()
    in_progress = Task.query.filter_by(status='In Progress').count()
    done = Task.query.filter_by(status='Done').count()
    
    return jsonify({
        "total": total, "todo": todo, 
        "in_progress": in_progress, "done": done
    }), 200

@app.route('/')
def home():
    # This reads your HTML file and displays it at your main URL
    with open('frontend/index.html', 'r') as file:
        return file.read()


# Run locally
if __name__ == '__main__':
    app.run(debug=True, port=5000)