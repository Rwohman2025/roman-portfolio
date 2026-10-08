from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pastel-dynamic-key-2026'

# --- PERSISTENT STORAGE SETUP ---
# By putting both the DB and Uploads in a 'data' folder, you only need to mount ONE volume in Railway to /app/data
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(DATA_DIR, 'portfolio.db')}"
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
DOC_EXTENSIONS = {'pdf', 'docx', 'txt', 'step', 'stl', 'zip'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), default="Roman Macedo")
    tagline = db.Column(db.String(200), default="Designing Precision Systems")
    about = db.Column(db.Text, default="I am a mechanical engineering student bridging the gap between mechanical design, electrical hardware, and software integration.")
    skills = db.Column(db.String(300), default="SolidWorks, FEA Simulation, Python, Mechatronics")
    email = db.Column(db.String(100), default="your.email@example.com")
    linkedin = db.Column(db.String(200), default="#")
    resume_file = db.Column(db.String(200))

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    skills = db.Column(db.String(200))
    image_file = db.Column(db.String(200))
    doc_file = db.Column(db.String(200))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---
@app.route('/')
def index():
    profile = Profile.query.first()
    projects = Project.query.order_by(Project.id.desc()).all()
    # Safely split skills string for badges
    skills_list = [s.strip() for s in profile.skills.split(',')] if profile and profile.skills else []
    return render_template('index.html', profile=profile, projects=projects, skills_list=skills_list)

@app.route('/project/<int:id>')
def project_detail(id):
    project = Project.query.get_or_404(id)
    return render_template('project.html', project=project)

# Serve files from the persistent data directory
@app.route('/files/<filename>')
def serve_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    profile = Profile.query.first()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # HANDLE PROFILE UPDATE
        if action == 'update_profile':
            profile.name = request.form.get('name')
            profile.tagline = request.form.get('tagline')
            profile.about = request.form.get('about')
            profile.skills = request.form.get('skills')
            profile.email = request.form.get('email')
            profile.linkedin = request.form.get('linkedin')
            
            resume = request.files.get('resume')
            if resume and allowed_file(resume.filename, DOC_EXTENSIONS):
                resume_filename = secure_filename(resume.filename)
                resume.save(os.path.join(app.config['UPLOAD_FOLDER'], resume_filename))
                profile.resume_file = resume_filename
                
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('dashboard'))
            
        # HANDLE ADD PROJECT
        elif action == 'add_project':
            title = request.form.get('title')
            description = request.form.get('description')
            skills = request.form.get('skills')
            
            image_file = request.files.get('image')
            doc_file = request.files.get('document')
            
            image_filename = doc_filename = None
            
            if image_file and allowed_file(image_file.filename, IMAGE_EXTENSIONS):
                image_filename = secure_filename(image_file.filename)
                image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            if doc_file and allowed_file(doc_file.filename, DOC_EXTENSIONS):
                doc_filename = secure_filename(doc_file.filename)
                doc_file.save(os.path.join(app.config['UPLOAD_FOLDER'], doc_filename))
                
            new_project = Project(title=title, description=description, skills=skills, 
                                  image_file=image_filename, doc_file=doc_filename)
            db.session.add(new_project)
            db.session.commit()
            flash('Project added successfully.', 'success')
            return redirect(url_for('dashboard'))
            
    projects = Project.query.order_by(Project.id.desc()).all()
    return render_template('dashboard.html', profile=profile, projects=projects)

@app.route('/delete/<int:id>')
@login_required
def delete_project(id):
    project = Project.query.get_or_404(id)
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted.', 'info')
    return redirect(url_for('dashboard'))

def setup_database():
    with app.app_context():
        db.create_all()
        # Create admin
        if not User.query.filter_by(username='admin').first():
            hashed_pw = generate_password_hash('engineering2026', method='pbkdf2:sha256')
            admin = User(username='admin', password=hashed_pw)
            db.session.add(admin)
        
        # Create default profile
        if not Profile.query.first():
            default_profile = Profile()
            db.session.add(default_profile)
            
        db.session.commit()

setup_database()
if __name__ == '__main__':
 
    app.run(debug=True, port=5000)
