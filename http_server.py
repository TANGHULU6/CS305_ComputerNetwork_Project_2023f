# http_server.py

import socket
import threading
from request_handler import handle_request

class HttpServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"Server running on {self.host}:{self.port}")

            while True:
                client_socket, addr = server_socket.accept()
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
                client_thread.start()

    def handle_client(self, client_socket, addr):
        with client_socket:
            print(f"Connected by {addr}")
            keep_alive = True
            while keep_alive:
                request = client_socket.recv(1024).decode('utf-8')
                if not request:
                    continue
                response, keep_alive = handle_request(request)
                print(f'send {response}')
                client_socket.sendall(response.encode('utf-8'))


