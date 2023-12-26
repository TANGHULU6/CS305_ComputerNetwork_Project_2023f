import http_server

def main(host='localhost', port=8080):
    server = http_server.HttpServer(host, port)
    server.run()

if __name__ == '__main__':
    main()
