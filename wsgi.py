""" Mirror wsgi application """
import logging
import os

from mirror import Mirror

logger = logging.getLogger('gunicorn.error')


class AppFactory:  # pylint: disable=too-few-public-methods
    """ Factory to generate new wsgi app for some `mirror` instance """
    def __init__(self, mirror: Mirror):
        self.mirror = mirror

    def __call__(self, env, start_response):
        logger.info("%s %s", env['REQUEST_METHOD'], env['PATH_INFO'])
        headers = {
            "user-agent": env['HTTP_USER_AGENT'],
            "accept-language": env['HTTP_ACCEPT_LANGUAGE'],
            "cookie": env['HTTP_COOKIE']
        }
        response = self.mirror.request_host(
            env['REQUEST_METHOD'],
            env['PATH_INFO'],
            headers=headers, data=env['wsgi.input']
        )
        logger.info('requested %s, status:%s', response.url, response.status_code)

        content = response.content
        content_type = response.headers.get('content-type', '')
        if 'text/html' in content_type:
            content = self.mirror.modify_html(content, encoding=response.encoding)
            logger.info('modified %s', response.url)

        # self.send(response.status_code, response.headers, content)
        client_headers = [('Content-Type', response.headers.get('content-type'))]
        set_cookie = response.headers.get('Set-Cookie', '')
        if set_cookie:
            client_headers.append(('Set-Cookie', set_cookie))
        start_response(f'{response.status_code} {response.reason}', client_headers)
        logger.info('sending %s to client', env['PATH_INFO'])
        yield content


def create_mirror_application():
    """ create an wsgi app for new `mirror` instance """
    host = os.environ.get('HOST', 'lifehacker.ru')
    emoji = os.environ.get('EMOJI', '')
    proto = os.environ.get('PROTO', 'https') + '://'
    return AppFactory(Mirror(emoji=emoji, host=host, proto=proto))


application = create_mirror_application()
