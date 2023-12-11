import http_server

def main():
    server = http_server.HttpServer('localhost', 8080)
    server.run()

if __name__ == '__main__':
    main()
