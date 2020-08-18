""" local http.server.ThreadingHTTPServer to run mirror """
import argparse
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import NoReturn

from mirror import Mirror


class ThreadingHTTPServerMirror(Mirror):
    """ Add ThreadingHTTPServer usage in Mirror class """
    def __init__(self, port: int, proto: str, host: str, emoji: str):
        super().__init__(proto=proto, host=host, emoji=emoji)
        self.port = port

    def start(self) -> None:
        """ start to serve the HTTP server """
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s: %(levelname)s: %(message)s"
        )
        server = ThreadingHTTPServer(('', self.port), self.get_handler())
        logging.info('Start server on %d port. Use ctrl+C to stop it.', self.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        server.server_close()
        logging.info('Server stopped')

    def get_handler(self):
        """ define and return Handler class which need to use in HTTPServer """
        mirror = self

        class Handler(BaseHTTPRequestHandler):
            """ this will be used in HTTPServer """
            def do_GET(self):  # pylint: disable=C0103
                """ handle GET request """
                logging.info("GET %s", self.path)
                headers = {}
                for header_line in str(self.headers).rstrip().split('\n'):
                    key, value = header_line.split(': ')
                    if key.lower() == 'host':
                        continue
                    headers[key] = value

                response = mirror.request_host('get', self.path, headers=headers)
                logging.info('requested %s, status:%s', response.url, response.status_code)

                content = response.content
                content_type = response.headers.get('content-type', '')
                if 'text/html' in content_type:
                    encoding = 'utf-8'
                    if 'charset' in content_type:
                        encoding = content_type.split('charset=')[1]
                    content = mirror.modify_html(content, encoding=encoding)
                    logging.info('modified %s', response.url)

                self.send(response.status_code, response.headers, content)
                logging.info('sent %s to client', self.path)

            def send(self, code: int, headers, content: bytes) -> NoReturn:
                """ send response back to user """
                self.send_response(code)
                for header in headers:
                    if header.lower() not in [
                            'server', 'date', 'transfer-encoding',
                            'content-encoding', 'connection']:
                        self.send_header(header, headers[header])

                self.end_headers()
                self.wfile.write(content)

        return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Local mirror of some site with emoji injection after each 6-letter word.')
    parser.add_argument('emoji', type=str, help='What emojis need to insert on a page')
    parser.add_argument('--port', default=9000, type=int, help='Port to listen. Default to 9000')
    parser.add_argument('--host', default='lifehacker.ru', type=str,
                        help='What the site will be displayed. Default to lifehacker.ru')
    parser.add_argument('--http', dest='proto', action='store_const', const='http://',
                        default='https://', help='Send http instead of https')

    args = parser.parse_args()
    ThreadingHTTPServerMirror(**vars(args)).start()
