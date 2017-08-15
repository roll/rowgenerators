# Copyright (c) 2016 Civic Knowledge. This file is licensed under the terms of the
# Revised BSD License, included in this distribution as LICENSE

"""Functions and classes for processing different kinds of URLs"""

from __future__ import print_function

from os.path import splitext, basename, dirname
from rowgenerators.util import fs_join as join
from rowgenerators.util import parse_url_to_dict, unparse_url_dict, reparse_url


def file_ext(v):
    """Split of the extension of a filename, without throwing an exception of there is no extension. Does not
    return the leading '.'
    :param v: """

    try:
        v = splitext(v)[1][1:]

        if v == '*':  # Not a file name, probably a fragment regex
            return None

        return v.lower() if v else None
    except IndexError:
        return None


def extract_proto(url):
    parts = parse_url_to_dict(url)

    return parts['scheme_extension'] if parts.get('scheme_extension') \
        else {'https': 'http', '': 'file'}.get(parts['scheme'], parts['scheme'])


def url_is_absolute(ref):
    u = Url(ref)

    if u.scheme in ('http', 'https'):
        return True


class Url(object):
    """Base class for URL Managers

    url: The input URL
    proto: The extension of the scheme (git+http://, etc), if there is one, otherwise the scheme.

    """

    reparse = True  # Can this URL be reparsed?

    archive_formats = ['zip']

    def __new__(cls, url, **kwargs):
        return super(Url, cls).__new__(get_handler(url, **kwargs))

    def __init__(self, url, **kwargs):

        assert 'is_archive' not in kwargs

        self._extract_parts(url, kwargs)

        self._assign_args(kwargs)

        self._process()

    def _extract_parts(self, url, kwargs):
        self.url = reparse_url(url)
        self.parts = self.url_parts(self.url, **kwargs)

    def _assign_args(self, kwargs):
        self.scheme = kwargs.get('scheme', self.parts.scheme)
        self.proto = kwargs.get('proto')
        self.resource_url = kwargs.get('resource_url')
        self.resource_file = kwargs.get('resource_file')
        self.resource_format = kwargs.get('resource_format')
        self.target_file = kwargs.get('target_file')
        self.target_format = kwargs.get('target_format').lower() if kwargs.get('target_format') else kwargs.get(
            'target_format')
        self.encoding = kwargs.get('encoding')
        self.target_segment = kwargs.get('target_segment')

    def _process(self):
        self._process_proto()
        self._process_resource_url()
        self._process_fragment()
        self._process_target_file()

    def _process_proto(self):
        if not self.proto:
            self.proto = extract_proto(self.url)

    @property
    def is_archive(self):
        return self.resource_format in self.archive_formats

    # property
    def archive_file(self):
        # Return the name of the archive file, if there is one.
        return self.target_file if self.is_archive and self.resource_file != self.target_file else None

    def _process_fragment(self):

        if self.parts.fragment:
            target_file, self.target_segment = self.decompose_fragment(self.parts.fragment, self.is_archive)
        else:
            target_file = self.target_segment = None

        if not self.target_file and target_file:
            self.target_file = target_file

    def _process_resource_url(self):

        self.resource_url = unparse_url_dict(self.parts.__dict__,
                                             scheme=self.parts.scheme if self.parts.scheme else 'file',
                                             scheme_extension=False,
                                             fragment=False)

        self.resource_file = basename(reparse_url(self.resource_url, query=None))

        if not self.resource_format:
            self.resource_format = file_ext(self.resource_file)

    def _process_target_file(self):

        if not self.target_file:
            self.target_file = basename(reparse_url(self.resource_url, query=None))

        if not self.target_format:
            self.target_format = file_ext(self.target_file)

        if not self.target_format:
            self.target_format = self.resource_format

    @classmethod
    def decompose_fragment(cls, frag, is_archive):

        # noinspection PyUnresolvedReferences
        from six.moves.urllib.parse import unquote_plus

        frag_parts = unquote_plus(frag).split(';')

        file = segment = None

        # An archive file might have an inner Excel file, and that file can have
        # a segment.

        if is_archive and frag_parts:

            if len(frag_parts) == 2:
                file = frag_parts[0]
                segment = frag_parts[1]

            else:
                file = frag_parts[0]
        elif frag_parts:
            # If it isn't an archive, then the only possibility is a spreadsheet with an
            # inner segment
            segment = frag_parts[0]

        return file, segment

    @classmethod
    def url_parts(cls, url, **kwargs):
        from .util import Bunch
        """Return an object of url parts, possibly with updates from the kwargs"""
        parts = parse_url_to_dict(url)

        parts['resource_format'] = file_ext(parts['path'])

        parts.update(kwargs)

        return Bunch(parts)

    @classmethod
    def match(cls, url, **kwargs):
        """Return True if this handler can handle the input URL"""
        raise NotImplementedError

    @property
    def generator(self):
        """Return a suitable generator for this url"""
        raise NotImplementedError

    def component_url(self, s, scheme_extension=None):
        """
        :param s:
        :param scheme_extension:
        :return:
        """
        """
        :param s:
        :param scheme_extension:
        :return:
        """
        sp = parse_url_to_dict(s)

        # If there is a netloc, it's an absolute URL
        if sp['netloc']:
            return s

        url = reparse_url(s, path=join(dirname(self.parts.path), sp['path']),
                          fragment=sp['fragment'],
                          scheme_extension=scheme_extension or sp['scheme_extension'])

        assert url
        return url

    def abspath(self, s):

        sp = parse_url_to_dict(s)

        if sp['netloc']:
            return s

        url = reparse_url(self.url, path=join(dirname(self.parts.path), sp['path']), fragment=sp['fragment'])

        assert url
        return url

    def prefix_path(self, base):
        """Prefix the path with a base, if the path is relative"""

        url = reparse_url(self.url, path=join(base, self.parts.path))

        assert url
        return url

    def path(self, base=''):
        """Prefix the path with a base, if the path is relative, then return only the path element"""

        url = reparse_url(self.url, path=join(base, self.parts.path))

        return Url(url).parts.path

    def dirname(self):
        """Return the dirname of the path"""
        return reparse_url(self.url, path=dirname(self.parts.path))


    def update(self, **kwargs):
        """Returns a new Url object, possibly with some of the paroperties replaced"""

        o = Url(
            self.rebuild_url(target_file=kwargs.get('target_file', self.target_file),
                             target_segment=kwargs.get('target_segment', self.target_segment)),
            scheme=kwargs.get('scheme', self.scheme),
            proto=kwargs.get('proto', self.proto),
            resource_url=kwargs.get('resource_url', self.resource_url),
            resource_file=kwargs.get('resource_file', self.resource_file),
            resource_format=kwargs.get('resource_format', self.resource_format),
            target_file=kwargs.get('target_file', self.target_file),
            target_format=kwargs.get('target_format', self.target_format),
            encoding=kwargs.get('encoding', self.encoding),
            target_segment=kwargs.get('target_segment', self.target_segment)
        )

        o._process_resource_url()
        o._process_fragment()
        o._process_target_file()

        return o

    def rebuild_url(self, target_file=None, target_segment=None, **kw):

        if target_file:
            tf = target_file
        elif target_file is False:
            tf = None
        else:
            tf = self.archive_file()

        if target_segment is False:
            ts = None
        elif target_segment or target_segment == 0:
            ts = target_segment

        else:
            ts = self.target_segment

        second_sep = ''

        parts = parse_url_to_dict(self.url)

        f = ''

        if tf:
            f = tf
            second_sep = ';'

        if ts or ts == 0:
            f += second_sep
            f += str(ts)

        parts['fragment'] = f

        for k, v in kw.items():
            if k in parts:
                if v == False:
                    del parts[k]
                else:
                    parts[k] = v

        return unparse_url_dict(parts)

    @property
    def dict(self):
        from operator import itemgetter

        keys = "url scheme proto resource_url resource_file resource_format target_file target_format " \
               "encoding target_segment"

        return dict((k, v) for k, v in self.__dict__.items() if k in keys)

    def __deepcopy__(self, o):
        d = self.__dict__.copy()
        del d['url']
        return type(self)(self.url, **d)

    def __copy__(self, o):
        return self.__deepcopy__(o)

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self.rebuild_url())


