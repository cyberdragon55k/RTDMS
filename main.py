from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_cors import CORS
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import mysql.connector
import hashlib

app = Flask(__name__, template_folder='.', static_folder='.')
app.secret_key = 'your-secret-key-here'  
CORS(app)

class DisasterDashboard:
    def __init__(self):
        self.setup_logging()
        self.setup_database()
    
    def setup_database(self):
        try:
            self.db = mysql.connector.connect(
                host="localhost",
                user="root",
                password="root",
                database="disaster"
            )
            self.logger.info('Database connected successfully')
        except mysql.connector.Error as err:
            self.logger.error(f'Error connecting to database: {err}')
            raise
    
    def get_connection(self):
        if not self.db.is_connected():
            self.db.reconnect()
        return self.db
    
    def get_all_disasters(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, type, location, severity, 
                       DATE_FORMAT(date, '%Y-%m-%d') as date, 
                       description, source 
                FROM disasters 
                ORDER BY date DESC
            """)
            disasters = cursor.fetchall()
            return disasters
        finally:
            cursor.close()
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_dashboard_data(self):
        disasters = self.get_all_disasters()
        now = datetime.now()
        last_24h = now - timedelta(days=1)
        
        formatted_disasters = []
        severity_counts = defaultdict(int)
        type_counts = defaultdict(int)
        location_counts = defaultdict(int) 
        
        for disaster in disasters:
            try:
                formatted_disaster = {
                    'id': disaster[0],
                    'type': disaster[1],
                    'location': disaster[2],
                    'severity': disaster[3],
                    'date': disaster[4],
                    'description': disaster[5],
                    'source': disaster[6]
                }
                
                formatted_disasters.append(formatted_disaster)
                severity_counts[disaster[3].lower() if disaster[3] else 'unknown'] += 1
                type_counts[disaster[1]] += 1
                location_counts[disaster[2]] += 1
            except (ValueError, IndexError) as e:
                self.logger.error(f'Error processing disaster data: {e}')
                continue
        
        top_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_disasters': len(formatted_disasters),
            'last_24h_disasters': sum(1 for d in formatted_disasters 
                                    if d['date'] and datetime.strptime(d['date'], '%Y-%m-%d') > last_24h),
            'severity_breakdown': dict(severity_counts),
            'disaster_types': dict(type_counts),
            'top_locations': dict(top_locations),
            'disasters': formatted_disasters
        }

    def create_user(self, username, email, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:

            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            cursor.execute("""
                INSERT INTO users (username, email, password)
                VALUES (%s, %s, %s)
            """, (username, email, hashed_password))
            conn.commit()
            return True
        except mysql.connector.Error as err:
            self.logger.error(f'Error creating user: {err}')
            return False
        finally:
            cursor.close()

    def verify_user(self, username, password):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            cursor.execute("""
                SELECT id FROM users
                WHERE username = %s AND password = %s
            """, (username, hashed_password))
            user = cursor.fetchone()
            return user is not None
        finally:
            cursor.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if dashboard.verify_user(username, password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if dashboard.create_user(username, email, password):
            return redirect(url_for('login'))
        return render_template('signup.html', error='Username already exists')
    return render_template('signup.html')

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    dashboard_data = dashboard.get_dashboard_data()
    return render_template('index.html', 
                         disasters=dashboard_data['disasters'],
                         total_disasters=dashboard_data['total_disasters'],
                         last_24h_disasters=dashboard_data['last_24h_disasters'],
                         severity_breakdown=dashboard_data['severity_breakdown'],
                         disaster_types=dashboard_data['disaster_types'],
                         top_locations=dashboard_data['top_locations'],
                         now=datetime.now(),
                         timedelta=timedelta)

@app.route('/api/dashboard-data')
def get_dashboard_api():
    dashboard_data = dashboard.get_dashboard_data()
    return jsonify(dashboard_data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

dashboard = DisasterDashboard()

if __name__ == '__main__':
    app.run(debug=True, port=5000)