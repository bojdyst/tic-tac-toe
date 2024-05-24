import socket
import threading
import os

class TicTacToeClient:
    def __init__(self, host='localhost', port=12345):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((host, port))
        self.nickname = input("Enter your nickname: ")
        self.client_socket.sendall(self.nickname.encode())
        self.board = [' ' for _ in range(9)]
        self.game_active = True

    def start(self):
        threading.Thread(target=self.receive_messages, daemon=True).start()
        self.play_game()

    def receive_messages(self):
        while self.game_active:
            try:
                message = self.client_socket.recv(1024).decode()
                if message:
                    if message.startswith("Move"):
                        move = int(message.split()[1]) - 1
                        self.update_board(move)
                        self.print_board()
                    elif "Game over" in message:
                        self.print_board()
                        print(message)
                        self.game_active = False
                        self.client_socket.close()
                        os._exit(os.EX_OK)
                    else:
                        self.print_board()
                        print(message)
                else:
                    self.client_socket.close()
                    break
            except Exception as e:
                print("Error receiving message:", e)
                self.client_socket.close()
                break

    def play_game(self):
        while self.game_active:
            try:
                move = input("Enter your move (1-9): ")
                if move.isdigit() and 1 <= int(move) <= 9 and self.board[int(move) - 1] == ' ':
                    self.client_socket.sendall(move.encode())
                else:
                    print("Invalid move. Try again.")
            except Exception as e:
                print("Error sending move:", e)
                self.client_socket.close()
                break

    def update_board(self, move):
        symbol = 'X' if self.board.count('X') <= self.board.count('O') else 'O'
        self.board[move] = symbol

    def print_board(self):
        os.system('clear')
        print("\nCurrent board:")
        for i in range(3):
            print(" " + " | ".join(self.board[i*3:(i+1)*3]))
            if i < 2:
                print("---+---+---")

if __name__ == "__main__":
    client = TicTacToeClient()
    client.start()

