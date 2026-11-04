import socket

# ==========================================
# SENTINEL TCP CLIENT
# ==========================================

HOST = "10.0.0.1"
PORT = 5000


def main():

    try:

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        ) as client:

            client.connect((HOST, PORT))

            print("\n================================")
            print(" SENTINEL NETWORK CLIENT")
            print("================================")
            print("Connected to TCP server.")
            print("Enter 'exit' to disconnect.")
            print("================================")

            while True:

                message = input("\nEnter message: ")

                if message.lower() == "exit":
                    break

                if not message:
                    print("Please enter a message.")
                    continue

                client.sendall(message.encode("utf-8"))

                response = client.recv(2048)

                if not response:
                    print("Server disconnected.")
                    break

                response_text = response.decode(
                    "utf-8",
                    errors="replace"
                )

                print("\nServer response:")
                print(response_text)

                if response_text.startswith("ALLOWED:"):

                    print("[+] Traffic accepted")

                elif response_text.startswith("BLOCKED:"):

                    print("[-] Traffic rejected")

    except ConnectionRefusedError:

        print("Connection refused. Start server.py first.")

    except OSError as error:

        print(f"Network error: {error}")


if __name__ == "__main__":
    main()
