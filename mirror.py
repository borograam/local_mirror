"""
Local mirror of some site with emoji injection after each 6-letter word.
"""
import re
from typing import Iterator

import requests
from bs4 import BeautifulSoup, NavigableString


class Mirror:
    """ Each object is independent and manages a separate server """
    def __init__(self, proto: str, host: str, emoji: str):
        self.proto = proto
        self.host = host

        self._emoji_iterator = Mirror.emoji_generator(emoji)

    @staticmethod
    def emoji_generator(emoji: str) -> Iterator[str]:
        """ returns infinite iterator of chars from `emoji` string """
        infinite = iter(int, 1)
        if not emoji:
            return ('' for _ in infinite)
        return (char for _ in infinite for char in emoji)

    @property
    def emoji(self):
        """ returns the next emoji """
        return next(self._emoji_iterator)

    def request_host(self, method, path, **kwargs):
        return requests.request(method, f'{self.proto}{self.host}{path}', **kwargs)

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
