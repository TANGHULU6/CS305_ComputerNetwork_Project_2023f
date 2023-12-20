import base64
import mimetypes
import os
import urllib.parse

AUTHORIZED_USERS = {"user1": "password1", "user2": "password2"}


def handle_request(request):
    headers = parse_headers(request)
    keep_alive = False
    if "Connection" in headers.keys():
        keep_alive = headers.get("Connection").lower() != "close"

    # Add your request handling logic here
    request_line = request.split("\\r\\n")[0].split('\n')[0]

    method, path, _ = request_line.split(' ')

    # 检查授权
    if not is_authorized(headers):
        return generate_unauthorized_response(keep_alive), keep_alive

    # 解析请求路径
    if path == "/":
        return generate_file_list_response(keep_alive), keep_alive
    else:
        return generate_file_download_response(path, keep_alive), keep_alive


def parse_headers(request):
    headers = {}
    lines = request.split("\\r\\n")
    for line in lines[1:]:
        if ": " in line:
            key, value = line.split(": ", 1)
            headers[key] = value
    return headers


def is_authorized(headers):
    auth_header = headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    encoded_credentials = auth_header.split(" ")[1]
    decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
    username, password = decoded_credentials.split(":")
    return username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password


def generate_unauthorized_response(keep_alive):
    response_headers = [
        "HTTP/1.1 401 Unauthorized",
        "Content-Type: text/plain",
        "WWW-Authenticate: Basic realm=\"Authorization Required\"",
        "Content-Length: 23"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "Unauthorized Access!"
    return "\\r\\n".join(response_headers) + "\\r\\n\\r\\n" + response_body


def generate_file_list_response(keep_alive):
    files = os.listdir('./data')
    response_body = "\\n".join(files)
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/plain",
        "Content-Length: " + str(len(response_body))
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return "\\r\\n".join(response_headers) + "\\r\\n\\r\\n" + response_body


def generate_file_download_response(path, keep_alive):
    file_path = os.path.join('./data', urllib.parse.unquote(path[1:]))
    if not os.path.exists(file_path):
        return generate_404_response(keep_alive)

    with open(file_path, 'rb') as file:
        response_body = file.read()
    mime_type, _ = mimetypes.guess_type(file_path)
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: " + (mime_type or "application/octet-stream"),
        "Content-Length: " + str(len(response_body))
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return "\\r\\n".join(response_headers) + "\\r\\n\\r\\n" + str(response_body)


def generate_404_response(keep_alive):
    response_headers = [
        "HTTP/1.1 404 Not Found",
        "Content-Type: text/plain",
        "Content-Length: 13"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "File not found"
    return "\\r\\n".join(response_headers) + "\\r\\n\\r\\n" + response_body
