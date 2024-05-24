from flask import Flask, render_template
import socket
import threading
import logging
import atexit
import json

# set starting details to make connection and decode messages
HEADER = 64
PORT = 5050
SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "disconnected"
DISCOVERY_PORT = 5051
MULTICAST_GROUP = '224.0.0.1'

# start and bind server socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(ADDR)

def send_message(msg, clients, conn):
    # sends message to client that it did not receive the message from
    for client in clients:
        if client != conn:
            message = msg.encode(FORMAT)
            msg_length = len(message)
            send_length = str(msg_length).encode(FORMAT)
            send_length += b' ' * (HEADER - len(send_length))
            client.send(send_length)
            client.send(message)

def send_client_start(conn, item):
    # sends clients their starting information (X or O, who's turn is first)
    message = item.encode(FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b' ' * (HEADER - len(send_length))
    conn.send(send_length)
    conn.send(message)

def handle_client(conn, addr, clients, nicknames):
    # receives messages from clients and sends to opposite client
    logging.info(f"[NEW CONNECTION] {addr} connected")
    
    # Get the nickname from the client
    nickname_length = conn.recv(HEADER).decode(FORMAT)
    if nickname_length:
        nickname_length = int(nickname_length)
        nickname = conn.recv(nickname_length).decode(FORMAT)
        nicknames[conn] = nickname
        logging.info(f"[NEW NICKNAME] {nickname} connected")
    
    connected = True
    while connected:
        try:
            msg_length = conn.recv(HEADER).decode(FORMAT)
            if msg_length:
                msg_length = int(msg_length)
                msg = conn.recv(msg_length).decode(FORMAT)
                if msg == DISCONNECT_MESSAGE:
                    connected = False
                logging.info(f"[{addr}-{nickname}] {msg}")
                if connected:
                    send_message(msg, clients, conn)
        except:
            connected = False
    
    conn.close()
    clients.remove(conn)
    del nicknames[conn]

def handle_discovery():
    discovery_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    discovery_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    discovery_socket.bind(('', DISCOVERY_PORT))
    group = socket.inet_aton(MULTICAST_GROUP)
    mreq = group + socket.inet_aton('0.0.0.0')
    discovery_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    while True:
        data, addr = discovery_socket.recvfrom(1024)
        if data.decode(FORMAT) == "DISCOVER_SERVER":
            discovery_socket.sendto(f"{SERVER}:{PORT}".encode(FORMAT), addr)

def start():
    # beginning, waits for client connections and calls the function to send the clients their starting information
    clients = []
    nicknames = {}
    s.listen(2)
    logging.info(f'Server is listening on {SERVER}')
    
    discovery_thread = threading.Thread(target=handle_discovery, daemon=True)
    discovery_thread.start()
    
    while True:
        conn, addr = s.accept()
        clients.append(conn)
        
        t = threading.Thread(target=handle_client, args=(conn, addr, clients, nicknames))
        t.start()

        symbols = ['O', 'X']
        turns = ['0', '1']
        
        if len(clients) == 2:
            for client in clients:
                send_client_start(client, symbols.pop(0) + turns.pop(0))
        
        logging.info(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")



def add_points_for_winner(nickname, scoreboard):
    found = False
    for entry in scoreboard:
        if entry['nickname'] == nickname:
            logging.info(f"Adding 1 point for {nickname}.")
            entry['score'] += 1
            found = True
            break
    if not found:
        logging.info(f"Adding new player: {nickname}.")
        scoreboard.append({'nickname': nickname, 'score': 1})

# Ścieżka do pliku JSON
JSON_FILE_PATH = 'scoreboard.json'

def load_scoreboard():
    with open(JSON_FILE_PATH, 'r') as file:
        return json.load(file)

def save_scoreboard(scoreboard):
    with open(JSON_FILE_PATH, 'w') as file:
        json.dump(scoreboard, file, indent=4)


logging.basicConfig(level=logging.INFO)

scoreboard = load_scoreboard()

app = Flask(__name__)
        
@app.route('/')
def index():
    return render_template('scoreboard.html', scoreboard=scoreboard)

def run_flask():
    app.run(debug=True, host='0.0.0.0', use_reloader=False)

# Uruchomienie aplikacji Flask w osobnym wątku
flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

add_points_for_winner('Marcin', scoreboard)
# Funkcja do zapisywania scoreboard podczas wyłączania programu
def on_exit():
    global scoreboard
    save_scoreboard(scoreboard)

# Rejestracja funkcji on_exit, aby była wykonywana przy zamykaniu programu
atexit.register(on_exit)

logging.info("[STARTING] server is starting...")
# start and bind server socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(ADDR)
start()