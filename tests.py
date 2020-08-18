""" Mirror unit tests """
import unittest
from typing import Iterable, Callable, Generator

from mirror import Mirror


class MirrorEmojiTestCase(unittest.TestCase):
    """ test emoji property """
    def test_one_emoji(self):
        """ test for one emoji in `mirror` """
        skull = '\U0001f480'
        mirror = Mirror('https://', 'lifehacker.ru', skull)
        for _ in range(5):
            self.assertEqual(mirror.emoji, skull)

    def test_five_emoji(self):
        """ test for several emoji in `mirror` """
        string = '\U0001f480\U0001f60d\U0001f9a5\U0001F453\u3299'
        mirror = Mirror('https://', 'lifehacker.ru', string)
        for _ in range(5):
            for char in string:
                self.assertEqual(mirror.emoji, char)

    def test_no_emoji(self):
        """ test for no emoji in `mirror` """
        mirror = Mirror('https://', 'ya.ru', '')
        for _ in range(5):
            self.assertEqual(mirror.emoji, '')


class MirrorModifyHTMLTestCase(unittest.TestCase):
    """ test Mirror's modify_html method """
    def setUp(self) -> None:
        self.emojis = '\U0001f480\U0001f60d\U0001f9a5\U0001F453\u3299'
        self.mirror = Mirror('https://', 'ya.ru', self.emojis)
        self.emoji_iterator = Mirror.emoji_generator(emoji=self.emojis)

    @staticmethod
    def get_source(constructor: Callable[[str], bytes], items: Iterable[str]) -> bytes:
        """ helper function to concatenate bytes in tests """
        return b''.join(constructor(s) for s in items)

    def assert_modified_html(self, source: bytes, expect: bytes, encoding: str = 'utf-8') -> None:
        """ helper function which call modify_html and check if it contains expected data """
        result = self.mirror.modify_html(source, encoding)
        # 'assertIn' because of BeautifulSoup on return will populate html with <html>, <head>, ...
        self.assertIn(expect, result)

    def test_a_href_multiple_nested(self):
        """ test if multiple "a" tags are found """
        # check if multiple a[href]s are overwritten
        def get_source(href1: str, href2: str) -> bytes:
            return f'<div><b><a href="{href1}"><p></p></a></b><a href="{href2}"></a></div>'.encode()

        self.assert_modified_html(
            get_source('ya.ru/12345', 'ya.ru/54321'),
            get_source('/12345', '/54321')
        )

    def test_a_href_host_links(self):
        """
        check if modify_html edit only links to "host". 'https://' and 'http://' will be deleted too
        """
        def constructor(link: str) -> bytes:
            return f'<a href="{link}"></a>'.encode()

        def gen() -> Generator[str, None, None]:
            for addr, path in zip(
                    (proto+host
                     for host in ['ya.ru', 'goo.gl']
                     for proto in ['', 'http://', 'https://']
                    ),
                    ['/qwe', '/asd', '/zxc', '/rty', '/fgh', '/vbn']):
                yield addr+path

        self.assert_modified_html(
            self.get_source(constructor, gen()),
            self.get_source(
                constructor,
                ['/qwe', '/asd', '/zxc', 'goo.gl/rty', 'http://goo.gl/fgh', 'https://goo.gl/vbn']
            )
        )

    def test_src_link_href(self):
        """
        check if [src] and link[href] elements edit their links (only for "host" for any protocol)
        """
        def constructor(proto_host: str) -> bytes:
            return (
                f'<img src="{proto_host}/logo"/>'
                f'<script src="{proto_host}/script.js"></script>'
                f'<link href="{proto_host}/style.css"/>'
            ).encode()

        self.assert_modified_html(
            self.get_source(
                constructor,
                (proto + host
                 for host in ['ya.ru', 'gmail.com']
                 for proto in ['', 'http://', 'https://']
                )
            ),
            self.get_source(
                constructor,
                ['', '', '', 'gmail.com', 'http://gmail.com', 'https://gmail.com']
            )
        )

    def test_host_dot_escape_in_re(self):
        """ ensure (dot) in host domain isn't (dot) in "re" """
        def constructor(proto_host: str) -> bytes:
            return (f'<a href="{proto_host}"></a>'
                    f'<img src="{proto_host}"/>'
                    f'<link href="{proto_host}"/>').encode()

        self.assert_modified_html(
            self.get_source(constructor, ['ya.ru', 'yazru.ru']),
            self.get_source(constructor, ['', 'yazru.ru'])
        )

    def test_emoji_re(self):
        """ check places where emoji actually inject """
        # '_' is part of word (end of word uses '\b' re)
        def e() -> str:  # pylint: disable=invalid-name
            return next(self.emoji_iterator)

        self.assert_modified_html(
            "aBcDeF АбВгДе-FцDЁёL.Йцуке qwerty_0 SevenCh пп3ппп=ЪьЮэЯЖ".encode(),
            (f"aBcDeF{e()} АбВгДе{e()}-FцDЁёL{e()}.Йцуке"
             f" qwerty_0 SevenCh пп3ппп=ЪьЮэЯЖ{e()}").encode(),
        )

    def test_emoji_only_in_text(self):
        """ be sure no emojis insert in comments, styles and scripts """
        def e() -> str:  # pylint: disable=invalid-name
            return next(self.emoji_iterator)

        self.assert_modified_html(
            b"qwerty<!-- qwerty -->qwerty",
            f'qwerty{e()}<!-- qwerty -->qwerty{e()}'.encode()
        )
        self.assert_modified_html(
            b"qwerty<style>a.qwerty{position: absolute}</style>forbes",
            f"qwerty{e()}<style>a.qwerty{{position: absolute}}</style>forbes{e()}".encode()
        )
        script = b'<script>const intvar = 5;</script>'
        self.assert_modified_html(script, script)


if __name__ == '__main__':
    unittest.main()
