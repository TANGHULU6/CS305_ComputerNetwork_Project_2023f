import socket
from request_handler import handle_request

class HttpServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"Server running on {self.host}:{self.port}")

            while True:
                client_socket, addr = server_socket.accept()
                request = client_socket.recv(1024).decode('utf-8')
                response = handle_request(request)
                client_socket.sendall(response.encode('utf-8'))
                client_socket.close()
