from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine
import os

# Import your existing functions from your python file
# Assuming your script is named 'logic.py'
from backend import get_store_rankings 

app = Flask(__name__, template_folder=".", static_folder="assets")

# Connect to your existing DB
db_path = "price_comparison.db"
engine = create_engine(f"sqlite:///{db_path}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search():
    data = request.json
    user_items = data.get('items', [])
    # Default user position (Varna Center) if browser GPS fails
    user_pos = data.get('coords', "43.2047, 27.9100")
    
    # Run your ranking logic
    results = get_store_rankings(engine, user_items, user_pos)
    
    # Return results as JSON
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)