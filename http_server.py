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
                request = bytes()
                content_length = None
                header_end = None
                while True:
                    # 接收数据
                    chunk = client_socket.recv(1024)
                    if not chunk:
                        # 如果没有数据，跳出循环
                        break
                    request += chunk


                    # 检查是否收到完整的HTTP头部
                    if b'\r\n\r\n' in request and content_length is None:
                        header_end = request.find(b'\r\n\r\n') + 4  # 加4是为了包含分界标记本身
                        headers, _ = request.split(b'\r\n\r\n', 1)
                        for line in headers.split(b'\r\n'):
                            if line.lower().startswith(b'content-length:'):
                                content_length = int(line.split(b':')[1].strip())

                    content = request[header_end:]
                    # 检查是否已经接收到了所有预期的数据
                    if content_length is not None and len(content) >= content_length:
                        break

                    if content_length is None:
                        break

                if not request:
                    continue
                response, keep_alive = handle_request(request)
                print(f'|SEND| \n {response}')
                client_socket.sendall(response)
            # client_socket.close()


