import os
import json
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'alpha_research_secret_key_99x8'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==============================================================================
# Database Models
# ==============================================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    referral_code = db.Column(db.String(10), unique=True, nullable=False)
    referred_by = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    responses = db.relationship('SurveyResponse', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    reward = db.Column(db.Float, nullable=False)
    estimated_time = db.Column(db.Integer, nullable=False)  # in minutes
    rating = db.Column(db.Float, default=5.0)
    category = db.Column(db.String(50), default='General')
    questions_json = db.Column(db.Text, nullable=False)  # JSON formatted list of questions

    def get_questions(self):
        return json.loads(self.questions_json)

class SurveyResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    responses_json = db.Column(db.Text, nullable=False)  # JSON formatted answers
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'earnings' or 'withdrawal'
    status = db.Column(db.String(20), default='completed')  # 'completed', 'pending', 'failed'
    method = db.Column(db.String(50), nullable=True)  # 'PayPal', 'UPI/Paytm', 'Amazon', etc.
    details = db.Column(db.String(150), nullable=True)  # Target email/phone
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ==============================================================================
# Helper Functions & Decorators
# ==============================================================================

def generate_ref_code():
    """Generate a unique 6-character uppercase referral code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        # Ensure uniqueness
        if not User.query.filter_by(referral_code=code).first():
            return code

def login_required(f):
    """Decorator to protect routes that require authentication."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in or sign up first.', 'info')
            return redirect(url_for('login'))
        
        # Load user into globally accessible Flask 'g' object
        g.user = User.query.get(session['user_id'])
        if not g.user:
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# Route Handlers
# ==============================================================================

@app.route('/')
@login_required
def dashboard():
    # Fetch surveys that the user hasn't completed yet
    completed_survey_ids = [r.survey_id for r in SurveyResponse.query.filter_by(user_id=g.user.id).all()]
    
    available_surveys = Survey.query.filter(~Survey.id.in_(completed_survey_ids) if completed_survey_ids else True).all()
    
    # Calculate progress toward withdrawal goal (e.g., $50 threshold)
    threshold = 50.0
    progress_percent = min(100, int((g.user.balance / threshold) * 100))
    
    return render_template(
        'dashboard.html', 
        surveys=available_surveys, 
        progress_percent=progress_percent,
        threshold=threshold,
        active_tab='home'
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        action = request.form.get('action') # 'login' or 'register'
        
        if action == 'login':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                flash(f'Welcome back, {user.username}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.', 'error')
                
        elif action == 'register':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            ref_code_entered = request.form.get('referral_code', '').strip().upper()
            
            # Validation
            if not username or not email or not password:
                flash('All fields are required.', 'error')
                return render_template('login.html')
                
            if User.query.filter_by(email=email).first():
                flash('Email is already registered.', 'error')
                return render_template('login.html')
                
            if User.query.filter_by(username=username).first():
                flash('Username is already taken.', 'error')
                return render_template('login.html')
                
            referred_by_user = None
            if ref_code_entered:
                referred_by_user = User.query.filter_by(referral_code=ref_code_entered).first()
                if not referred_by_user:
                    flash('Invalid referral code. Registering without bonus.', 'warning')
            
            # Create user
            hashed_pwd = generate_password_hash(password)
            new_code = generate_ref_code()
            
            # Give welcome bonus (e.g., $2) if they used a referral code, or nothing if normal
            initial_balance = 2.0 if referred_by_user else 0.0
            
            new_user = User(
                username=username,
                email=email,
                password_hash=hashed_pwd,
                balance=initial_balance,
                referral_code=new_code,
                referred_by=referred_by_user.referral_code if referred_by_user else None
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            # Credit the referrer (e.g., $5) instantly
            if referred_by_user:
                referred_by_user.balance += 5.0
                ref_txn = Transaction(
                    user_id=referred_by_user.id,
                    amount=5.0,
                    type='earnings',
                    status='completed',
                    method='Referral Bonus',
                    details=f'Referred {username}'
                )
                db.session.add(ref_txn)
                
                # Create a welcome balance txn for the new user too
                new_user_txn = Transaction(
                    user_id=new_user.id,
                    amount=2.0,
                    type='earnings',
                    status='completed',
                    method='Welcome Bonus',
                    details='Used referral code'
                )
                db.session.add(new_user_txn)
                db.session.commit()
                
            session['user_id'] = new_user.id
            flash('Registration successful! Welcome to Alpha Research Server.', 'success')
            return redirect(url_for('dashboard'))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/survey/<int:survey_id>')
@login_required
def survey_run(survey_id):
    survey = Survey.query.get_or_404(survey_id)
    
    # Check if already completed
    existing = SurveyResponse.query.filter_by(user_id=g.user.id, survey_id=survey_id).first()
    if existing:
        flash('You have already completed this survey.', 'info')
        return redirect(url_for('dashboard'))
        
    questions = survey.get_questions()
    return render_template('survey_run.html', survey=survey, questions=questions)

@app.route('/survey/<int:survey_id>/submit', methods=['POST'])
@login_required
def survey_submit(survey_id):
    survey = Survey.query.get_or_404(survey_id)
    
    existing = SurveyResponse.query.filter_by(user_id=g.user.id, survey_id=survey_id).first()
    if existing:
        return jsonify({'success': False, 'message': 'Survey already completed.'}), 400
        
    responses = {}
    for key, value in request.form.items():
        if key.startswith('q_'):
            responses[key] = value
            
    # Save response
    survey_response = SurveyResponse(
        user_id=g.user.id,
        survey_id=survey_id,
        responses_json=json.dumps(responses)
    )
    db.session.add(survey_response)
    
    # Credit reward
    g.user.balance += survey.reward
    
    # Create Transaction
    txn = Transaction(
        user_id=g.user.id,
        amount=survey.reward,
        type='earnings',
        status='completed',
        method='Survey Earnings',
        details=f'Completed survey: {survey.title}'
    )
    db.session.add(txn)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Thank you! ${survey.reward:.2f} credited to your wallet.',
        'reward': survey.reward,
        'new_balance': g.user.balance
    })

@app.route('/wallet', methods=['GET', 'POST'])
@login_required
def wallet():
    threshold = 50.0
    if request.method == 'POST':
        method = request.form.get('method')
        details = request.form.get('details', '').strip()
        amount_to_withdraw = g.user.balance
        
        if amount_to_withdraw < threshold:
            flash(f'Minimum withdrawal limit is ${threshold:.2f}.', 'error')
            return redirect(url_for('wallet'))
            
        if not details:
            flash('Please enter the payout destination (UPI ID or Email).', 'error')
            return redirect(url_for('wallet'))
            
        # Deduct balance & log transaction
        g.user.balance = 0.0
        
        txn = Transaction(
            user_id=g.user.id,
            amount=-amount_to_withdraw,
            type='withdrawal',
            status='pending',
            method=method,
            details=details
        )
        db.session.add(txn)
        db.session.commit()
        
        flash(f'Withdrawal request of ${amount_to_withdraw:.2f} submitted successfully! It will be processed in 24 hours.', 'success')
        return redirect(url_for('wallet'))
        
    # Get transaction history
    transactions = Transaction.query.filter_by(user_id=g.user.id).order_by(Transaction.timestamp.desc()).all()
    progress_percent = min(100, int((g.user.balance / threshold) * 100))
    
    return render_template(
        'wallet.html', 
        transactions=transactions, 
        progress_percent=progress_percent,
        threshold=threshold,
        active_tab='wallet'
    )

@app.route('/referrals')
@login_required
def referrals():
    # Count friends invited
    referred_users = User.query.filter_by(referred_by=g.user.referral_code).all()
    count = len(referred_users)
    
    # Calculate referral earnings
    ref_transactions = Transaction.query.filter_by(user_id=g.user.id, method='Referral Bonus').all()
    earnings = sum(t.amount for t in ref_transactions)
    
    return render_template(
        'referrals.html', 
        referral_code=g.user.referral_code, 
        count=count, 
        earnings=earnings,
        referred_users=referred_users,
        active_tab='invite'
    )

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        
        if not username or not email:
            flash('Username and email cannot be empty.', 'error')
        else:
            # Check collisions
            existing_email = User.query.filter(User.email == email, User.id != g.user.id).first()
            existing_username = User.query.filter(User.username == username, User.id != g.user.id).first()
            
            if existing_email:
                flash('Email is already in use by another account.', 'error')
            elif existing_username:
                flash('Username is already taken.', 'error')
            else:
                g.user.username = username
                g.user.email = email
                db.session.commit()
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('profile'))
                
    # Calculate stats
    completed_responses = SurveyResponse.query.filter_by(user_id=g.user.id).all()
    completed_count = len(completed_responses)
    
    all_earnings = Transaction.query.filter(Transaction.user_id == g.user.id, Transaction.amount > 0).all()
    total_earned = sum(t.amount for t in all_earnings)
    
    return render_template(
        'profile.html', 
        completed_count=completed_count, 
        total_earned=total_earned,
        active_tab='profile'
    )

