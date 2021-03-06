# -*- coding: utf-8 -*-
"""
Copyright (c) 2015 Civic Knowledge. This file is licensed under the terms of the
Revised BSD License, included in this distribution as LICENSE.txt
"""


from six import string_types, text_type, PY3
import os


class DelayedFlo(object):
    """Holds functions to open and close a file-like object"""

    def __init__(self, path, open_f, flo_f, close_f):
        self.path = path
        self.open_f = open_f
        self.flo_f = flo_f
        self.close_f = close_f
        self.memo = None
        self.message = None # Set externally for debugging

    def open(self, mode):
        self.memo = self.open_f(mode)
        return self.flo_f(self.memo)

    def close(self):
        if self.memo:
            self.close_f(self.memo)


def copy_file_or_flo(input_, output, buffer_size=64 * 1024, cb=None):
    """ Copy a file name or file-like-object to another file name or file-like object"""

    assert bool(input_)
    assert bool(output)

    input_opened = False
    output_opened = False

    try:
        if isinstance(input_, string_types):

            if not os.path.isdir(os.path.dirname(input_)):
                os.makedirs(os.path.dirname(input_))

            input_ = open(input_, 'r')
            input_opened = True

        if isinstance(output, string_types):

            if not os.path.isdir(os.path.dirname(output)):
                os.makedirs(os.path.dirname(output))

            output = open(output, 'wb')
            output_opened = True

        # shutil.copyfileobj(input_,  output, buffer_size)

        def copyfileobj(fsrc, fdst, length=buffer_size):
            cumulative = 0
            while True:
                buf = fsrc.read(length)
                if not buf:
                    break
                fdst.write(buf)
                if cb:
                    cumulative += len(buf)
                    cb(len(buf), cumulative)

        copyfileobj(input_, output)

    finally:
        if input_opened:
            input_.close()

        if output_opened:
            output.close()


def parse_url_to_dict(url, assume_localhost=False):
    """Parse a url and return a dict with keys for all of the parts.

    The urlparse function() returns a wacky combination of a namedtuple
    with properties.

    """
    from six.moves.urllib.parse import urlparse, urlsplit, urlunsplit, unquote_plus, ParseResult
    from six import text_type
    import re
    assert url is not None

    url = text_type(url)

    if re.match(r'^[a-zA-Z]:', url):
        url = path2url(url)

        p = urlparse(unquote_plus(url))

        # urlparse leaves a '/' before the drive letter.
        p = ParseResult(p.scheme, p.netloc, p.path.lstrip('/'), p.params, p.query, p.fragment)

    else:
        p = urlparse(url)

    #  '+' indicates that the scheme has a scheme extension
    if '+' in p.scheme:
        scheme_extension, scheme = p.scheme.split('+')
    else:
        scheme = p.scheme
        scheme_extension = None

    if scheme is '':
        scheme = 'file'


    return {
        'scheme': scheme,
        'scheme_extension': scheme_extension,
        'netloc': p.netloc,
        'hostname': p.hostname,
        'path': p.path,
        'params': p.params,
        'query': p.query,
        'fragment': unquote_plus(p.fragment) if p.fragment else None,
        'username': p.username,
        'password': p.password,
        'port': p.port
    }

def unparse_url_dict(d, **kwargs):

    from six.moves.urllib.parse import urlparse, urlsplit, urlunsplit, quote_plus

    d = dict(d.items())

    d.update(kwargs)


    if 'netloc' in d and d['netloc']:
        host_port = d['netloc']
    else:
        host_port = ''

    if 'port' in d and d['port']:
        host_port += ':' + text_type(d['port'])

    user_pass = ''
    if 'username' in d and d['username']:
        user_pass += d['username']

    if 'password' in d and d['password']:
        user_pass += ':' + d['password']

    if user_pass:
        host_port = '{}@{}'.format(user_pass, host_port)

    if d.get('scheme') and host_port:
        url = '{}://{}/{}'.format(d['scheme'],host_port, d.get('path', '').lstrip('/'))
    elif d.get('scheme') in ('mailto', 'file'):
        url = '{}:{}'.format(d['scheme'], d.get('path', ''))
    elif d.get('scheme'):
        url = '{}://{}'.format(d['scheme'], d.get('path', '').lstrip('/'))
    elif d.get('path'):
        # It's possible just a local file url.
        # This isn't the standard file: url form, which is specified to have a :// and a host part,
        # like 'file://localhost/etc/config', but that form can't handle relative URLs ( which don't start with '/')
        url = 'file:'+d['path'].lstrip('/')
    else:
        url = ''

    if d.get('scheme_extension'):
        url = d['scheme_extension']+'+'+url

    if 'query' in d and d['query']:
        url += '?' + d['query']

    if d.get('fragment'):
        url += '#' + quote_plus(d['fragment'])

    return url

