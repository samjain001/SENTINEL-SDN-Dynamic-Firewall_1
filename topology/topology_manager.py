import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import OVSKernelSwitch, RemoteController


# ==========================================
# SENTINEL CONFIGURATION
# ==========================================

CONTROLLER_IP = "127.0.0.1"
CONTROLLER_PORT = 6653

API_HOST = "127.0.0.1"
API_PORT = 5050

IP_PREFIX = "10.0.0."
MAX_DEVICES = 254


# ==========================================
# INITIAL MININET TOPOLOGY
# ==========================================

class SentinelTopo(Topo):

    def build(self):

        h1 = self.addHost(
            "h1",
            ip="10.0.0.1/24"
        )

        h2 = self.addHost(
            "h2",
            ip="10.0.0.2/24"
        )

        h3 = self.addHost(
            "h3",
            ip="10.0.0.3/24"
        )

        s1 = self.addSwitch(
            "s1",
            protocols="OpenFlow13"
        )

        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)


# ==========================================
# SENTINEL NETWORK MANAGER
# ==========================================

class SentinelNetwork:

    def __init__(self):

        self.lock = threading.RLock()

        self.topo = SentinelTopo()

        self.net = Mininet(
            topo=self.topo,
            controller=None,
            switch=OVSKernelSwitch,
            autoSetMacs=True
        )

        self.net.addController(
            "c0",
            controller=RemoteController,
            ip=CONTROLLER_IP,
            port=CONTROLLER_PORT
        )

        self.devices = {
            "h1": {
                "name": "h1",
                "ip": "10.0.0.1",
                "role": "server"
            },
            "h2": {
                "name": "h2",
                "ip": "10.0.0.2",
                "role": "client"
            },
            "h3": {
                "name": "h3",
                "ip": "10.0.0.3",
                "role": "client"
            }
        }

        self.dynamic_links = {}

    # ======================================
    # START NETWORK
    # ======================================

    def start(self):

        print("Starting Sentinel Mininet network...")

        self.net.start()

        print("Sentinel network started successfully.")

        print(
            "Connected to controller:",
            CONTROLLER_IP
        )

        print(
            "OpenFlow port:",
            CONTROLLER_PORT
        )

    # ======================================
    # GENERATE UNIQUE IP
    # ======================================

    def get_next_ip(self):

        used_ips = {
            int(device["ip"].split(".")[-1])
            for device in self.devices.values()
        }

        for last_octet in range(
            4,
            MAX_DEVICES + 1
        ):

            if last_octet not in used_ips:

                return IP_PREFIX + str(last_octet)

        raise ValueError(
            "No available IP addresses."
        )

    # ======================================
    # ADD SERVER OR CLIENT
    # ======================================

    def add_device(self, role):

        role = str(role).lower().strip()

        if role not in ("server", "client"):

            raise ValueError(
                "Role must be server or client."
            )

        with self.lock:

            if len(self.devices) >= MAX_DEVICES:

                raise ValueError(
                    "Device limit reached."
                )

            number = 1

            while "h" + str(number) in self.devices:
                number += 1

            name = "h" + str(number)

            ip = self.get_next_ip()

            host = self.net.addHost(
                name,
                ip=ip + "/24"
            )

            switch = self.net.get("s1")

            link = self.net.addLink(
                host,
                switch
            )

            try:

                # Configure the host interface.
                host.configDefault()

                # Explicitly attach the switch-side interface.
                switch.attach(link.intf2)

                # Ensure the host interface is enabled.
                link.intf1.ifconfig("up")

                self.devices[name] = {
                    "name": name,
                    "ip": ip,
                    "role": role
                }

                self.dynamic_links[name] = link

                print(
                    "Device added:",
                    name,
                    ip,
                    role
                )

                print(
                    "Switch interface attached:",
                    link.intf2
                )

                return self.devices[name]

            except Exception:

                try:
                    switch.detach(link.intf2)
                except Exception:
                    pass

                try:
                    self.net.delLink(link)
                except Exception:
                    pass

                try:
                    self.net.delHost(host)
                except Exception:
                    pass

                raise

    # ======================================
    # REMOVE DEVICE
    # ======================================

    def remove_device(self, name):

        with self.lock:

            if name not in self.devices:

                raise ValueError(
                    "Device not found."
                )

            if name in ("h1", "h2", "h3"):

                raise ValueError(
                    "Initial devices cannot be removed."
                )

            host = self.net.get(name)

            link = self.dynamic_links.get(name)

            if link is not None:

                switch = self.net.get("s1")

                switch.detach(link.intf2)

                self.net.delLink(link)

            self.net.delHost(host)

            self.dynamic_links.pop(name, None)

            del self.devices[name]

            print(
                "Device removed:",
                name
            )

            return {
                "message": name + " removed successfully."
            }

    # ======================================
    # LIST DEVICES
    # ======================================

    def list_devices(self):

        with self.lock:

            return list(
                self.devices.values()
            )

    # ======================================
    # STOP NETWORK
    # ======================================

    def stop(self):

        print("Stopping Sentinel network...")

        self.net.stop()

        print("Sentinel network stopped.")


