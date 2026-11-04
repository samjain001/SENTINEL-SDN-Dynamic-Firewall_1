
import socket
import threading
import csv
import os
from datetime import datetime

# ==========================================
# SENTINEL TCP SECURITY SERVER
# ==========================================

HOST = "0.0.0.0"
PORT = 5000

LOG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "traffic_log.csv"
)

MAX_MESSAGE_SIZE = 1024

# Configure IP addresses that must be denied.
BLOCKED_IPS = set()

# Demonstration rule:
# Messages beginning with BLOCK: are rejected.
# This is a test rule, not a general threat detector.

log_lock = threading.Lock()


# ==========================================
# 1. CREATE CSV LOG
# ==========================================

def setup_log():

    if not os.path.exists(LOG_FILE):

        with open(LOG_FILE, "w", newline="", encoding="utf-8") as file:

            writer = csv.writer(file)

            writer.writerow([
                "Timestamp",
                "Source IP",
                "Source Port",
                "Destination IP",
                "Destination Port",
                "Protocol",
                "Message",
                "Decision"
            ])


# ==========================================
# 2. SECURITY POLICY
# ==========================================

def check_traffic(source_ip, message):

    # Rule 1: Block configured source IPs.
    if source_ip in BLOCKED_IPS:
        return "BLOCKED", "Source IP is denied"

    # Rule 2: Reject empty messages.
    if not message.strip():
        return "BLOCKED", "Empty message"

    # Rule 3: Reject oversized messages.
    if len(message.encode("utf-8")) > MAX_MESSAGE_SIZE:
        return "BLOCKED", "Message exceeds size limit"

    # Rule 4: Demonstration blocking rule.
    if message.strip().upper().startswith("BLOCK:"):
        return "BLOCKED", "Demonstration security rule matched"

    return "ALLOWED", "Traffic passed security checks"


# ==========================================
# 3. RECORD NETWORK EVENT
# ==========================================

def log_traffic(
    source_ip,
    source_port,
    destination_ip,
    destination_port,
    message,
    decision
):

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with log_lock:

        with open(
            LOG_FILE,
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                timestamp,
                source_ip,
                source_port,
                destination_ip,
                destination_port,
                "TCP",
                message,
                decision
            ])


# ==========================================
# 4. HANDLE CLIENT CONNECTION
# ==========================================

def handle_client(conn, address):

    source_ip, source_port = address

    destination_ip, destination_port = conn.getsockname()

    print(f"\nConnected: {source_ip}:{source_port}")

    try:

        while True:

            data = conn.recv(MAX_MESSAGE_SIZE + 1)

            if not data:
                break

            message = data.decode(
                "utf-8",
                errors="replace"
            )

            decision, reason = check_traffic(
                source_ip,
                message
            )

            # Record both allowed and blocked attempts.
            log_traffic(
                source_ip,
                source_port,
                destination_ip,
                destination_port,
                message,
                decision
            )

            print("\n------------------------------")
            print(f"Source IP : {source_ip}")
            print(f"Message   : {message}")
            print(f"Protocol  : TCP")
            print(f"Decision  : {decision}")
            print(f"Reason    : {reason}")
            print("------------------------------")

            if decision == "ALLOWED":

                conn.sendall(
                    b"ALLOWED: Message received by Sentinel server"
                )

            else:

                conn.sendall(
                    f"BLOCKED: {reason}".encode("utf-8")
                )

    except (ConnectionError, OSError) as error:

        print(f"Connection error: {error}")

    finally:

        conn.close()

        print(
            f"Disconnected: {source_ip}:{source_port}"
        )


# ==========================================
# 5. START TCP SERVER
# ==========================================

def main():

    setup_log()

    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    try:

        server.bind((HOST, PORT))

        server.listen()

        print("\n================================")
        print(" SENTINEL NETWORK SECURITY SERVER")
        print("================================")
        print(f"Listening on port: {PORT}")
        print(f"Traffic log: {LOG_FILE}")
        print("Security filtering: ENABLED")
        print("================================")
        print("Press Ctrl+C to stop.")

        while True:

            conn, address = server.accept()

            thread = threading.Thread(
                target=handle_client,
                args=(conn, address),
                daemon=True
            )

            thread.start()

    except KeyboardInterrupt:

        print("\nSentinel server stopped.")

    except OSError as error:

        print(f"Server error: {error}")

    finally:

        server.close()


if __name__ == "__main__":
    main()
