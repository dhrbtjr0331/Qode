import os

import sqlite3
from flask import Flask, flash, redirect, render_template, request, session, g 
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from groq import Groq, Client
from helpers import login_required


# Configure application
app = Flask(__name__)

#Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

#Configure SQLite database path
app.config['DATABASE'] = 'qode.db'

global_topics = [
    "Array",
    "Hash Table",
    "Two Pointers",
    "Sliding Window",
    "Stack",
    "Binary Search",
    "Linked List",
    "Trees",
    "Heap",
    "Priority Queue",
    "Backtracking",
    "Tries",
    "Graphs",
    "Advanced Graphs",
    "Dynamic Programming",
    "Greedy",
    "Intervals",
    "Math",
    "Geometry",
    "Bit Manipulation"
    ]

#Ensure responses are not cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

#Function to connect to the database and return in dictionary form
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    db_connect = sqlite3.connect('qode.db')
    db = db_connect.cursor()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            error_message = "Must Provide Username"
            return render_template("login.html", error=error_message)

        # Ensure password was submitted
        elif not request.form.get("password"):
            error_message = "Must Provide Password"
            return render_template("login.html", error=error_message)

        # Query database for username
        db.execute(
            "SELECT * FROM users WHERE username = ?", (request.form.get("username"),)
        )
        rows = db.fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0][2], request.form.get("password")  # Assuming 'hash' is the third column
        ):
            error_message = "Invalid username and/or password"
            return render_template("login.html", error=error_message)

        # Remember which user has logged in
        session["user_id"] = rows[0][0]  # Assuming 'id' is the first column

        db.close()
        db_connect.close()

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        db.close()
        db_connect.close()
        return render_template("login.html")


# Logout
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

# Register username/password
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    db_connect = sqlite3.connect('qode.db')
    db = db_connect.cursor()

    if request.method == "POST":
        username = request.form.get("username")
        # Execute the query with the username passed as a tuple
        db.execute("SELECT * FROM users WHERE username = ?", (username,))
        rows_username = db.fetchall()

        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        hashed_password = generate_password_hash(password)

        # All error cases
        if len(rows_username) > 0:
            error_message = "Username already exists"
            return render_template("register.html", error=error_message)
        elif not username:
            error_message = "Username is empty"
            return render_template("register.html", error=error_message)
        elif not password:
            error_message = "Password is empty"
            return render_template("register.html", error=error_message)
        elif password != confirmation:
            error_message = "Confirmation does not match password"
            return render_template("register.html", error=error_message)

        # Insert username/password info into the database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", (username, hashed_password))
        db_connect.commit()  # Commit the transaction to save changes
        db.close()
        db_connect.close()

        return redirect("/login")
    
    else:
        db.close()
        db_connect.close()

        return render_template("register.html")

    
#Homepage
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    topics = global_topics
    
    # access homepage 
    if request.method == "GET":
        return render_template("index.html", topics=topics)
    
    # Connect Database
    db_connect = sqlite3.connect('qode.db')
    db = db_connect.cursor()

    # User Input for difficulty & topic
    difficulty = request.form.get("difficulty")
    topic = request.form.get("topic")

    # Generate a random question from the leetcode problems database based on the user inputs for difficulty & topic
    db.execute("SELECT description, title FROM leetcode_problems WHERE difficulty = ? AND related_topics LIKE ? ORDER BY RANDOM() LIMIT 1", (difficulty, f'%{topic}%'))
    result = db.fetchone()
    description = result[0].strip() if result else "No quesiton found."
    title = result[1].strip() if result else "No question found"

    # Store the question info into session
    session["title"] = title
    session["description"] = description
    
    db.close()
    db_connect.close()

    return render_template("question.html", difficulty=difficulty, topic=topic, description=description, title=title)
    
@app.route("/ask-llama", methods=["GET", "POST"])
@login_required
def askLLM():
    if request.method == "POST":
        code = request.form.get("code")
        title = session["title"]
        description = session["description"]
        output = None
        feedback = None
        try:
            # Create a local context for the exec function
            local_context = {}
            
            # Execute the code
            exec(code, {}, local_context)
            
            # Attempt to call the first function defined in the code, if any
            func_name = None
            for key in local_context:
                if callable(local_context[key]):
                    func_name = key
                    break
            
            if func_name:
                # Call the function and get its return value
                result = local_context[func_name]()
                output = f"Function '{func_name}' returned: {result}"
            else:
                output = "No function found to call."

        except Exception as e:
            output = f"Error executing code: {str(e)}"

        question_to_llm = f"You are an coding assistant. The question that the user has to answer is: \n{description}. \n The user has submitted the following as the answer: \n {code} \n. Please give some hints or advice on optimization without giving away the answer. Also, let the user know if he/she got it correct with the most optimized way."
        client = Groq(api_key=os.environ.get("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"),)

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": question_to_llm,
                }
            ],
            model="llama3-8b-8192",
        )
        feedback = chat_completion.choices[0].message.content
    
    # Re-render the same page with the code, output, and feedback
    return render_template("question.html", description=description, code=code, output=output, feedback=feedback, title=title)

@app.route("/submit_code", methods=["POST"])
@login_required
def submit_code():

    db_connect = sqlite3.connect('qode.db')
    db = db_connect.cursor()

    if request.method == "POST":
        code = request.form.get("code")
        title = session["title"]
        description = session["description"]
        user_id = session["user_id"]

        db.execute("INSERT INTO history (user_id, title, description, code, datetime) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)", (user_id, title, description, code))
        db_connect.commit()

    # Re-render the same page with the code, output, and feedback
    return redirect("/history")

@app.route("/history", methods=["GET"])
@login_required
def history():

    db_connect = sqlite3.connect('qode.db')
    db = db_connect.cursor()
    user_id = session["user_id"]

    if request.method == "GET":

        db.execute("SELECT title, description, code, datetime FROM history WHERE user_id = ?", (user_id,))
        rows = db.fetchall()

        return render_template("history.html", rows=rows, user_id = user_id)