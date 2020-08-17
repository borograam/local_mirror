"""
Local mirror of some site with emoji injection after each 6-letter word.
"""
import argparse
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import NoReturn, Iterator

import requests
from bs4 import BeautifulSoup, NavigableString


class Mirror:
    """ Each object is independent and manages a separate server """
    def __init__(self, port: int, proto: str, host: str, emoji: str):
        self.port = port
        self.proto = proto
        self.host = host

        self._emoji_iterator = Mirror.emoji_generator(emoji)

    @staticmethod
    def emoji_generator(emoji: str) -> Iterator[str]:
        """ returns infinite iterator of chars from `emoji` string """
        while True:
            for char in emoji:
                yield char

    @property
    def emoji(self):
        """ returns the next emoji """
        return next(self._emoji_iterator)

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
                response = mirror.get_from_host(self.path, str(self.headers))
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

    def get_from_host(self, path: str, headers: str) -> requests.Response:
        """ request `path` page from `self.host` """
        header_dict = {}
        for header_line in headers.rstrip().split('\n'):
            key, value = header_line.split(': ')
            if key.lower() == 'host':
                continue
            header_dict[key] = value

        return requests.get(
            f'{self.proto}{self.host}{path}',
            headers=header_dict
        )

    def modify_html(self, content: bytes, encoding: str) -> bytes:
        """ perform some html modifications """
        soup = BeautifulSoup(content, 'html5lib', from_encoding=encoding)

        # change a[href] absolute paths to relative
        host_for_re = self.host.replace('.', r'\.')
        domain_re = re.compile(f'^(?:https?://)?{host_for_re}')
        for tag in soup('a', href=domain_re):
            tag['href'] = domain_re.sub('', tag['href'])

        # change [src] and link[href] paths to relative
        for tag in soup(src=domain_re):
            tag['src'] = domain_re.sub('', tag['src'])
        for tag in soup('link', href=domain_re):
            tag['href'] = domain_re.sub('', tag['href'])

        # inject emoji
        def emoji_word(match):
            return match.group(0) + self.emoji
        word_re = re.compile(r'\b[a-zA-Zа-яА-ЯёЁ]{6}\b')
        for tag in soup(string=word_re):
            # I need to sure tag is NavigableString but not its subclass
            # pylint: disable=unidiomatic-typecheck
            if type(tag) == NavigableString and tag.parent.name not in ['script', 'style']:
                tag.replace_with(word_re.sub(emoji_word, tag))

        return soup.encode(encoding=encoding)


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
    Mirror(**vars(args)).start()
