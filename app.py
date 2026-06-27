from flask import Flask, render_template, request, jsonify
import requests
import time
import threading
import sqlite3
from datetime import datetime

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('monitor.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS apis
                 (id INTEGER PRIMARY KEY, name TEXT, url TEXT, interval_sec INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs
                 (id INTEGER PRIMARY KEY, api_id INTEGER, timestamp TEXT,
                  status_code INTEGER, response_time REAL, status TEXT)''')
    conn.commit()
    conn.close()

def check_api(api_id, name, url, interval_sec):
    while True:
        try:
            start = time.time()
            r = requests.get(url, timeout=10)
            end = time.time()
            response_time = round((end - start) * 1000, 2)
            status = "UP" if r.status_code == 200 else "DOWN"
            status_code = r.status_code
        except Exception as e:
            response_time = 0
            status = "DOWN"
            status_code = 0

        conn = sqlite3.connect('monitor.db')
        c = conn.cursor()
        c.execute("INSERT INTO logs (api_id, timestamp, status_code, response_time, status) VALUES (?,?,?,?,?)",
                  (api_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status_code, response_time, status))
        conn.commit()
        conn.close()
        time.sleep(interval_sec)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form["name"]
        url = request.form["url"]
        interval = int(request.form["interval"])

        conn = sqlite3.connect('monitor.db')
        c = conn.cursor()
        c.execute("INSERT INTO apis (name, url, interval_sec) VALUES (?,?,?)", (name, url, interval))
        api_id = c.lastrowid
        conn.commit()
        conn.close()

        thread = threading.Thread(target=check_api, args=(api_id, name, url, interval))
        thread.daemon = True
        thread.start()

    conn = sqlite3.connect('monitor.db')
    c = conn.cursor()
    c.execute("SELECT * FROM apis")
    apis = c.fetchall()
    conn.close()
    return render_template("index.html", apis=apis)

@app.route("/data/<int:api_id>")
def get_data(api_id):
    conn = sqlite3.connect('monitor.db')
    c = conn.cursor()
    c.execute("SELECT timestamp, response_time, status FROM logs WHERE api_id=? ORDER BY id DESC LIMIT 20", (api_id,))
    data = c.fetchall()

    c.execute("SELECT AVG(response_time), SUM(CASE WHEN status='UP' THEN 1 ELSE 0 END)*100.0/COUNT(*) FROM logs WHERE api_id=?", (api_id,))
    avg_time, uptime = c.fetchone()
    conn.close()

    return jsonify({
        "labels": [d[0][11:] for d in reversed(data)],
        "times": [d[1] for d in reversed(data)],
        "avg_time": round(avg_time or 0, 2),
        "uptime": round(uptime or 0, 1),
        "current_status": data[0][2] if data else "N/A"
    })

if __name__ == "__main__":
    init_db()
    app.run(debug=True)