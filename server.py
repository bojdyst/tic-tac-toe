from flask import Flask, render_template
import socket
import logging
import threading
import atexit
import random
import time
import json
import os
from datetime import datetime

PORT = 5050
SERVER = '0.0.0.0'
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCOVERY_PORT = 5051
MULTICAST_GROUP = '224.0.0.1'

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

discovery_thread = threading.Thread(target=handle_discovery, daemon=True)
discovery_thread.start()

class TicTacToeServer:
    def __init__(self, host=SERVER, port=PORT):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(2)
        self.players = []
        self.board = [' ' for _ in range(9)]
        self.current_turn = 0
        self.scoreboard = self.load_scoreboard()
        self.history = self.load_history()
        self.lock = threading.Lock()
        self.game_active = False
        logging.info("Server started, waiting for players...")

    def load_history(self):
        if not os.path.exists('history.json'):
            with open('history.json', 'w') as file:
                json.dump([], file)
        with open('history.json', 'r') as file:
            return json.load(file)

    def save_history(self):
        with open('history.json', 'w') as file:
            json.dump(self.history, file, indent=4)

    def load_scoreboard(self):
        if not os.path.exists('scoreboard.json'):
            with open('scoreboard.json', 'w') as file:
                json.dump([], file)
        with open('scoreboard.json', 'r') as file:
            return json.load(file)

    def save_scoreboard(self):
        with open('scoreboard.json', 'w') as file:
            json.dump(self.scoreboard, file, indent=4)

    def update_flask(self, winner, loser):
        found = False
        # Adds point for a winner
        for entry in self.scoreboard:
            if entry['nickname'] == winner:
                logging.info(f"+1 point for {winner}.")
                entry['score'] += 1
                found = True
                break
        if not found:
            logging.info(f"Adding new player: {winner}.")
            self.scoreboard.append({'nickname': winner, 'score': 1})
        
        # Removes point for a loser
        for entry in self.scoreboard:
            if entry['nickname'] == loser:
                logging.info(f"-1 point for {loser}.")
                entry['score'] -= 1

        # Updates history
        game_result = {
            'nicknames': f"{winner}-{loser}",
            'winner': winner,
            'date': datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.history.append(game_result)

    def start(self):
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while True:
            client_socket, addr = self.server_socket.accept()
            logging.info(f"Player connected from {addr}")
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def handle_client(self, client_socket):
        client_socket.sendall("Enter your nickname: ".encode())
        nickname = client_socket.recv(1024).decode().strip()
        self.lock.acquire()
        self.players.append((client_socket, nickname))
        if len(self.players) == 2:
            self.game_active = True
            self.lock.release()
            self.start_game()
        else:
            self.lock.release()
            client_socket.sendall("Waiting for the second player...\n".encode())

        while not self.game_active:
            time.sleep(1)

        self.play_game(client_socket, nickname)
        client_socket.close()  # Close the client socket after the game ends

    def start_game(self):
        for player in self.players:
            player[0].sendall(f"Game starting! Your opponent is {self.players[1 - self.players.index(player)][1]}\n".encode())
        self.broadcast("The game has started!\n")
        self.broadcast_board()

    def play_game(self, client_socket, nickname):
        while self.game_active:
            self.lock.acquire()
            try:
                if self.players[self.current_turn][1] == nickname:
                    client_socket.sendall("Your turn! Enter the position (1-9): ".encode())
                    client_socket.settimeout(10.0)
                    move = client_socket.recv(1024).decode().strip()
                    if move.isdigit() and 1 <= int(move) <= 9 and self.board[int(move) - 1] == ' ':
                        move = int(move) - 1
                        self.board[move] = 'X' if self.current_turn == 0 else 'O'
                        self.broadcast(f"Move {move + 1}\n")
                        self.broadcast_board()
    
                        if self.check_winner():
                            self.broadcast(f"Game over! Winner: {nickname}\nScoreboard and history of games can be seen under: http://{SERVER}:5000")
                            for _, n in self.players:
                                if n != nickname:
                                    loser = n
                            self.update_flask(nickname, loser)
                            self.game_active = False
                        elif ' ' not in self.board:
                            self.broadcast("Game over! It's a draw!\n")
                            self.game_active = False
                        self.current_turn = 1 - self.current_turn
                    else:
                        client_socket.sendall("Invalid move! Try again.\n".encode())
            except socket.timeout:
                move = self.random_move()
                self.board[move] = 'X' if self.current_turn == 0 else 'O'
                self.broadcast(f"Move {move + 1} (timeout)\n")
                self.broadcast_board()

                if self.check_winner():
                    self.broadcast(f"Game over! Winner: {nickname}\n")
                    for _, n in self.players:
                            if n != nickname:
                                self.decrement_points(n)
                    self.increment_points(nickname)
                    self.game_active = False
                elif ' ' not in self.board:
                    self.broadcast("Game over! It's a draw!\n")
                    self.game_active = False
                self.current_turn = 1 - self.current_turn
            except ConnectionResetError:
                self.game_active = False
            finally:
                self.lock.release()
                time.sleep(1)
            
        # Remove players after the game ends
        self.lock.acquire()
        for player in self.players:
            if player[0] == client_socket:
                self.players.remove(player)
                break
        self.board = [' ' for _ in range(9)]
        self.lock.release()
        client_socket.close()  # Close the client socket after the game ends


    def random_move(self):
        available_moves = [i for i, v in enumerate(self.board) if v == ' ']
        return random.choice(available_moves)

    def check_winner(self):
        time.sleep(1)
        winning_combinations = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
            [0, 4, 8], [2, 4, 6]              # Diagonals
        ]
        for combo in winning_combinations:
            if self.board[combo[0]] == self.board[combo[1]] == self.board[combo[2]] != ' ':
                return True
        return False

    def broadcast(self, message):
        for player in self.players:
            try:
                player[0].sendall(message.encode())
            except:
                pass

    def broadcast_board(self):
        board_display = ""
        for i in range(3):
            row = " | ".join(self.board[i * 3: (i + 1) * 3])
            board_display += f"{row}\n"
            if i < 2:
                board_display += "---------\n"
        self.broadcast(board_display)

def on_exit(server):
    server.save_scoreboard()
    server.save_history()

if __name__ == "__main__":
    logging.basicConfig(filename='server.log', level=logging.INFO)
    server = TicTacToeServer()
    server.start()
    atexit.register(on_exit,server)
    app = Flask(__name__)
        
    @app.route('/')
    def indexMain():
        return render_template('main.html')

    @app.route('/scoreboard')
    def indexScoreboard():
        server.scoreboard.sort(key=lambda x: x['score'], reverse=True)
        return render_template('scoreboard.html', scoreboard=server.scoreboard)

    @app.route('/history')
    def indexHistory():
        server.history.sort(key=lambda x: x['date'], reverse=True)
        return render_template('history.html', history=server.history)

    def run_flask():
        app.run(debug=True, host='0.0.0.0', use_reloader=False)

    # Run Flask app in separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    while True:
        time.sleep(1)
