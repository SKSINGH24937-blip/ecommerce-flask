# test_app.py
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Hello — test app is running!"

if __name__ == '__main__':
    print("Starting test Flask app...")
    app.run(debug=True, port=5000)
