import socket
import threading

# set starting details to make connection and decode messages
HEADER = 64
PORT = 5050
SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "disconnected"

# start and bind server socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(ADDR)

def send_message(msg, clients, conn):
    # sends message to client that it did not receive the message from
    for client in clients:
        if client != conn:
            client.send(msg.encode(FORMAT))

def send_client_start(conn, item):
    # sends clients their starting information (X or O, who's turn is first)
    conn.send(item.encode(FORMAT))

def handle_client(conn, addr, clients):
    # receives messsages from clients and sends to opposite client
    print(f"[NEW CONNECTION] {addr} connected")

    connected = True
    while connected:
        msg_length = conn.recv(HEADER).decode(FORMAT)
        if msg_length:
            msg_length = int(msg_length)
            msg = conn.recv(msg_length).decode(FORMAT)
            if msg == DISCONNECT_MESSAGE:
                connected = False
            print(f"[{addr}] {msg}")
            if connected:
                send_message(msg, clients, conn)
    conn.close()

def start():
    # beginning, waits for client connections and calls the function to send the clients their starting information
    clients = []
    symbols = ['O', 'X']
    turns = ['0', '1']
    s.listen(2)
    print(f'Server is listening on {SERVER}')
    while True:
        conn, addr = s.accept()
        clients.append(conn)
        send_client_start(conn, symbols[0])
        if len(clients) == 1:
            send_client_start(conn, turns[0])
        else:
            send_client_start(conn, turns[1])
        t = threading.Thread(target=handle_client, args=(conn, addr, clients))
        t.start()
        try:
            del symbols[0]
        except:
            print('[ERROR] Too many players')
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

 
print("[STARTING] server is starting...")
start()