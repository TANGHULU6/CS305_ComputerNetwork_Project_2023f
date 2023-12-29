import base64
import binascii
import hashlib
import mimetypes
import os
import urllib.parse
import time
import AES
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

AUTHORIZED_USERS = {"12110518": "asdasdasd", "user2": "password2", "client1": "123", "client2": "123", "client3": "123"}
SESSIONS = {}
SESSION_TIMEOUT = 300
encrypt_key = None

def handle_request(request, client_socket):
    global encrypt_key
    header_end = request.find(b'\r\n\r\n') + 4  # 加4是为了包含分界标记本身

    header_data = request[:header_end]

    body_data = request[header_end:]

    header_text = header_data.decode('utf-8')

    headers = parse_headers(header_text)

    keep_alive = True

    chunked = False

    encrypt = False

    if "Connection" in headers.keys():
        keep_alive = headers.get("Connection").lower() != "close"

    if "X-Content-Encrypted" in headers.keys():
        encrypt = (headers.get("X-Content-Encrypted").lower() == "true")

    # Add your request handling logic here
    request_line = header_text.split("\r\n")[0].split('\n')[0]

    method, path, _ = request_line.split(' ')

    is_authed, currentUser, session_id = handle_user_auth(headers)

    response_header = str()
    response_body = bytes()

    if encrypt and not path.startswith('/upload?') and len(body_data) != 0:
        body_data = AES.aes_decrypt(encrypt_key, body_data)

    # 获取非对称加密公钥
    if method == 'GET' and path == '/getPublicKey':
        response_header, response_body = handle_get_public_key(keep_alive)

    # 客户端发送加密后的对称密钥
    elif method == 'POST' and path == '/sendEncryptKey':
        encrypt_key = handle_send_encrypt_key(body_data)
        response_header, response_body = handle_send_encrypt_key_response(keep_alive)
        print(f"|Encrypt Key| \n {encrypt_key}")

    # 检查授权
    elif not is_authed:
        response_header, response_body = generate_401_response(keep_alive)

    elif method == "HEAD" and path == '/':
        response_header, response_body = generate_head_200_response(keep_alive)
    # elif method == "POST" and path == '/':
    #     response_header, response_body = generate_200_response(keep_alive, "Post This")
    elif method == 'GET' and not path.startswith('/upload?') and not path.startswith('/delete?'):

        url_components = urllib.parse.urlparse(path)
        file_path = os.path.join('./data', url_components.path[1:])
        query_params = urllib.parse.parse_qs(url_components.query)

        chunk = query_params.get("chunked")

        if chunk and int(chunk[0]) == 1:
            chunked = True

        if os.path.isdir(file_path):
            response_header, response_body = handle_directory_request(file_path, query_params, keep_alive, currentUser)
        elif os.path.isfile(file_path):
            response_header, response_body = generate_file_download_response(file_path, keep_alive, headers,
                                                                             query_params,
                                                                             client_socket)
        else:
            response_header, response_body = generate_404_response(keep_alive)

    # elif method == 'POST' and not path.startswith('/upload?') and not path.startswith('/delete?'):
    #     response_header, response_body =  generate_400_response(keep_alive)

    elif method != 'POST' and path.startswith('/upload?'):
        response_header, response_body = generate_405_response(keep_alive)

    elif method == 'POST' and path.startswith('/upload?'):
        parsed_url = urllib.parse.urlparse(path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        if 'path' not in query_params:
            response_header, response_body = generate_400_response(keep_alive)
        else:
            path = query_params['path'][0].lstrip('/')
            directory = path.strip('/').split('/')[0]  # 假设目录是路径的第一部分
            if directory != currentUser:
                path = query_params['path'][0].lstrip('/')
                directory = path.strip('/').split('/')[0]  # 假设目录是路径的第一部分
                response_header, response_body = generate_403_response(keep_alive)
            elif directory not in AUTHORIZED_USERS.keys():
                response_header, response_body = generate_404_response(keep_alive)

            else:
                response_header, response_body = handle_post_request(request, headers, './data/' + path, keep_alive,
                                                                     currentUser)

    elif method == 'POST' and path.startswith('/delete?'):

        parsed_url = urllib.parse.urlparse(path)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if 'path' not in query_params:
            response_header, response_body = generate_400_response(keep_alive)
        else:
            path = query_params['path'][0].lstrip('/')
            directory = path.strip('/').split('/')[0]  # 假设目录是路径的第一部分
            real_path = './data/' + path

            if directory != currentUser:
                response_header, response_body = generate_403_response(keep_alive)
            elif not os.path.exists(real_path):
                response_header, response_body = generate_404_response(keep_alive)
            else:
                response_header, response_body = handle_delete_request(real_path, keep_alive)
    else:
        response_header, response_body = generate_405_response(keep_alive)

    # 如果是加密通信
    if encrypt:
        response_body = AES.aes_encrypt(encrypt_key, response_body)
        response_header = response_header.split("\r\n")
        response_header = [header for header in response_header if not header.startswith("Content-Length")]
        response_header.append(f"Content-Length: {len(response_body)}")
        response_header = "\r\n".join(response_header)

    if chunked:
        return None, keep_alive
    elif not is_authed:
        if method == "HEAD":
            return (
                    response_header + f"\r\nSet-Cookie: session-id={session_id}; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/; HttpOnly;" + '\r\n\r\n').encode(
                'utf-8'), keep_alive
        else:
            return (
                           response_header + f"\r\nSet-Cookie: session-id={session_id}; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/; HttpOnly;" + '\r\n\r\n').encode(
                'utf-8') + response_body, keep_alive
    elif currentUser and session_id:
        if method == "HEAD":
            return (
                    response_header + f"\r\nSet-Cookie: session-id={session_id};  Path=/; HttpOnly;" + '\r\n\r\n').encode(
                'utf-8'), keep_alive
        else:
            return (
                           response_header + f"\r\nSet-Cookie: session-id={session_id}; Path=/; HttpOnly;" + '\r\n\r\n').encode(
                'utf-8') + response_body, keep_alive
    elif currentUser is None and session_id is None:
        if method == "HEAD":
            return (
                    response_header + f"\r\nSet-Cookie: session-id={session_id}; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/; HttpOnly;" + '\r\n\r\n').encode(
                'utf-8'), keep_alive
        else:
            return (
                           response_header + f"\r\nSet-Cookie: session-id={session_id}; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/; HttpOnly;" + '\r\n\r\n').encode(
                'utf-8') + response_body, keep_alive
    else:
        if method == "HEAD":
            return (response_header + '\r\n\r\n').encode('utf-8'), keep_alive
        else:
            return (response_header + '\r\n\r\n').encode('utf-8') + response_body, keep_alive


def is_session_valid(session_id):
    if session_id in SESSIONS.keys():
        if time.time() < SESSIONS[session_id]['expiry']:
            return True
        else:
            # Session expired
            del SESSIONS[session_id]
    return False


def handle_chunked_transfer(file_path, client_socket):
    response_headers = [
        "HTTP/1.1 200 OK",
        "Transfer-Encoding: chunked",
        "Content-Type: text/plain",  # or appropriate content type
        # any other necessary headers
    ]
    response_header = "\r\n".join(response_headers) + "\r\n\r\n"

    with open(file_path, 'rb') as file:
        chunk = file.read(1024)  # Read in chunks of 1024 bytes
        while chunk:
            yield f"{len(chunk):X}\r\n".encode('utf-8')  # Chunk size in hex
            yield chunk
            yield b"\r\n"
            chunk = file.read(1024)

    yield b"0\r\n\r\n"  # End of chunks


def handle_user_auth(headers):
    cookies = headers.get('Cookie', '')
    session_id = None
    if cookies and 'session-id=' in cookies:
        session_id = cookies.split('session-id=')[1].split(';')[0]
        if session_id and is_session_valid(session_id):
            is_authed = True
            current_user = get_user_from_session(session_id)
            return is_authed, current_user, None
        else:
            return False, None, None
    is_authed, currentUser = is_authorized(headers)
    if is_authed:
        session_id = generate_session_id(currentUser)
        return is_authed, currentUser, session_id
    return is_authed, None, None


def generate_session_id(username):
    current_time = str(time.time()).encode('utf-8')
    user_bytes = username.encode('utf-8')
    session_id = hashlib.sha256(user_bytes + current_time).hexdigest()
    SESSIONS[session_id] = {'user': username, 'expiry': time.time() + SESSION_TIMEOUT}
    return session_id


def get_user_from_session(session_id):
    if session_id in SESSIONS:
        session_info = SESSIONS[session_id]
        if time.time() < session_info['expiry']:
            return session_info['user']
        else:
            # Session expired
            del SESSIONS[session_id]
    return None


def handle_delete_request(real_path, keep_alive):
    try:
        os.remove(real_path)
        return generate_200_response(keep_alive, "Remove Success!")
    except Exception as e:
        print(f'Error deleting file: {e}')
        return generate_500_response(keep_alive)

def handle_post_request(request, headers, file_path, keep_alive, currentUser):
    if not 'Content-Type' in headers.keys():
        return generate_400_response(keep_alive)

    content_type = headers['Content-Type']
    if 'multipart/form-data' not in content_type:
        return generate_400_response(keep_alive)

    # Extract boundary from content type header
    boundary = content_type.split(';')[1].strip().split('=')[1]

    # Extract and save the file
    return extract_and_save_file(request, boundary, file_path, keep_alive)


def extract_and_save_file(request, boundary, file_path, keep_alive):
    # Split request by boundary
    parts = request.split(b'--' + boundary.encode('utf-8'))

    # Iterate over parts and handle file data
    for part in parts:
        if b'Content-Disposition: form-data' in part:
            # Extract filename
            filename = part.split(b'filename="')[1].split(b'"')[0].decode('utf-8')
            file_content = part.split(b'\r\n\r\n')[1].rstrip(b'\r\n')

            if encrypt_key:
                file_content = AES.aes_decrypt(encrypt_key, file_content)

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Save file
            with open(os.path.join(file_path, filename), 'wb') as file:
                file.write(file_content)

            return generate_200_response(keep_alive, 'Upload success!')

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
    return "\r\n".join(response_headers), str(items).encode('utf-8')


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
    return "\r\n".join(response_headers), html_content.encode('utf-8')


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


def generate_file_download_response_basic(path, keep_alive, query_params, client_socket):
    # file_path = os.path.join('./data/', urllib.parse.unquote(path[1:]))
    # print(path)
    # print(file_path)
    if not os.path.exists(path):
        return generate_400_response(keep_alive)

    chunk = query_params.get("chunked")

    if not (chunk and int(chunk[0]) == 1):
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
        return "\r\n".join(response_headers), response_body
    else:

        mime_type, _ = mimetypes.guess_type(path)
        response_headers = [
            "HTTP/1.1 200 OK",
            "Transfer-Encoding: chunked",
            # "Content-Type: " + (mime_type or "application/octet-stream"),
            # "Content-Type: text/plain",  # or appropriate content type
            # any other necessary headers
        ]
        if keep_alive:
            response_headers.append("Connection: keep-alive")

        client_socket.sendall(("\r\n".join(response_headers) + '\r\n\r\n').encode('utf-8'))

        with open(path, 'rb') as file:
            chunk = file.read(1024)  # Read in chunks of 1024 bytes
            while chunk:
                client_socket.sendall(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")  # Chunk size in hex
                chunk = file.read(1024)

        client_socket.sendall(b"0\r\n\r\n")  # End of chunks
        return None, None


import uuid


def generate_file_download_response(path, keep_alive, headers, query_params, client_socket):
    if not os.path.exists(path):
        return generate_400_response(keep_alive)

    range_header = headers.get("Range")
    if range_header:
        ranges, is_valid = parse_range_header(range_header, path)
        if not is_valid:
            return generate_416_response(keep_alive)

        if len(ranges) == 1:
            start, end = ranges[0]
            return generate_single_range_response(path, start, end, keep_alive)

        boundary = str(uuid.uuid4())
        response_headers, response_body = prepare_multipart_response(boundary, ranges, path, keep_alive)
        return "\r\n".join(response_headers), response_body
    else:
        return generate_file_download_response_basic(path, keep_alive, query_params, client_socket)


def parse_range_header(range_header, file_path):
    size = os.path.getsize(file_path)
    ranges = []
    is_valid = True
    for part in range_header.replace("bytes=", "").split(","):
        start_end = part.split("-")
        start = int(start_end[0]) if start_end[0] != '' else None
        end = int(start_end[1]) if start_end[1] != '' else size - 1
        if start is None:
            start = size - end
            end = size - 1
        if start <= end and end < size:
            ranges.append((start, end))
        else:
            is_valid = False
            break
    return ranges if ranges and is_valid else None, is_valid


def prepare_multipart_response(boundary, ranges, path, keep_alive):
    response_headers = [
        "HTTP/1.1 206 Partial Content",
        "Content-Type: multipart/byteranges; boundary={}".format(boundary)
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = b""
    for start, end in ranges:
        part_content = read_file_part(path, start, end)
        mime_type, _ = mimetypes.guess_type(path)
        response_body += bytes("--{}\r\n".format(boundary), 'utf-8')
        response_body += bytes("Content-Type: {}\r\n".format(mime_type or "application/octet-stream"), 'utf-8')
        response_body += bytes("Content-Range: bytes {}-{}/{}\r\n\r\n".format(start, end, os.path.getsize(path)),
                               'utf-8')
        response_body += part_content
        response_body += b"\r\n"
    response_body += bytes("--{}--\r\n".format(boundary), 'utf-8')
    response_headers.append("Content-Length: " + str(len(response_body)))
    return response_headers, response_body


def read_file_part(path, start, end):
    with open(path, 'rb') as file:
        file.seek(start)
        return file.read(end - start + 1)


# 生成单个范围的响应
def generate_single_range_response(path, start, end, keep_alive):
    part_content = read_file_part(path, start, end)
    mime_type, _ = mimetypes.guess_type(path)
    response_headers = [
        "HTTP/1.1 206 Partial Content",
        "Content-Type: " + (mime_type or "application/octet-stream"),
        "Content-Length: " + str(len(part_content)),
        "Content-Range: bytes {}-{}/{}".format(start, end, os.path.getsize(path))
    ]
    if keep_alive:
        response_headers.append("Connection: keep_alive")
    return "\r\n".join(response_headers), part_content


def generate_416_response(keep_alive):
    response_headers = [
        "HTTP/1.1 416 Range Not Satisfiable",
        "Content-Type: text/plain",
        "Content-Length: 0"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return "\r\n".join(response_headers), b''


def generate_401_response(keep_alive):
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
    return "\r\n".join(response_headers), response_body.encode('utf-8')


def generate_400_response(keep_alive):
    response_headers = [
        "HTTP/1.1 400 Bad Request",
        "Content-Type: text/plain",
        "Content-Length: 14"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "File not found"
    return "\r\n".join(response_headers), response_body.encode('utf-8')


def generate_403_response(keep_alive):
    response_headers = [
        "HTTP/1.1 403 Forbidden",
        "Content-Type: text/plain",
        "Content-Length: 14"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "No Authorized!"
    return "\r\n".join(response_headers), response_body.encode('utf-8')


def generate_405_response(keep_alive):
    response_headers = [
        "HTTP/1.1 405 Method Not Allowed",
        "Content-Type: text/plain",
        "Content-Length: 18"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "Method not allowed"
    return "\r\n".join(response_headers), response_body.encode('utf-8')


def generate_404_response(keep_alive):
    response_headers = [
        "HTTP/1.1 404 Not Found",
        "Content-Type: text/plain",
        "Content-Length: 14"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "File not found"
    return "\r\n".join(response_headers), response_body.encode('utf-8')


def generate_200_response(keep_alive, response_body):
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/plain",
        f"Content-Length: {len(response_body)}"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return "\r\n".join(response_headers), response_body.encode('utf-8')


def generate_500_response(keep_alive):
    response_headers = [
        "HTTP/1.1 500 System Error",
        "Content-Type: text/plain",
        "Content-Length: 19"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "Delete file failed."
    return "\r\n".join(response_headers), response_body.encode('utf-8')


def generate_head_200_response(keep_alive):
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/plain",
        f"Content-Length: 0"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    return "\r\n".join(response_headers), None

def handle_get_public_key(keep_alive):
    with open('public_key.pem', 'rb') as pub_key_file:
        public_key = pub_key_file.read()
    return generate_200_response(keep_alive, public_key.__str__())

def handle_send_encrypt_key(body_data):
    # 使用之前的 decrypt_with_private_key 函数解密接收到的对称密钥
    return decrypt_with_private_key(body_data)

def handle_send_encrypt_key_response(keep_alive):
    # 使用之前的 decrypt_with_private_key 函数解密接收到的对称密钥
    return generate_200_response(keep_alive, "Send Success!")

def decrypt_with_private_key(encrypted_data):
    with open('private_key.pem', 'rb') as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None
        )

    decrypted_data = private_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    return decrypted_data
