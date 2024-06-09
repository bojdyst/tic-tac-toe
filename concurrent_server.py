import socket
import threading
import ssl
import logging
import atexit
import os
import json
from datetime import datetime
from flask import Flask, render_template

def get_server_ip():
    # Get server IP address by connecting to Google DNS server. If cannot connect, return localhost address
    try:
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_socket.settimeout(2)
        temp_socket.connect(('8.8.8.8', 1))
        ip_address = temp_socket.getsockname()[0]
        temp_socket.close()
        return ip_address
    except Exception as e:
        logging.error(f"Could not determine server external IP address: {e}.")
        return '127.0.0.1'

SERVER = get_server_ip() # Server IP
PORT = 5050 # Server game port
ADDR = (SERVER, PORT) # Server game IP and port
FORMAT = 'utf-8' # Messages format
DISCOVERY_PORT = 5051 # Discovery port that server is listening on
MULTICAST_GROUP = '224.0.0.1' # Discovery multicast group that server is listening on

def handle_discovery():
    # Multicast UDP service discovery handler. Allows clients on the network to discover the server's address by sending a multicast message "DISCOVER_SERVER".
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

# Start discovery service as a separate thread
discovery_thread = threading.Thread(target=handle_discovery, daemon=True)
discovery_thread.start()

def load_history():
    # Load history variable from history.json   
    if not os.path.exists('history.json'):
        with open('history.json', 'w') as file:
            json.dump([], file)
    with open('history.json', 'r') as file:
        return json.load(file)

def load_scoreboard():
    # Load scoreboard variable from scoreboard.json
    if not os.path.exists('scoreboard.json'):
        with open('scoreboard.json', 'w') as file:
            json.dump([], file)
    with open('scoreboard.json', 'r') as file:
        return json.load(file)

def save_history(historyf):
    # Save current history to history.json
    with open('history.json', 'w') as file:
        json.dump(history, file, indent=4)

def save_scoreboard(scoreboard):
    # Save current scoreboard to scoreboard.json
    with open('scoreboard.json', 'w') as file:
        json.dump(scoreboard, file, indent=4)

# load global variables
scoreboard = load_scoreboard()
history = load_history()

# Function to handle a single game session
def handle_game(client_socket_1, nickname_1, client_socket_2, nickname_2):
    board = [' ' for _ in range(9)]
    player = 'X'

    def print_board():
        board_display = ""
        for i in range(3):
            row = " | ".join(board[i * 3: (i + 1) * 3])
            board_display += f"{row}\n"
            if i < 2:
                board_display += "--+---+--\n"
        send_string_to_both_clients(board_display)

    def check_win(player):
        win_conditions = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
        return any(board[a] == board[b] == board[c] == player for a, b, c in win_conditions)

    def send_string_to_both_clients(string):
        client_socket_1.send(string.encode())
        client_socket_2.send(string.encode())

    while True:
        try:
            if hasattr(client_socket_2, 'raddr'):
                print(client_socket_2)
            if hasattr(client_socket_1, 'raddr'):
                print(client_socket_1)
            print_board()
            if player == 'X':
                client_socket = client_socket_1
            else:
                client_socket = client_socket_2

            client_socket.send(f"Your move ({player}): ".encode())

            client_message = client_socket.recv(1024).decode()

            if client_message not in ['0', '1', '2', '3', '4', '5', '6', '7', '8']:
                client_socket.send("Invalid move. Try again.".encode())
            else:
                move = int(client_message)
                if board[move] == ' ':
                    board[move] = player
                    if check_win(player):
                        print_board()
                        if player == 'X':
                            winner, loser = nickname_1, nickname_2
                        else:
                            winner, loser = nickname_2, nickname_1
                        update_results(winner, loser)    
                        send_string_to_both_clients(f"{player} ({winner}) wins!")
                        break
                    elif ' ' not in board:
                        print_board()
                        send_string_to_both_clients("It's a draw!")
                        break
                    player = 'O' if player == 'X' else 'X'
                else:
                    client_socket.send("Invalid move. Try again.".encode())

        except Exception as e:
            logging.error(f"{e} error occurred. Connection closed by client.")
            try:
                print(client_socket_1.getpeername())
                client_socket_1.send(f"Your opponent {nickname_2} has left the game. Please play another one.".encode())
            except:
                pass
            
            try:
                print(client_socket_2.getpeername())
                client_socket_2.send(f"Your opponent {nickname_1} has left the game. Please play another one.".encode())
            except:
                pass                
            
            break

    client_socket_1.close()
    client_socket_2.close()
    
def update_results(winner, loser):
    # Update current results available on flask app
    found = False
    # Add point for a winner
    for entry in scoreboard:
        if entry['nickname'] == winner:
            logging.info(f"+1 point for {winner}.")
            entry['score'] += 1
            found = True
            break
    if not found:
        logging.info(f"Adding new player: {winner}.")
        scoreboard.append({'nickname': winner, 'score': 1})
    
    # Remove point for a loser
    for entry in scoreboard:
        if entry['nickname'] == loser:
            logging.info(f"-1 point for {loser}.")
            entry['score'] -= 1

    # Update history
    game_result = {
        'nicknames': f"{winner}-{loser}",
        'winner': winner,
        'date': datetime.today().strftime('%Y-%m-%d %H:%M:%S')
    }
    history.append(game_result)

def on_exit(scoreboard, history):
    save_scoreboard(scoreboard)
    save_history(history)

def start_server():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="sample_cert.pem", keyfile="sample_key.pem")
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SERVER, PORT))
    server.listen(5)
    print("Server started, waiting for connections...")

    while True:
        client_socket_1, addr1 = server.accept()
        client_socket_1 = context.wrap_socket(client_socket_1, server_side=True)
        nickname_1 = client_socket_1.recv(1024).decode().strip()
        print(f"Player 1 connected from {addr1} ({nickname_1})")
        client_socket_1.send("Waiting for another player...".encode())

        client_socket_2, addr2 = server.accept()
        client_socket_2 = context.wrap_socket(client_socket_2, server_side=True)
        nickname_2 = client_socket_2.recv(1024).decode().strip()
        print(f"Player 2 connected from {addr2} ({nickname_2})")

        # Start a new thread for each game session
        game_thread = threading.Thread(target=handle_game, args=(client_socket_1, nickname_1, client_socket_2, nickname_2))
        
        game_thread.start()

if __name__ == "__main__":
    logging.basicConfig(filename='server.log', level=logging.INFO)
    atexit.register(on_exit,scoreboard,history)
    app = Flask(__name__)    
    # Main game page
    @app.route('/')
    def indexMain():
        return render_template('main.html')

    # Scoreboard route
    @app.route('/scoreboard')
    def indexScoreboard():
        scoreboard.sort(key=lambda x: x['score'], reverse=True)
        return render_template('scoreboard.html', scoreboard=scoreboard)

    # History route
    @app.route('/history')
    def indexHistory():
        history.sort(key=lambda x: x['date'], reverse=True)
        return render_template('history.html', history=history)

    def run_flask():
        app.run(debug=True, host=SERVER, use_reloader=False)

    # Run Flask app in separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    start_server()