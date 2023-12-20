import base64

AUTHORIZED_USERS = {"user1": "password1", "user2": "password2"}


def handle_request(request):
    headers = parse_headers(request)
    keep_alive = False
    if "Connection" in headers.keys():
        keep_alive = headers.get("Connection").lower() != "close"

    # Check for basic authorization header
    if not is_authorized(headers):
        return generate_unauthorized_response(), keep_alive

    # Add your request handling logic here
    response_headers = [
        "HTTP/1.1 200 OK",
        "Content-Type: text/plain",
        "Content-Length: 13"
    ]
    if keep_alive:
        response_headers.append("Connection: keep-alive")
    response_body = "Hello, Authorized User!"
    return "\\r\\n".join(response_headers) + "\\r\\n\\r\\n" + response_body, keep_alive


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


def generate_unauthorized_response():
    response_headers = [
        "HTTP/1.1 401 Unauthorized",
        "Content-Type: text/plain",
        "WWW-Authenticate: Basic realm=\"Authorization Required\"",
        "Content-Length: 23"
    ]
    response_body = "Unauthorized Access!"
    return "\\r\\n".join(response_headers) + "\\r\\n\\r\\n" + response_body
