import unittest
from typing import Iterable, Callable, Generator

import requests

from server import Mirror


class MirrorEmojiTestCase(unittest.TestCase):
    def test_one_emoji(self):
        skull = '\U0001f480'
        mirror = Mirror(9000, 'https://', 'lifehacker.ru', skull)
        for i in range(5):
            self.assertEqual(mirror.emoji, skull)
            self.assertEqual(next(mirror._emoji_iterator), skull)

    def test_five_emoji(self):
        string = '\U0001f480\U0001f60d\U0001f9a5\U0001F453\u3299'
        mirror = Mirror(9000, 'https://', 'lifehacker.ru', string)
        for i in range(5):
            for char in string:
                self.assertEqual(mirror.emoji, char)


class MirrorGetHandlerTestCase(unittest.TestCase):
    def test_simple(self):
        from http.server import BaseHTTPRequestHandler

        mirror = Mirror(9000, 'https://', 'lifehacker.ru', "1")
        handler = mirror.get_handler()
        self.assertEqual(handler.__name__, 'Handler')
        self.assertEqual(handler.__base__, BaseHTTPRequestHandler)


class MirrorGetFromHostTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.mirror = Mirror(9000, 'https://', 'httpbin.org', '\U0001f480')

    def test_host_ignore(self):
        host = 'yandex.ru'
        headers = f'Host: {host}\n\n'
        try:
            response = self.mirror.get_from_host(path='/get', headers=headers)
        except requests.ConnectionError:
            raise unittest.SkipTest("connection error to httpbin.org")
        actual_headers = response.json().get('headers')
        self.assertNotEqual(actual_headers.get('Host'), host)

    def test_usage(self):
        accept = 'application/json'
        accept_language = 'en-US'
        headers = f'Accept: {accept}\nAccept-Language: {accept_language}\n\n'
        try:
            response = self.mirror.get_from_host(path='/get', headers=headers)
        except requests.ConnectionError:
            raise unittest.SkipTest("connection error to httpbin.org")
        actual_headers = response.json().get('headers')
        self.assertEqual(actual_headers.get('Accept'), accept)
        self.assertEqual(actual_headers.get('Accept-Language'), accept_language)


class MirrorModifyHTMLTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.emojis = '\U0001f480\U0001f60d\U0001f9a5\U0001F453\u3299'
        self.mirror = Mirror(9000, 'https://', 'ya.ru', self.emojis)
        self.emoji_iterator = Mirror.emoji_generator(emoji=self.emojis)

    def get_source(self, constructor: Callable[[str], bytes], items: Iterable[str]) -> bytes:
        return b''.join(constructor(s) for s in items)

    def assertModifiedHTML(self, source: bytes, expect: bytes, encoding: str = 'utf-8') -> None:
        result = self.mirror.modify_html(source, encoding)
        # 'assertIn' because of BeautifulSoup on return will populate html with <html>, <head>, ...
        self.assertIn(expect, result)

    def test_a_href_multiple_nested(self):
        # check if multiple a[href]s are overwritten
        def get_source(href1: str, href2: str) -> bytes:
            return f'<div><b><a href="{href1}"><p></p></a></b><a href="{href2}"></a></div>'.encode()

        self.assertModifiedHTML(
            get_source('ya.ru/12345', 'ya.ru/54321'),
            get_source('/12345', '/54321')
        )

    def test_a_href_host_links(self):
        # check if modify_html edit only links to "host". 'https://' and 'http://' will be deleted too
        def constructor(link: str) -> bytes:
            return f'<a href="{link}"></a>'.encode()

        def gen() -> Generator[str, None, None]:
            for addr, path in zip(
                    (proto+host for host in ['ya.ru', 'goo.gl'] for proto in ['', 'http://', 'https://']),
                    ['/qwe', '/asd', '/zxc', '/rty', '/fgh', '/vbn']):
                yield addr+path

        self.assertModifiedHTML(
            self.get_source(constructor, gen()),
            self.get_source(
                constructor,
                ['/qwe', '/asd', '/zxc', 'goo.gl/rty', 'http://goo.gl/fgh', 'https://goo.gl/vbn']
            )
        )

    def test_src_link_href(self):
        # check if [src] and link[href] elements edit their links (only for "host" for any protocol)
        def constructor(proto_host: str) -> bytes:
            return (
                f'<img src="{proto_host}/logo"/>'
                f'<script src="{proto_host}/script.js"></script>'
                f'<link href="{proto_host}/style.css"/>'
            ).encode()

        self.assertModifiedHTML(
            self.get_source(
                constructor,
                (proto + host for host in ['ya.ru', 'gmail.com'] for proto in ['', 'http://', 'https://'])
            ),
            self.get_source(constructor, ['', '', '', 'gmail.com', 'http://gmail.com', 'https://gmail.com'])
        )

    def test_host_dot_escape_in_re(self):
        def constructor(proto_host: str) -> bytes:
            return f'<a href="{proto_host}"></a><img src="{proto_host}"/><link href="{proto_host}"/>'.encode()

        self.assertModifiedHTML(
            self.get_source(constructor, ['ya.ru', 'yazru.ru']),
            self.get_source(constructor, ['', 'yazru.ru'])
        )

    def test_emoji_re(self):
        # '_' is part of word (end of word uses '\b' re)
        def e() -> str:
            return next(self.emoji_iterator)

        self.assertModifiedHTML(
            "aBcDeF АбВгДе-FцDЁёL.Йцуке qwerty_0 SevenCh пп3ппп=ЪьЮэЯЖ".encode(),
            f"aBcDeF{e()} АбВгДе{e()}-FцDЁёL{e()}.Йцуке qwerty_0 SevenCh пп3ппп=ЪьЮэЯЖ{e()}".encode(),
        )

    def test_emoji_only_in_text(self):
        def e() -> str:
            return next(self.emoji_iterator)

        self.assertModifiedHTML(
            b"qwerty<!-- qwerty -->qwerty",
            f'qwerty{e()}<!-- qwerty -->qwerty{e()}'.encode()
        )
        self.assertModifiedHTML(
            b"qwerty<style>a.qwerty{position: absolute}</style>forbes",
            f"qwerty{e()}<style>a.qwerty{{position: absolute}}</style>forbes{e()}".encode()
        )
        script = b'<script>const intvar = 5;</script>'
        self.assertModifiedHTML(script, script)


if __name__ == '__main__':
    unittest.main()
