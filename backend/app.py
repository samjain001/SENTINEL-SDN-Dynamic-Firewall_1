
import csv
import json
import socket

from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from flask import (
    Flask,
    jsonify,
    request,
    send_from_directory
)


# ==========================================
# SENTINEL CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

WEBSITE_DIR = BASE_DIR / "website"

LOG_FILE = BASE_DIR / "traffic_log.csv"

CONTROLLER_HOST = "127.0.0.1"
CONTROLLER_PORT = 6653

TOPOLOGY_API = "http://127.0.0.1:5050"

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 8000


# ==========================================
# FLASK APPLICATION
# ==========================================

app = Flask(__name__)


# ==========================================
# HELPER: READ TRAFFIC CSV
# ==========================================

def read_traffic():

    if not LOG_FILE.exists():
        return []

    try:

        with open(
            LOG_FILE,
            "r",
            newline="",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            return list(reader)

    except (OSError, csv.Error) as error:

        print("Traffic log error:", error)

        return []


# ==========================================
# HELPER: CHECK SDN CONTROLLER
# ==========================================

def check_controller():

    try:

        connection = socket.create_connection(
            (
                CONTROLLER_HOST,
                CONTROLLER_PORT
            ),
            timeout=2
        )

        connection.close()

        return True

    except OSError:

        return False


# ==========================================
# HELPER: CONNECT TO TOPOLOGY MANAGER
# ==========================================

def topology_request(
    path,
    method="GET",
    data=None
):

    url = TOPOLOGY_API + path

    body = None

    headers = {}

    if data is not None:

        body = json.dumps(data).encode("utf-8")

        headers["Content-Type"] = "application/json"

    req = Request(
        url,
        data=body,
        headers=headers,
        method=method
    )

    try:

        with urlopen(
            req,
            timeout=10
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

            return result, response.status

    except HTTPError as error:

        try:

            result = json.loads(
                error.read().decode("utf-8")
            )

        except Exception:

            result = {
                "error": "Topology manager returned an error."
            }

        return result, error.code

    except URLError:

        return {
            "error": "Cannot connect to Sentinel topology manager."
        }, 503

    except Exception as error:

        print("Topology API error:", error)

        return {
            "error": "Unexpected topology manager error."
        }, 500


# ==========================================
# WEBSITE HOME PAGE
# ==========================================

@app.route("/")
def home():

    return send_from_directory(
        WEBSITE_DIR,
        "index.html"
    )


# ==========================================
# WEBSITE STATIC FILES
# ==========================================

@app.route("/<path:filename>")
def website_files(filename):

    return send_from_directory(
        WEBSITE_DIR,
        filename
    )


# ==========================================
# BACKEND STATUS
# ==========================================

@app.route("/api/status")
def backend_status():

    return jsonify({
        "status": "ONLINE",
        "backend": "Sentinel Flask API"
    })


# ==========================================
# CONTROLLER STATUS
# ==========================================

@app.route("/api/controller")
def controller_status():

    online = check_controller()

    return jsonify({
        "online": online,
        "host": CONTROLLER_HOST,
        "port": CONTROLLER_PORT,
        "status": "ONLINE" if online else "OFFLINE"
    })


# ==========================================
# TRAFFIC HISTORY
# ==========================================

@app.route("/api/traffic")
def traffic():

    rows = read_traffic()

    return jsonify({
        "traffic": rows,
        "total": len(rows)
    })


# ==========================================
# TRAFFIC STATISTICS
# ==========================================

@app.route("/api/stats")
def statistics():

    rows = read_traffic()

    total = len(rows)

    allowed = 0
    blocked = 0
    tcp = 0

    for row in rows:

        decision = (
            row.get("Decision") or ""
        ).strip().upper()

        protocol = (
            row.get("Protocol") or ""
        ).strip().upper()

        if decision == "ALLOWED":
            allowed += 1

        elif decision == "BLOCKED":
            blocked += 1

        if protocol == "TCP":
            tcp += 1

    return jsonify({

        "total": total,
        "allowed": allowed,
        "blocked": blocked,
        "tcp": tcp,

        # Compatibility aliases for dashboard scripts.
        "total_messages": total,
        "allowed_messages": allowed,
        "blocked_messages": blocked,
        "tcp_messages": tcp

    })


# ==========================================
# DYNAMIC DEVICE MANAGEMENT
# ==========================================

@app.route("/api/devices", methods=["GET"])
def get_devices():

    result, status = topology_request(
        "/devices"
    )

    return jsonify(result), status


# ==========================================
# ADD SERVER OR CLIENT
# ==========================================

@app.route("/api/devices", methods=["POST"])
def add_device():

    data = request.get_json(silent=True) or {}

    role = str(
        data.get("role", "")
    ).strip().lower()

    if role not in ("server", "client"):

        return jsonify({
            "error": "Select either server or client."
        }), 400

    result, status = topology_request(
        "/devices",
        method="POST",
        data={
            "role": role
        }
    )

    return jsonify(result), status


# ==========================================
# REMOVE SERVER OR CLIENT
# ==========================================

@app.route(
    "/api/devices/<device_name>",
    methods=["DELETE"]
)
def remove_device(device_name):

    result, status = topology_request(
        "/devices/" + device_name,
        method="DELETE"
    )

    return jsonify(result), status


# ==========================================
# START FLASK SERVER
# ==========================================

if __name__ == "__main__":

    print("=" * 50)
    print("       SENTINEL NETWORK OPERATIONS CENTER")
    print("=" * 50)

    print("Website directory:", WEBSITE_DIR)
    print("Traffic log:", LOG_FILE)

    print("Controller:", CONTROLLER_HOST, CONTROLLER_PORT)
    print("Topology API:", TOPOLOGY_API)

    print("Starting Sentinel Flask backend...")

    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=False,
        threaded=True
    )