def reparse_url(url, **kwargs):

    assume_localhost = kwargs.get('assume_localhost', False)

    return unparse_url_dict(parse_url_to_dict(url,assume_localhost),**kwargs)

def join_url_path(url, *paths):
    """Like path.os.join, but operates on the url path, ignoring the query and fragments."""

    parts = parse_url_to_dict(url)

    return reparse_url(url,path=os.path.join(parts['path'], *paths))



# From http://stackoverflow.com/a/2597440
class Bunch(object):
  def __init__(self, adict):
    self.__dict__.update(adict)



def get_cache(cache_name='rowgen'):
    """Return the path to a file cache"""

    from fs.osfs import OSFS
    from fs.appfs import UserDataFS
    import os

    env_var = (cache_name+'_cache').upper()

    cache_dir = os.getenv(env_var, None)

    if cache_dir:
        return OSFS(cache_dir)
    else:
        return UserDataFS(cache_name.lower())

def clean_cache(cache = None, cache_name='rowgen'):
    """Delete items in the cache older than 4 hours"""
    import datetime

    cache = cache if cache else get_cache(cache_name)

    for step in cache.walk.info():
        details = cache.getdetails(step[0])
        mod = details.modified
        now = datetime.datetime.now(tz=mod.tzinfo)
        age = (now - mod).total_seconds()
        if age > (60 * 60 * 4) and details.is_file:
            cache.remove(step[0])

def nuke_cache(cache = None, cache_name='rowgen'):
    """Delete Everythong in the cache"""
    from os.path import isfile

    cache = cache if cache else get_cache(cache_name)

    for step in cache.walk.info():
        if not step[1].is_dir:
            cache.remove(step[0])

# From http://stackoverflow.com/a/295466
def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.type(
    """
    import re
    import unicodedata
    from six import text_type
    value = text_type(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('utf8')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    value = re.sub(r'[-\s]+', '-', value)
    return value

def real_files_in_zf(zf):
    """Return a list of internal paths of real files in a zip file, based on the 'external_attr' values"""
    from os.path import basename

    for e in zf.infolist():

        if basename(e.filename).startswith('__') or basename(e.filename).startswith('.'):
            continue

        # I really don't understand external_attr, but no one else seems to either,
        # so we're just hacking here.
        # e.external_attr>>31&1 works when the archive has external attrs set, and a dir heirarchy
        # e.external_attr==0 works in cases where there are no external attrs set
        # e.external_attr==32 is true for some single-file archives.
        if bool(e.external_attr >> 31 & 1 or e.external_attr == 0 or e.external_attr == 32):
            yield e.filename

def flatten(d, sep='.'):
    """Flatten a data structure into tuples"""
    def _flatten(e, parent_key='', sep='.'):
        import collections

        prefix = parent_key+sep if parent_key else ''

        if isinstance(e, collections.MutableMapping):
            return tuple( (prefix+k2, v2) for k, v in e.items() for k2,v2 in _flatten(v,  k, sep ) )
        elif isinstance(e, collections.MutableSequence):
            return tuple( (prefix+k2, v2) for i, v in enumerate(e) for k2,v2 in _flatten(v,  str(i), sep ) )
        else:
            return (parent_key, (e,)),

    return tuple( (k, v[0]) for k, v in _flatten(d, '', sep) )

def fs_join(*args):
    """Like os.path.join, but never returns '\' chars"""
    from os.path import join
    return join(*args).replace('\\','/')

def path2url(path):
    "Convert a pathname to a file URL"
    try:
        # Python 3
        # http://stackoverflow.com/a/30702300
        from urllib.parse import urljoin
        from urllib.request import pathname2url
    except ImportError:
        # Python 2
        from urlparse import urljoin
        from urllib import pathname2url

    return urljoin('file:', pathname2url(path))