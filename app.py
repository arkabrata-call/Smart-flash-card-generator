from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from werkzeug.utils import secure_filename
import PyPDF2
import random
import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this in a production environment

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Mock database (in a real application, you'd use a proper database)
users = {
    'admin': {'password': 'admin123', 'name': 'Admin User', 'email': 'admin@example.com'},
    'user': {'password': 'password', 'name': 'Test User', 'email': 'user@example.com'}
}

# Store generated content
flashcards_data = {}
quiz_data = {}
study_plan_data = {}

# Helper Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in first')
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
    return text

def generate_flashcards(text):
    # In a real application, you might use NLP or AI to generate better flashcards
    # This is a simple demonstration
    sentences = text.split('.')
    flashcards = []
    
    for sentence in sentences:
        if len(sentence.strip()) > 30:  # Only consider longer sentences
            flashcards.append(sentence.strip())
        if len(flashcards) >= 10:  # Limit to 10 flashcards
            break
    
    return flashcards

def generate_quiz(flashcards):
    questions = []
    
    for i, flashcard in enumerate(flashcards):
        if i >= 5:  # Limit to 5 questions
            break
            
        words = flashcard.split()
        if len(words) < 5:
            continue
            
        # Create a simple fill-in-the-blank question
        blank_index = random.randint(2, min(10, len(words) - 1))
        blank_word = words[blank_index]
        words[blank_index] = "_____"
        
        question = {
            "question": " ".join(words),
            "options": [
                blank_word,
                blank_word[::-1],  # Reverse the word as a wrong option
                blank_word[0] + "".join(random.sample(blank_word[1:-1], len(blank_word[1:-1]))) + blank_word[-1] if len(blank_word) > 2 else blank_word,
                "None of the above"
            ],
            "answer": blank_word
        }
        
        # Shuffle options
        random.shuffle(question["options"])
        questions.append(question)
    
    return questions

def generate_study_plan(flashcards):
    study_plan = []
    today = datetime.datetime.now()
    
    for i, flashcard in enumerate(flashcards[:5]):  # Use first 5 flashcards
        # Create a study item for each flashcard
        topic = flashcard[:50] + "..." if len(flashcard) > 50 else flashcard
        
        # Assign date (one day per flashcard)
        date = (today + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        
        # Assign priority based on position
        priority = "High" if i < 2 else "Medium" if i < 4 else "Low"
        
        study_plan.append({
            "topic": topic,
            "date": date,
            "priority": priority
        })
    
    return study_plan

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login-page')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if username in users and users[username]['password'] == password:
        session['username'] = username
        return redirect(url_for('profile'))
    else:
        flash('Invalid username or password')
        return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/profile')
@login_required
def profile():
    username = session.get('username')
    user = users.get(username, {})
    return render_template('profile.html', user=user)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdfFile' not in request.files:
        flash('No file part')
        return redirect(url_for('home'))
    
    file = request.files['pdfFile']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('home'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Process the PDF
        text = extract_text_from_pdf(file_path)
        
        # Generate flashcards
        flashcards = generate_flashcards(text)
        user_id = session.get('username', 'anonymous')
        flashcards_data[user_id] = flashcards
        
        # Generate quiz
        questions = generate_quiz(flashcards)
        quiz_data[user_id] = questions
        
        # Generate study plan
        study_plan = generate_study_plan(flashcards)
        study_plan_data[user_id] = study_plan
        
        return render_template('flashcards.html', flashcards=flashcards, questions=questions)
    
    return redirect(url_for('home'))

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    user_id = session.get('username', 'anonymous')
    
    if request.method == 'POST':
        # Process quiz submission
        score = 0
        total = len(quiz_data.get(user_id, []))
        result_details = []
        
        for i, question in enumerate(quiz_data.get(user_id, [])):
            user_answer = request.form.get(f'question_{i}')
            correct = user_answer == question['answer']
            if correct:
                score += 1
                
            result_details.append({
                'question': question['question'],
                'your_answer': user_answer,
                'correct_answer': question['answer'],
                'correct': correct
            })
        
        return render_template('quiz_result.html', score=score, total=total, result_details=result_details)
    
    # Display quiz
    questions = quiz_data.get(user_id, [])
    if not questions:
        flash('No quiz available. Upload a PDF first.')
        return redirect(url_for('home'))
        
    return render_template('quiz.html', questions=questions)

@app.route('/study-plan')
def study_plan():
    user_id = session.get('username', 'anonymous')
    study_plan = study_plan_data.get(user_id, [])
    
    if not study_plan:
        flash('No study plan available. Upload a PDF first.')
        return redirect(url_for('home'))
        
    return render_template('study_plan.html', study_plan=study_plan)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        # In a real application, you'd store this message or send an email
        flash(f'Thank you {name}! Your message has been sent.')
        return redirect(url_for('home'))
    
    return render_template('contact.html')

@app.route('/results')
def results():
    user_id = session.get('username', 'anonymous')
    flashcards = flashcards_data.get(user_id, [])
    
    if not flashcards:
        flash('No results available. Upload a PDF first.')
        return redirect(url_for('home'))
        
    return render_template('result.html', flashcards=flashcards)

if __name__ == '__main__':
    app.run(debug=True)