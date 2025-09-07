from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "supersecretkey"  # for flash messages and sessions

# SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    company_name = db.Column(db.String(150))
    role = db.Column(db.String(100))

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    industry = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    users = db.relationship('UserCompany', back_populates='company')
    transactions = db.relationship('Transaction', backref='company', lazy=True)

class UserCompany(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    user = db.relationship('User', backref='companies')
    company = db.relationship('Company', back_populates='users')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200))
    amount = db.Column(db.Float)
    type = db.Column(db.String(10))  # Debit or Credit

# Initialize DB
with app.app_context():
    db.create_all()

# ----------------- Routes ----------------- #

# Home page
@app.route("/")
def index():
    return render_template("index.html")


# Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        company_name = request.form['company_name']
        role = request.form['role']

        # Check password match
        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for('register'))

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered", "danger")
            return redirect(url_for('register'))

        # Hash password
        # Hash password securely
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')


        # Create new user
        new_user = User(full_name=full_name, email=email,
                        password=hashed_password,
                        company_name=company_name, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template("register.html")

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash("Invalid email or password", "danger")
            return redirect(url_for('login'))

        session['user_id'] = user.id
        session['user_name'] = user.full_name
        flash(f"Welcome back, {user.full_name}!", "success")
        return redirect(url_for('dashboard'))

    return render_template("login.html")

# Dashboard (example protected page)
# Dashboard / Workspace
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access your workspace", "warning")
        return redirect(url_for('login'))

    # Get the logged-in user
    user = User.query.get(session['user_id'])

    # Get all companies assigned to this user
    user_companies = [uc.company for uc in user.companies]

    # Determine selected company
    selected_company_id = request.form.get('company_id') or (user_companies[0].id if user_companies else None)
    selected_company = Company.query.get(selected_company_id) if selected_company_id else None

    # Recent transactions for the selected company
    transactions = Transaction.query.filter_by(company_id=selected_company_id).order_by(Transaction.date.desc()).limit(5).all() if selected_company else []

    # Example stats for cards
    total_transactions = Transaction.query.filter_by(company_id=selected_company_id).count() if selected_company else 0
    last_report_date = datetime.utcnow().strftime("%Y-%m-%d") if selected_company else "N/A"

    return render_template(
        "dashboard.html",   # renamed template
        user=user,
        companies=user_companies,
        selected_company=selected_company,
        transactions=transactions,
        total_transactions=total_transactions,
        last_report_date=last_report_date
    )
# Add Company
@app.route('/add_company', methods=['POST'])
def add_company():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    company_name = request.form['company_name']
    industry = request.form.get('industry', '')

    # Create new company
    new_company = Company(name=company_name, industry=industry)
    db.session.add(new_company)
    db.session.commit()

    # Assign company to logged-in user
    user_company = UserCompany(user_id=session['user_id'], company_id=new_company.id)
    db.session.add(user_company)
    db.session.commit()

    flash(f"Company '{company_name}' added successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/ledger/<int:company_id>', methods=['GET', 'POST'])
def ledger(company_id):
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    company = Company.query.get_or_404(company_id)

    # Add transaction
    if request.method == 'POST':
        description = request.form['description']
        type_ = request.form['type']
        amount = float(request.form['amount'])

        new_transaction = Transaction(
            company_id=company.id,
            description=description,
            type=type_,
            amount=amount
        )
        db.session.add(new_transaction)
        db.session.commit()
        flash("Transaction added successfully!", "success")
        return redirect(url_for('ledger', company_id=company.id))

    # Get all transactions
    transactions = Transaction.query.filter_by(company_id=company.id).order_by(Transaction.date).all()

    # Running balance calculation (Debit/Asset increases, Credit decreases)
    balance = 0
    ledger_entries = []
    for t in transactions:
        if t.type == 'Debit':
            balance += t.amount
        else:  # Credit
            balance -= t.amount
        ledger_entries.append({
            'date': t.date,
            'description': t.description,
            'type': t.type,
            'amount': t.amount,
            'balance': balance
        })

    return render_template('ledger.html', company=company, user=user,
                           ledger_entries=ledger_entries, balance=balance)

@app.route('/analytics/<int:company_id>')
def analytics(company_id):
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])  # <-- get logged-in user
    company = Company.query.get_or_404(company_id)

    # Aggregate monthly debit, credit, and balance data
    from sqlalchemy import extract, func
    months = []
    debit_data = []
    credit_data = []
    balance_data = []

    for m in range(1, 13):
        month_name = datetime(2025, m, 1).strftime('%b')  # Example year, can make dynamic
        months.append(month_name)

        month_transactions = Transaction.query.filter_by(company_id=company.id).filter(extract('month', Transaction.date) == m).all()
        month_debit = sum(t.amount for t in month_transactions if t.type == 'Debit')
        month_credit = sum(t.amount for t in month_transactions if t.type == 'Credit')
        month_balance = month_credit - month_debit

        debit_data.append(month_debit)
        credit_data.append(month_credit)
        balance_data.append(month_balance)

    return render_template(
        'analytics.html',
        user=user,  # <-- pass user here
        company=company,
        months=months,
        debit_data=debit_data,
        credit_data=credit_data,
        balance_data=balance_data
    )
# Example in app.py

@app.route('/generate_report/<int:company_id>')
def generate_report(company_id):
    if 'user_id' not in session:
        flash("Please log in", "warning")
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    company = Company.query.get_or_404(company_id)
    transactions = Transaction.query.filter_by(company_id=company.id).all()

    total_debit = sum(t.amount for t in transactions if t.type=="Debit")
    total_credit = sum(t.amount for t in transactions if t.type=="Credit")
    balance = total_credit - total_debit

    # Prepare monthly data
    monthly = defaultdict(lambda: {'Debit':0, 'Credit':0})
    for t in transactions:
        month = t.date.strftime("%B")
        monthly[month][t.type] += t.amount

    months = list(monthly.keys())
    debit_data = [monthly[m]['Debit'] for m in months]
    credit_data = [monthly[m]['Credit'] for m in months]
    balance_data = [credit_data[i]-debit_data[i] for i in range(len(months))]

    return render_template(
        'report.html',
        user=user,
        company=company,
        transactions=transactions,
        total_debit=total_debit,
        total_credit=total_credit,
        balance=balance,
        months=months,
        debit_data=debit_data,
        credit_data=credit_data,
        balance_data=balance_data
    )
@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')



# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

