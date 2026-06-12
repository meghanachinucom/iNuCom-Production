import os
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Basic route
@app.route('/')
def index():
    return "iNuCom Production Tracker - Initial Setup"

if __name__ == '__main__':
    # Listen on all network interfaces for local LAN access
    app.run(host='0.0.0.0', port=5000, debug=True)
