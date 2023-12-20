import base64
import binascii
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


    url_components = urllib.parse.urlparse(path)
    file_path = os.path.join('./data', url_components.path[1:])
    query_params = urllib.parse.parse_qs(url_components.query)


    if os.path.isdir(file_path):
        return handle_directory_request(file_path, query_params, keep_alive), keep_alive
    elif os.path.isfile(file_path):
        return generate_file_download_response(file_path, keep_alive), keep_alive
    else:
        return generate_404_response(keep_alive), keep_alive


def handle_directory_request(file_path, query_params, keep_alive):
    sustech_http = query_params.get("SUSTech-HTTP", ["0"])[0]
    if sustech_http == "1":
        return generate_directory_list_response(file_path, keep_alive)
    else:
        return generate_html_directory_response(file_path, './data', keep_alive)


def generate_directory_list_response(file_path, keep_alive):
    # Generate a list of items in the directory
    items = os.listdir(file_path)
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: application/json",
        f"Content-Length: {len(items)}"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return ("\r\n".join(response_headers) + "\r\n\r\n" + items).encode('utf-8')


def generate_html_directory_response(path, base_url, keep_alive):
    # Generate HTML content to display the directory listing with links to root and parent directories
    html_content = "<html><body><ul>"

    # Link to the root directory
    html_content += '<li><a href="/">/ (Root Directory)</a></li>'

    # Link to the parent directory
    print('path' + path)
    print('baseurl' + base_url)
    parent_dir = os.path.dirname(path.rstrip('/'))
    if parent_dir != base_url:
        html_content += f'<li><a href="{path[6:]}/../">../ (Parent Directory)</a></li>'
    else:
        # If already at the root, link to the root itself
        html_content += '<li><a href="/">../ (Root Directory)</a></li>'

    for item in os.listdir(path):
        item_path = os.path.join(path, item)

        html_content += f'<li><a href="{item_path[6:]}">{item}</a></li>'

    html_content += "</ul></body></html>"
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/html",
        f"Content-Length: {len(html_content)}"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return ("\r\n".join(response_headers) + "\r\n\r\n" + html_content).encode('utf-8')


def parse_headers(request):
    headers = {}
    lines = request.split("\r\n")
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
    try:
        decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded_credentials.split(":")
        return username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password
    except binascii.Error:
        return False


def generate_unauthorized_response(keep_alive):
    l = len("Unauthorized Access!")
    response_headers = [
        "HTTP/1.1 401 Unauthorized",
        "Content-Type: text/plain",
        "WWW-Authenticate: Basic realm=\"Authorization Required\"",
        f"Content-Length: {l}"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "Unauthorized Access!"
    return ("\r\n".join(response_headers) + "\r\n\r\n" + response_body).encode('utf-8')


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
    return ("\r\n".join(response_headers) + "\r\n\r\n" + response_body).encode('utf-8')


def generate_file_download_response(path, keep_alive):
    # file_path = os.path.join('./data/', urllib.parse.unquote(path[1:]))
    # print(path)
    # print(file_path)
    if not os.path.exists(path):
        return generate_400_response(keep_alive)

    with open(path, 'rb') as file:
        response_body = file.read()
    mime_type, _ = mimetypes.guess_type(path)
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: " + (mime_type or "application/octet-stream"),
        "Content-Length: " + str(len(response_body))
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return ("\r\n".join(response_headers) + "\r\n\r\n").encode('utf-8') +response_body


def generate_400_response(keep_alive):
    response_headers = [
        "HTTP/1.1 400 Bad Request",
        "Content-Type: text/plain",
        "Content-Length: 13"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "File not found"
    return ("\r\n".join(response_headers) + "\r\n\r\n" + response_body).encode('utf-8')


def generate_405_response(keep_alive):
    response_headers = [
        "HTTP/1.1 405 Method Not Allowed",
        "Content-Type: text/plain",
        "Content-Length: 17"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "Method not allowed"
    return ("\r\n".join(response_headers) + "\r\n\r\n" + response_body).encode('utf-8')


def generate_404_response(keep_alive):
    response_headers = [
        "HTTP/1.1 404 Not Found",
        "Content-Type: text/plain",
        "Content-Length: 14"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "File not found"
    return ("\r\n".join(response_headers) + "\r\n\r\n" + response_body).encode('utf-8')
