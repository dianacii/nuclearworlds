from flask import Flask, render_template, request, redirect, url_for, session
import os, json, uuid, sqlite3
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

if not os.getenv("SESSION_KEY") or not os.getenv("GEMINI_API_KEY"):
    print("Warning: SESSION_KEY or GEMINI_API_KEY not set in .env file.")
    exit(1)

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_KEY")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
model = "gemini-2.0-flash"

user_chat_contents = {}

# SQLite database connection
def get_db_connection():
    conn = sqlite3.connect("scores.db")
    conn.row_factory = sqlite3.Row
    return conn

def get_user_id():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

def get_or_create_contents():
    user_id = get_user_id()
    if user_id not in user_chat_contents:
        user_chat_contents[user_id] = []
    return user_chat_contents[user_id]

# Generate AI scenario
def generate(user_input):
    contents = get_or_create_contents()
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))
    print("length of contents:", len(contents))

    generate_content_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=[types.Part.from_text(text=open("system_prompt.txt", "r").read())],
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )

    try:
        response_json = json.loads(response.text)
        with open("response.json", "w") as f:
            json.dump(response_json, f, indent=4)

        contents.append(types.Content(role="model", parts=[types.Part.from_text(text=json.dumps(response_json))]))
        user_chat_contents[get_user_id()] = contents
        return response_json
    except json.JSONDecodeError:
        print(f"Error decoding JSON: {response.text}")
        return {"text": "An error occurred. Please try again.", "choices": {}}

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start():
    session['role'] = request.form['role']
    length = 'short game, no more than 10 mins'
    #length = 'DEBUGGING MODE. very short length. this is a test. only 1 scenario and then go to end!!!'
    initial_prompt = f"Game starts. User picked {session['role']} and {length}."
    generate(initial_prompt)
    return redirect(url_for('game'))

@app.route('/game')
def game():
    contents = get_or_create_contents()
    if contents and contents[-1].role == "model":
        last_bot_response = json.loads(contents[-1].parts[0].text)
    else:
        last_bot_response = {}
    return render_template('game.html', scenario=last_bot_response)

@app.route('/choose', methods=['POST'])
def choose():
    choice = request.form['choice']
    generate(choice)
    return redirect(url_for('game'))

@app.route('/end')
def end():
    user_chat_contents.pop(get_user_id(), None)
    session.pop('user_id', None)
    session.pop('role', None)
    return redirect(url_for('scoreboard'))

@app.route('/save-scores', methods=['POST'])
def save_scores():
    user_id = session.pop('user_id', None)
    contents = user_chat_contents.pop(user_id, [])
    role = session.pop('role', 'Unknown')
    username = request.form.get('saveName', 'anonymous')
    session['last_saved_user'] = username  # for scoreboard highlight

    try:
        last_response = contents[-1].parts[0].text
        data = json.loads(last_response)
        scores = data.get("scores", {})

        public_acceptance = int(scores.get("Public Acceptance of Nuclear", 0))
        tech_advancement = int(scores.get("Technological Advancement", 0))
        risk_of_nuclear_disaster = int(scores.get("Nuclear Disaster Risk", 0))

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS game_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                public_acceptance INTEGER,
                tech_advancement INTEGER,
                risk_of_nuclear_disaster INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO game_scores 
            (username, role, public_acceptance, tech_advancement, risk_of_nuclear_disaster)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, role, public_acceptance, tech_advancement, risk_of_nuclear_disaster)
        )
        db.commit()
        cursor.close()
        db.close()

        print(f"Saved scores for {username} to SQLite")
    except Exception as e:
        print("Error saving scores:", e)

    return redirect(url_for('end'))

@app.route('/scoreboard')
def scoreboard():
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, username, role, public_acceptance, tech_advancement, risk_of_nuclear_disaster, created_at
        FROM game_scores
        ORDER BY public_acceptance DESC
        LIMIT 10
    """)
    top_scores = cursor.fetchall()

    last_user = session.get('last_saved_user')
    last_score = None
    if last_user:
        cursor.execute("""
            SELECT id, username, role, public_acceptance, tech_advancement, risk_of_nuclear_disaster, created_at
            FROM game_scores
            WHERE username = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (last_user,))
        last_score = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template("scoreboard.html", top_scores=top_scores, last_score=last_score)

if __name__ == '__main__':
    app.run(debug=True, port=5003)
 