# ==============================================================================
# Database Seeding
# ==============================================================================

def seed_surveys():
    """Initial surveys to give users high-quality content right away."""
    if Survey.query.first():
        return # Already seeded
        
    surveys_data = [
        {
            "title": "⚡️ Quick Onboarding Survey",
            "reward": 5.0,
            "estimated_time": 2,
            "rating": 5.0,
            "category": "Onboarding",
            "questions": [
                {
                    "id": "q1",
                    "text": "What is your gender?",
                    "type": "single_choice",
                    "options": ["Male", "Female", "Non-binary", "Prefer not to say"]
                },
                {
                    "id": "q2",
                    "text": "What is your age range?",
                    "type": "single_choice",
                    "options": ["Under 18", "18-24", "25-34", "35-44", "45+"]
                },
                {
                    "id": "q3",
                    "text": "How did you find this survey application?",
                    "type": "single_choice",
                    "options": ["Google Play Store", "Friend recommendation", "Online Advertisement", "Social Media", "Other"]
                }
            ]
        },
        {
            "title": "📱 Mobile Tech & Brands Preference",
            "reward": 8.0,
            "estimated_time": 5,
            "rating": 4.8,
            "category": "Technology",
            "questions": [
                {
                    "id": "q1",
                    "text": "Which mobile operating system do you currently use?",
                    "type": "single_choice",
                    "options": ["Android (Google OS)", "iOS (Apple iPhone)", "Both / Use different ones", "Feature phone / Custom OS"]
                },
                {
                    "id": "q2",
                    "text": "How many smart devices do you own (Smartwatch, Smart Speaker, Apple TV, etc.)?",
                    "type": "single_choice",
                    "options": ["None", "1 - 2 devices", "3 - 5 devices", "More than 5 devices"]
                },
                {
                    "id": "q3",
                    "text": "Which tech brand do you find most innovative in terms of designs?",
                    "type": "single_choice",
                    "options": ["Apple", "Samsung", "Google", "OnePlus / Xiaomi", "Sony"]
                },
                {
                    "id": "q4",
                    "text": "Are you planning to upgrade your primary smartphone within the next 6 months?",
                    "type": "single_choice",
                    "options": ["Yes, definitely", "Probably yes", "Maybe / Unsure", "No, happy with my current device"]
                }
            ]
        },
        {
            "title": "🍔 Food Delivery & Dining Habits",
            "reward": 12.0,
            "estimated_time": 10,
            "rating": 4.6,
            "category": "Lifestyle",
            "questions": [
                {
                    "id": "q1",
                    "text": "How many times per week do you order food online from delivery apps?",
                    "type": "single_choice",
                    "options": ["Never / Dine out only", "1 - 2 times per week", "3 - 5 times per week", "Daily or more"]
                },
                {
                    "id": "q2",
                    "text": "Which delivery platform do you use the most?",
                    "type": "single_choice",
                    "options": ["Zomato", "Swiggy", "Direct Restaurant Call", "Uber Eats / EatSure / Others"]
                },
                {
                    "id": "q3",
                    "text": "What type of food do you order most frequently?",
                    "type": "single_choice",
                    "options": ["Indian Main Course", "Biryani / Rice dishes", "Pizzas & Burgers", "Chinese / Pan-Asian", "Cakes & Desserts"]
                },
                {
                    "id": "q4",
                    "text": "What is the single most important factor for you when choosing a restaurant online?",
                    "type": "single_choice",
                    "options": ["Customer reviews & ratings", "Discounts, offers & free delivery", "Speed of delivery", "Hygiene certification"]
                }
            ]
        },
        {
            "title": "✈️ Travel & Vacation Destinations",
            "reward": 15.0,
            "estimated_time": 15,
            "rating": 4.7,
            "category": "Travel",
            "questions": [
                {
                    "id": "q1",
                    "text": "How many leisure trips (vacations) do you take annually?",
                    "type": "single_choice",
                    "options": ["None / Staycations", "1 trip", "2 - 3 trips", "4 or more trips"]
                },
                {
                    "id": "q2",
                    "text": "What is your primary choice of transportation for holidays?",
                    "type": "single_choice",
                    "options": ["Flight", "Express Train", "Personal car / Road trip", "Interstate Bus service"]
                },
                {
                    "id": "q3",
                    "text": "What type of environment do you prefer for your vacation destinations?",
                    "type": "single_choice",
                    "options": ["Beaches & Coastal resorts", "Mountain hill stations & Snow", "Historical/Cultural heritage sites", "National parks & Wildlife safaris", "Metropolitan cities & shopping hubs"]
                },
                {
                    "id": "q4",
                    "text": "How do you usually book your accommodations?",
                    "type": "single_choice",
                    "options": ["MakeMyTrip / Agoda / Booking.com", "Airbnb / Homestays", "Directly contacting hotels", "Travel agencies / Packages"]
                }
            ]
        },
        {
            "title": "📺 Entertainment & Streaming Consumption",
            "reward": 6.0,
            "estimated_time": 4,
            "rating": 4.5,
            "category": "Entertainment",
            "questions": [
                {
                    "id": "q1",
                    "text": "Which video streaming service do you watch the most?",
                    "type": "single_choice",
                    "options": ["Netflix", "Amazon Prime Video", "Disney+ Hotstar / JioCinema", "YouTube (Free content)", "Traditional Cable TV"]
                },
                {
                    "id": "q2",
                    "text": "On average, how many hours do you spend watching streaming platforms per day?",
                    "type": "single_choice",
                    "options": ["Under 1 hour", "1 - 2 hours", "3 - 4 hours", "More than 4 hours"]
                },
                {
                    "id": "q3",
                    "text": "Do you prefer watching newly released movies at cinema halls or on OTT?",
                    "type": "single_choice",
                    "options": ["Always Cinema Halls", "Mostly Cinema Halls, occasionally OTT", "Mostly OTT, occasionally Cinema", "Always OTT at home"]
                }
            ]
        }
    ]

    for s in surveys_data:
        new_survey = Survey(
            title=s['title'],
            reward=s['reward'],
            estimated_time=s['estimated_time'],
            rating=s['rating'],
            category=s['category'],
            questions_json=json.dumps(s['questions'])
        )
        db.session.add(new_survey)
    db.session.commit()

# Initialize DB tables and seed them within context
with app.app_context():
    db.create_all()
    seed_surveys()

if __name__ == '__main__':
    # Running locally on port 5500
    app.run(host='0.0.0.0', port=5500, debug=True)
