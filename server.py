import socket
import threading
import logging
from flask import Flask, render_template

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
                logging.info(f"[{addr}] {msg}")
                if connected:
                    send_message(msg, clients, conn)
        except:
            connected = False
    
    conn.close()
    clients.remove(conn)
    del nicknames[conn]

def start():
    # beginning, waits for client connections and calls the function to send the clients their starting information
    clients = []
    nicknames = {}
    #symbols = ['O', 'X']
    #turns = ['0', '1']
    s.listen(2)
    logging.info(f'Server is listening on {SERVER}')
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

# set starting details to make connection and decode messages
HEADER = 64
PORT = 5050
SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "disconnected"

app = Flask(__name__)

# Przykładowe dane do tabeli
scoreboard = [
    {'nickname': 'Alice', 'score': 120},
    {'nickname': 'Bob', 'score': 95},
    {'nickname': 'Charlie', 'score': 110},
    {'nickname': 'Diana', 'score': 130}
]

@app.route('/')
def index():
    return render_template('scoreboard.html', scoreboard=scoreboard)

def run_flask():
    app.run(debug=True, host='0.0.0.0', use_reloader=False)

# Uruchomienie aplikacji Flask w osobnym wątku
flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# start and bind server socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(ADDR)
logging.basicConfig(level=logging.INFO)
logging.info("[STARTING] server is starting...")
start()
