# SENTINEL — SDN-Based Dynamic Firewall with Security Event Logger

SENTINEL is a Computer Networks mini-project that combines TCP socket communication, a Mininet-based software-defined network, an OS-Ken/OpenFlow 1.3 controller, a Flask dashboard, and CSV-based traffic logging.

## Project components

- `socket_app/` — TCP client and server programs.
- `controller/` — OS-Ken OpenFlow 1.3 learning-switch controller with security-event monitoring and OpenFlow drop statistics.
- `topology/` — Mininet topology and local device-management API.
- `backend/` — Flask API and dashboard server.
- `website/` — dashboard HTML, CSS, and JavaScript.
- `traffic_log.csv`, `openflow_drop_stats.json` — example/runtime data files.
- `screenshots/` — project screenshots supplied with the source archive.

## Requirements

This project is intended to run in an Ubuntu environment with Mininet, Open vSwitch, Python 3, and the OS-Ken controller installed. The dashboard backend uses Flask. The Mininet topology requires permission to create network namespaces and virtual switches.

Python dependencies are listed in `requirements.txt`. Mininet and Open vSwitch are system-level dependencies and are not installed by `pip`.

## Setup

From the repository root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If your system Python is externally managed, use the virtual environment as shown above. Install and verify Mininet and Open vSwitch using the instructions for your Ubuntu release.

## Run the project

Use separate Ubuntu terminals. Start each component from the repository root unless stated otherwise.

1. **Start the SDN controller** (activate the environment where OS-Ken is installed):

   ```bash
   source venv/bin/activate
   PYTHONPATH="$PWD" osken-manager --ofp-tcp-listen-port 6653 controller.simple_switch
   ```

2. **Start the Mininet topology and device API** in another terminal:

   ```bash
   sudo python3 topology/topology_manager.py
   ```

3. **Start the Flask backend/dashboard** in another terminal:

   ```bash
   source venv/bin/activate
   python backend/app.py
   ```

4. Open the dashboard in a browser at `http://127.0.0.1:8000/`.

5. Use the Mininet CLI to run the TCP server on `h1` and TCP client(s) on other hosts. The socket source files are in `socket_app/`. The exact command for launching them inside Mininet depends on the absolute repository path in the VM; for example, use the Mininet CLI's `h1`/`h2` host prefixes with the corresponding Python script path.

Stop the topology with Ctrl+C in the topology terminal, and stop the controller/backend in their respective terminals.

## Important configuration

- The default controller endpoint is `127.0.0.1:6653`.
- The topology device API listens on `127.0.0.1:5050`.
- The Flask dashboard listens on `0.0.0.0:8000`.
- The TCP server uses port `5000`.
- The backend and controller now resolve the CSV and OpenFlow statistics files relative to the repository root, rather than depending on one developer's home-directory path.

If you change ports or addresses, update the corresponding settings in `backend/app.py`, `topology/topology_manager.py`, `controller/simple_switch.py`, and the socket programs consistently.

## Testing and evidence

Use the supplied screenshots as visual evidence, and perform a fresh end-to-end run before reporting test results. Verify controller connectivity, host connectivity, TCP message exchange, dashboard updates, and traffic-log entries. Do not treat the sample CSV or screenshots alone as proof that a test passed in a new environment.

## Notes

- This is an academic prototype, not a replacement for a production firewall.
- Do not commit virtual environments, passwords, API keys, private keys, or personal data.
- Check the exact commands and dependency versions against the Ubuntu/Mininet environment used for the final demonstration.