class GeneralUrl(Url):
    """Basic URL, with no special handling or protocols"""

    def __init__(self, url, **kwargs):
        super(GeneralUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return True

    def component_url(self, s):
        sp = parse_url_to_dict(s)

        if sp['netloc']:
            return s

        return reparse_url(self.url, path=join(dirname(self.parts.path), sp['path']), fragment=sp['fragment'])

    @property
    def auth_resource_url(self):
        """Return An S3: version of the url, with a resource_url format that will trigger boto auth"""

        # This is just assuming that the url was created as a resource from the S2Url, and
        # has the form 'https://s3.amazonaws.com/{bucket}/{key}'

        parts = parse_url_to_dict(self.resource_url)

        return 's3://{}'.format(parts['path'])


class WebPageUrl(Url):
    """A URL for webpages, not for data"""

    def __init__(self, url, **kwargs):
        super(GeneralUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return True

    def component_url(self, s):
        sp = parse_url_to_dict(s)

        if sp['netloc']:
            return s

        return reparse_url(self.url, path=join(dirname(self.parts.path), sp['path']))


class GoogleProtoCsvUrl(Url):
    """Access a Google spreadheet as a CSV format download"""

    csv_url_template = 'https://docs.google.com/spreadsheets/d/{key}/export?format=csv'

    def __init__(self, url, **kwargs):
        kwargs['resource_format'] = 'csv'
        kwargs['encoding'] = 'utf8'
        kwargs['proto'] = 'gs'
        super(GoogleProtoCsvUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return extract_proto(url) == 'gs'

    def _process_resource_url(self):

        self._process_fragment()

        # noinspection PyUnresolvedReferences
        self.resource_url = self.csv_url_template.format(
            key=self.parts.netloc)  # netloc is case-sensitive, hostname is forced lower.

        self.resource_file = self.parts.netloc

        if self.target_segment:
            self.resource_url += "&gid={}".format(self.target_segment)
            self.resource_file += '-' + self.target_segment

        self.resource_file += '.csv'

        if self.resource_format is None:
            self.resource_format = file_ext(self.resource_file)

        self.target_file = self.resource_file  # _process_target() file will use this self.target_file

    def component_url(self, s):

        sp = parse_url_to_dict(s)

        if sp['netloc']:
            return s

        return reparse_url(self.url, fragment=s)

        url = reparse_url(self.resource_url, query="format=csv&gid=" + s)
        assert url
        return url


class SocrataUrl(Url):
    def __init__(self, url, **kwargs):
        kwargs['resource_format'] = 'csv'
        kwargs['encoding'] = 'utf8'
        kwargs['proto'] = 'socrata'

        super(SocrataUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return extract_proto(url) == 'socrata'

    def _process_resource_url(self):
        self.resource_url = unparse_url_dict(self.parts.__dict__,
                                             scheme_extension=False,
                                             fragment=False,
                                             path=join(self.parts.path, 'rows.csv'))

        self.resource_file = basename(self.url) + '.csv'

        if self.resource_format is None:
            self.resource_format = file_ext(self.resource_file)

        self.target_file = self.resource_file  # _process_target() file will use this self.target_file


class CkanUrl(Url):
    def __init__(self, url, **kwargs):
        kwargs['proto'] = 'ckan'
        super(CkanUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return extract_proto(url) == 'ckan'


class ZipUrl(Url):
    def __init__(self, url, **kwargs):
        kwargs['resource_format'] = 'zip'
        super(ZipUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        parts = parse_url_to_dict(url)
        return file_ext(parts['path']) in ('zip',) or kwargs.get('force_archive')

    def _process_fragment(self):

        if self.parts.fragment:
            self.target_file, self.target_segment = self.decompose_fragment(self.parts.fragment, self.is_archive)

        else:
            self.target_file = self.target_segment = None

    def _process_target_file(self):

        # Handles the case of file.csv.zip, etc.
        for ext in ('csv', 'xls', 'xlsx'):
            if self.resource_file.endswith('.' + ext + '.zip'):
                self.target_file = self.resource_file.replace('.zip', '')

        if self.target_file and not self.target_format:
            self.target_format = file_ext(self.target_file)

    def component_url(self, s):

        if url_is_absolute(s):
            return s

        return reparse_url(self.url, fragment=s)


class ExcelUrl(Url):
    resource_format = None  # Must be xls or xlsx

    @classmethod
    def match(cls, url, **kwargs):
        parts = parse_url_to_dict(url)

        return file_ext(parts['path']) in ('xls', 'xlsx')

    def component_url(self, s):
        if url_is_absolute(s):
            return s

        return reparse_url(self.url, fragment=s)

    def rebuild_url(self, target_file=None, target_segment=None):
        ts = target_segment if (target_segment or target_segment == 0) else self.target_segment

        return reparse_url(self.url, fragment=ts)


class S3Url(Url):
    """Convert an S3 proto url into the public access form"""

    def __init__(self, url, **kwargs):
        # Save for auth_url()
        self._orig_url = url
        self._orig_kwargs = dict(kwargs.items())

        kwargs['proto'] = 's3'
        super(S3Url, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return extract_proto(url) == 's3'

    def _process_resource_url(self):
        url_template = 'https://s3.amazonaws.com/{bucket}/{key}'

        self._bucket_name = self.parts.netloc
        self._key = self.parts.path.strip('/')

        # noinspection PyUnresolvedReferences
        self.resource_url = url_template.format(bucket=self._bucket_name, key=self._key)

        self.resource_file = basename(self.resource_url)

        if self.resource_format is None:
            self.resource_format = file_ext(self.resource_file)

    @property
    def auth_resource_url(self):
        """Return the orginal S3: version of the url, with a resource_url format that will trigger boto auth"""
        return 's3://{bucket}/{key}'.format(bucket=self._bucket_name, key=self._key)

    def component_url(self, s, scheme_extension=None):
        sp = parse_url_to_dict(s)

        new_key = join(dirname(self.key), sp['path'])

        return 's3://{bucket}/{key}'.format(bucket=self._bucket_name.strip('/'), key=new_key.lstrip('/'))

    @property
    def bucket_name(self):
        return self._bucket_name

    @property
    def key(self):
        return self._key

    @property
    def object(self):
        """Return the boto object for this source"""
        import boto3

        s3 = boto3.resource('s3')

        return s3.Object(self.bucket_name, self.key)

    @property
    def signed_resource_url(self):
        import boto3

        s3 = boto3.client('s3')

        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': self.key
            }
        )

        return url


class MetatabPackageUrl(Url):
    """"""

    def __init__(self, url, **kwargs):
        kwargs['proto'] = 'metatab'
        super(MetatabPackageUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return extract_proto(url) == 'metatab'

    def _process_resource_url(self):

        # Reminder: this is the HTTP resource, not the Metatab resource
        self.resource_url = unparse_url_dict(self.parts.__dict__, scheme_extension=False, fragment=False)

        self.resource_format = file_ext(self.resource_url)

        if self.resource_format not in ('zip', 'xlsx', 'csv'):
            self.resource_format = 'csv'
            self.resource_file = 'metadata.csv'
            self.resource_url += '/metadata.csv'
        else:
            self.resource_file = basename(self.resource_url)

        if self.resource_format == 'xlsx':
            self.target_file = 'meta'
        elif self.resource_format == 'zip':
            self.target_file = 'metadata.csv'
        else:
            self.target_file = self.resource_file

        self.target_format = 'metatab'

    def component_url(self, s, scheme_extension=None):
        return super().component_url(s, scheme_extension)

    def _process_fragment(self):
        self.target_segment = self.parts.fragment


class ProgramUrl(Url):
    def __init__(self, url, **kwargs):
        kwargs['proto'] = 'program'

        super(ProgramUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return extract_proto(url) == 'program'

    def _extract_parts(self, url, kwargs):
        parts = self.url_parts(url, **kwargs)

        self.url = reparse_url(url, assume_localhost=True,
                               scheme=parts.scheme if parts.scheme != 'program' else 'file',
                               scheme_extension='program')

        self.parts = self.url_parts(self.url, **kwargs)

    @property
    def path(self):
        return self.parts.path

    def _process_resource_url(self):
        self.resource_url = unparse_url_dict(self.parts.__dict__,
                                             scheme=self.parts.scheme if self.parts.scheme else 'file',
                                             scheme_extension=False,
                                             fragment=False)

        self.resource_file = basename(self.resource_url)

        if not self.resource_format:
            self.resource_format = file_ext(self.resource_file)


class ApplicationUrl(GeneralUrl):
    """Application URLs have weirdo schemes or protos"""

    reparse = False

    def __init__(self, url, **kwargs):
        super(ApplicationUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return extract_proto(url) not in ['file', 'ftp', 'http', 'https']


class NotebootUrl(Url):
    """IPYthon Notebook URL"""

    def __init__(self, url, **kwargs):
        kwargs['proto'] = 'ipynb'

        super(NotebootUrl, self).__init__(url, **kwargs)

    @classmethod
    def match(cls, url, **kwargs):
        return extract_proto(url) == 'ipynb'

    def _extract_parts(self, url, kwargs):
        parts = self.url_parts(url, **kwargs)

        self.url = reparse_url(url, assume_localhost=True,
                               scheme=parts.scheme if parts.scheme != 'ipynb' else 'file',
                               scheme_extension='ipynb')

        self.parts = self.url_parts(self.url, **kwargs)

    @property
    def path(self):
        return self.parts.path

    def _process_resource_url(self):
        self.resource_url = unparse_url_dict(self.parts.__dict__,
                                             scheme=self.parts.scheme if self.parts.scheme != 'ipynb' else 'file',
                                             scheme_extension=False,
                                             fragment=False).strip('/')

        self.resource_file = basename(self.resource_url)

        if not self.resource_format:
            self.resource_format = file_ext(self.resource_file)

    def _process_fragment(self):
        self.target_segment = self.parts.fragment

    def _process_target_file(self):
        super(NotebootUrl, self)._process_target_file()

        assert self.target_format == 'ipynb', self.target_format


url_handlers = [
    NotebootUrl,
    ProgramUrl,
    MetatabPackageUrl,
    CkanUrl,
    SocrataUrl,
    GoogleProtoCsvUrl,
    ZipUrl,
    ExcelUrl,
    S3Url,
    ApplicationUrl,
    GeneralUrl
]


def get_handler(url, **kwargs):
    for handler in url_handlers:
        if handler.match(url, **kwargs):
            return handler

    return GeneralUrl
