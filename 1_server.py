import socket
import threading
import atexit
import random
import time
import json

class TicTacToeServer:
    def __init__(self, host='0.0.0.0', port=12345):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(2)
        self.players = []
        self.board = [' ' for _ in range(9)]
        self.current_turn = 0
        self.scoreboard = self.load_scoreboard()
        self.lock = threading.Lock()
        self.game_active = False
        print("Server started, waiting for players...")
    
    def load_scoreboard(self):
        with open('scoreboard.json', 'r') as file:
            return json.load(file)

    def save_scoreboard(self):
        with open('scoreboard.json', 'w') as file:
            json.dump(self.scoreboard, file, indent=4)

    def add_points_for_winner(self, nickname):
        found = False
        for entry in self.scoreboard:
            if entry['nickname'] == nickname:
                print(f"Adding 1 point for {nickname}.")
                entry['score'] += 1
                found = True
                break
        if not found:
            print(f"Adding new player: {nickname}.")
            self.scoreboard.append({'nickname': nickname, 'score': 1})

    def start(self):
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"Player connected from {addr}")
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
                            self.broadcast(f"Game over! Winner: {nickname}\n")
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

if __name__ == "__main__":
    server = TicTacToeServer()
    server.start()
    atexit.register(on_exit,server)
    while True:
        time.sleep(1)

