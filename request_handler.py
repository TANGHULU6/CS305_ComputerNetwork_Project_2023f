import base64
import binascii
import mimetypes
import os
import urllib.parse

AUTHORIZED_USERS = {"12110518": "asdasdasd", "user2": "password2", "client1": "123"}


def handle_request(request):

    header_end = request.find(b'\r\n\r\n') + 4  # 加4是为了包含分界标记本身

    header_data = request[:header_end]
    body_data = request[header_end:]

    header_text = header_data.decode('utf-8')

    headers = parse_headers(header_text)

    keep_alive = True
    if "Connection" in headers.keys():
        keep_alive = headers.get("Connection").lower() != "close"

    # Add your request handling logic here
    request_line = header_text.split("\r\n")[0].split('\n')[0]

    method, path, _ = request_line.split(' ')

    is_authed, currentUser = is_authorized(headers)
    # 检查授权
    if not is_authed:
        return generate_unauthorized_response(keep_alive), keep_alive

    if method == 'GET' and not path.startswith('/upload?'):

        url_components = urllib.parse.urlparse(path)
        file_path = os.path.join('./data', url_components.path[1:])
        query_params = urllib.parse.parse_qs(url_components.query)

        if os.path.isdir(file_path):
            return handle_directory_request(file_path, query_params, keep_alive, currentUser), keep_alive
        elif os.path.isfile(file_path):
            return generate_file_download_response(file_path, keep_alive), keep_alive
        else:
            return generate_404_response(keep_alive), keep_alive

    elif method == 'POST' and not path.startswith('/upload?'):
        return generate_400_response(keep_alive), keep_alive

    elif method == 'POST' and path.startswith('/upload?'):
        parsed_url = urllib.parse.urlparse(path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        if 'path' not in query_params:
            return generate_404_response(keep_alive), keep_alive

        path = query_params['path'][0].lstrip('/')
        directory = path.strip('/').split('/')[0]  # 假设目录是路径的第一部分
        print(directory)
        if directory != currentUser:
            return generate_403_response(keep_alive), keep_alive
        return handle_post_request(request, headers, './data/' + path, keep_alive, currentUser)



def handle_post_request(request, headers, file_path, keep_alive, currentUser):
    if not 'Content-Type' in headers.keys():
        return generate_400_response(keep_alive), keep_alive

    content_type = headers['Content-Type']
    if 'multipart/form-data' not in content_type:
        return generate_400_response(keep_alive), keep_alive

    # Extract boundary from content type header
    boundary = content_type.split(';')[1].strip().split('=')[1]

    # Extract and save the file
    return extract_and_save_file(request, boundary, file_path, keep_alive), keep_alive


def extract_and_save_file(request, boundary, file_path, keep_alive):
    # Split request by boundary
    parts = request.split(b'--' + boundary.encode('utf-8'))

    # Iterate over parts and handle file data
    for part in parts:
        if b'Content-Disposition: form-data' in part:
            # Extract filename
            filename = part.split(b'filename="')[1].split(b'"')[0].decode('utf-8')
            file_content = part.split(b'\r\n\r\n')[1].rstrip(b'\r\n')

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Save file
            with open(os.path.join(file_path, filename), 'wb') as file:
                file.write(file_content)

            return generate_200_response(keep_alive)

    return generate_400_response(keep_alive)


def handle_directory_request(file_path, query_params, keep_alive, currentUser):
    sustech_http = query_params.get("SUSTech-HTTP", ["0"])[0]
    if sustech_http == "1":
        return generate_directory_list_response(file_path, keep_alive)
    else:
        return generate_html_directory_response(file_path, './data', keep_alive, currentUser)


def generate_directory_list_response(file_path, keep_alive):
    # Generate a list of items in the directory
    items = os.listdir(file_path)
    # print(file_path)
    # if os.path.isdir('./data\\t1/t2'):
    #     print('YES')
    for i in range(len(items)):
        if os.path.isdir(file_path + '/' + items[i]):
            items[i] = items[i] + '/'
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/plain",
        f"Content-Length: {len(str(items))}"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return ("\r\n".join(response_headers) + "\r\n\r\n" + str(items)).encode('utf-8')


def generate_html_directory_response(path, base_url, keep_alive, currentUser):
    # Generate HTML content to display the directory listing with links to root and parent directories
    html_content = "<html><body><ul>"

    # Link to the root directory
    html_content += '<li><a href="/">/ (Root Directory)</a></li>'

    # Link to the parent directory
    parent_dir = os.path.dirname(path.rstrip('/'))
    if parent_dir != base_url:
        html_content += f'<li><a href="{path[6:]}/../">../ (Parent Directory)</a></li>'
    else:
        # If already at the root, link to the root itself
        html_content += '<li><a href="/">../ (Root Directory)</a></li>'

    for item in os.listdir(path):
        item_path = os.path.join(path, item)

        html_content += f'<li><a href="{item_path[6:]}">{item}</a></li>'

    html_content += "</ul>"
    html_content += f"<form id=\"uploadForm\" method=\"post\" enctype=\"multipart/form-data\"><label for=\"url-input\">Upload location:</label><input type=\"text\" id=\"url-input\" placeholder=\"/\"><label for=\"file-upload\">Choose file:</label><input type=\"file\" id=\"file-upload\" name=\"file\"><input type=\"submit\" value=\"Upload File\"></form><script>    document.getElementById('uploadForm').onsubmit = function(event)" + " {var actionUrl = document.getElementById('url-input').value; this.action = \'http://localhost:8080/upload?path=/" + f'{currentUser}' + "/\' + actionUrl; };</script></body></html>"
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
        return False, None
    encoded_credentials = auth_header.split(" ")[1]
    try:
        decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded_credentials.split(":")
        return username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password, username
    except binascii.Error:
        return False, None


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
        "Content-Length: 14"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "File not found"
    return ("\r\n".join(response_headers) + "\r\n\r\n" + response_body).encode('utf-8')

def generate_403_response(keep_alive):
    response_headers = [
        "HTTP/1.1 403 Forbidden",
        "Content-Type: text/plain",
        "Content-Length: 14"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "No Authorized!"
    return ("\r\n".join(response_headers) + "\r\n\r\n" + response_body).encode('utf-8')


def generate_405_response(keep_alive):
    response_headers = [
        "HTTP/1.1 405 Method Not Allowed",
        "Content-Type: text/plain",
        "Content-Length: 18"
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


def generate_200_response(keep_alive):
    response_body = "Upload success!"
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/plain",
        f"Content-Length: {len(response_body)}"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return ("\r\n".join(response_headers) + "\r\n\r\n" + response_body).encode('utf-8')
