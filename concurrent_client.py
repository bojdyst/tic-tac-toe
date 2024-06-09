import socket
import ssl
import os

FORMAT = 'utf-8' # Format of message
DISCOVERY_PORT = 5051 # Discovery port that is searched for a listening server
MULTICAST_GROUP = '224.0.0.1' # Multicast group that is searched for a listening server
MAX_DISCOVERY_ATTEMPTS = 3  # Maximum number of discovery attempts

def discover_server():
    # Multicast UDP service discovery handler. Allows client to find a listening server
    discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    discovery_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    message = "DISCOVER_SERVER".encode(FORMAT)
    attempts = 0
    while attempts < MAX_DISCOVERY_ATTEMPTS:
        try:
            discovery_socket.sendto(message, (MULTICAST_GROUP, DISCOVERY_PORT))
            discovery_socket.settimeout(2)
            data, server_address = discovery_socket.recvfrom(1024)
            server_ip, server_port = data.decode(FORMAT).split(':')
            print(f"Discovered server {server_ip}:{int(server_port)}. Connecting to it.")
            return server_ip, int(server_port)
        except socket.timeout:
            attempts += 1
            print("Server discovery timed out. Retrying...")
    print(f"Server discovery failed after {MAX_DISCOVERY_ATTEMPTS} attempts.")
    return None, None

# Set found server info into variables
SERVER, PORT = discover_server()

def play():
    if SERVER == None and PORT == None:
        return
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    client = context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=SERVER)

    client.connect((SERVER, PORT))

    nickname = input("Enter your nickname: ")
    client.sendall(nickname.encode())

    while True:
        try:
            response = client.recv(4096).decode()
            if not response: break
            if "Your move" in response:
                print(response)
                move = input("Enter your move (0-8): ")
                client.send(move.encode())
            else:
                if "wins" not in response and "draw" not in response and "has left the game" not in response:
                    os.system('clear')
                    print(response)
                else:
                    print(response)
                    break
        except Exception as e:
            print("Error receiving message:", e)
            break

    client.close()

if __name__ == "__main__":
    play()