# ==========================================
# DEVICE API
# ==========================================

network = None


class DeviceAPI(BaseHTTPRequestHandler):

    def send_json(self, status, data):

        response = json.dumps(data).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Content-Length",
            str(len(response))
        )

        self.end_headers()

        self.wfile.write(response)

    # --------------------------------------
    # GET: LIST DEVICES
    # --------------------------------------

    def do_GET(self):

        if self.path == "/devices":

            self.send_json(
                200,
                {
                    "devices": network.list_devices()
                }
            )

        else:

            self.send_json(
                404,
                {
                    "error": "Endpoint not found."
                }
            )

    # --------------------------------------
    # POST: ADD DEVICE
    # --------------------------------------

    def do_POST(self):

        if self.path != "/devices":

            self.send_json(
                404,
                {
                    "error": "Endpoint not found."
                }
            )

            return

        try:

            length = int(
                self.headers.get(
                    "Content-Length",
                    0
                )
            )

            if length <= 0 or length > 1024:

                raise ValueError(
                    "Invalid request size."
                )

            data = json.loads(
                self.rfile.read(length).decode("utf-8")
            )

            device = network.add_device(
                data.get("role", "")
            )

            self.send_json(
                201,
                {
                    "message": "Device added successfully.",
                    "device": device
                }
            )

        except (
            ValueError,
            json.JSONDecodeError
        ) as error:

            self.send_json(
                400,
                {
                    "error": str(error)
                }
            )

        except Exception:

            self.send_json(
                500,
                {
                    "error": "Device creation failed."
                }
            )

            print(
                "Unexpected error while adding device:"
            )

            import traceback
            traceback.print_exc()

    # --------------------------------------
    # DELETE: REMOVE DEVICE
    # --------------------------------------

    def do_DELETE(self):

        name = self.path.removeprefix(
            "/devices/"
        )

        if (
            not name.startswith("h")
            or not name[1:].isdigit()
        ):

            self.send_json(
                400,
                {
                    "error": "Invalid device name."
                }
            )

            return

        try:

            result = network.remove_device(name)

            self.send_json(
                200,
                result
            )

        except ValueError as error:

            self.send_json(
                400,
                {
                    "error": str(error)
                }
            )

        except Exception:

            self.send_json(
                500,
                {
                    "error": "Device removal failed."
                }
            )

            import traceback
            traceback.print_exc()

    def log_message(self, format, *args):

        print(
            "Device API:",
            format % args
        )


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    global network

    network = SentinelNetwork()

    server = None

    try:

        network.start()

        server = ThreadingHTTPServer(
            (API_HOST, API_PORT),
            DeviceAPI
        )

        print()
        print(
            "Sentinel Device API running at "
            "http://127.0.0.1:5050"
        )

        print(
            "Press Ctrl+C to stop the network."
        )

        server.serve_forever()

    except KeyboardInterrupt:

        print("\nShutdown requested.")

    finally:

        if server is not None:

            server.server_close()

        network.stop()


if __name__ == "__main__":

    main()


