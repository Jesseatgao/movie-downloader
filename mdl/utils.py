import time
import random
from functools import wraps, reduce
import operator
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import threading
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, wait

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests import Session
from clint.textui import progress


ILLEGAL_FILENAME_CHARS = (' ', '#', '%', '&', '{', '}', '\\', '<', '>', '*', '?', '/', '$', '!', '\'', '"', ':', '@', '+', '`', '|', '=')


def normalize_filename(fn, repl='_'):
    norm = [c if c not in ILLEGAL_FILENAME_CHARS else repl for c in fn]

    return ''.join(norm)


def retry(exceptions, tries=10, backoff_factor=0.1, logger=None):
    """
    Retry calling the decorated function using an exponential backoff.
    Ref: http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
         https://en.wikipedia.org/wiki/Exponential_backoff

    Args:
        exceptions: The exception to check. may be a tuple of
            exceptions to check.
        tries: Number of times to try before giving up.
        backoff_factor:
        logger: Logger to use. None to disable logging.
    """
    logger = logger or logging.getLogger()

    def deco_retry(f):
        NTRIES = 7

        @wraps(f)
        def f_retry(*args, **kwargs):
            ntries = 0
            while tries > ntries:
                try:
                    return f(*args, **kwargs)
                except exceptions as e:
                    ntries += 1
                    steps = random.randrange(1, 2**(ntries % NTRIES))
                    backoff = steps * backoff_factor

                    logger.warning('{!r}, Retrying {}/{} in {:.2f} seconds...'.format(e, ntries, tries, backoff))

                    time.sleep(backoff)

            try:
                return f(*args, **kwargs)
            except exceptions as e:
                logger.warning('{!s}, Having retried {} times, finally failed...'.format(e, ntries))

                raise e

        return f_retry  # true decorator

    return deco_retry


# class RequestsWrapper(object):
#     def __init__(self):
#         # super().__init__()
#         self._requester = requests_retry_session()
#
#         headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0',
#             #'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
#             'Accept-Encoding': 'gzip, identity, deflate, br, *'
#         }
#         self._requester.headers = headers
#
#     @retry(requests.RequestException)
#     def get(self, url, params=None, timeout=3.5, verify=True, **kwargs):
#         return self._requester.get(url, params=params, timeout=timeout, verify=verify, **kwargs)
#
#     @retry(requests.RequestException)
#     def head(self, url, **kwargs):
#         return self._requester.head(url, **kwargs)


class RequestsSessionWrapper(Session):
    def __init__(self):
        super().__init__()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0',
            # 'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
            'Accept-Encoding': 'gzip, identity, deflate, br, *'
        }
        self.headers = headers

    @retry(requests.RequestException)
    def get(self, url, params=None, timeout=(3.2, 6), verify=True, **kwargs):
        return super().get(url, params=params, timeout=timeout, verify=verify, **kwargs)


def requests_retry_session(
        retries=7,
        backoff_factor=0.2,
        status_forcelist=(500, 502, 504),
        session=None,
):
    """
    Ref: https://www.peterbe.com/plog/best-practice-with-retries-with-requests

    """
    # session = session or requests.Session()
    session = session or RequestsSessionWrapper()

    max_retries = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=max_retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def json_path_get(nested_data, key_path, default=None):
    """Access the nested data via a key sequence

    Args:
        nested_data: Nested data (e.g. data loaded from JSON formatted string, a mix of dicts and lists)
            from which getting the key_path specified item
        key_path (list or tuple): List of strings for DICTIONARY keys and integers for LIST indices
        default: Default return value if the result is None

    Returns:

    Examples:
        nested = {'A0': 'a0',
                  'B0': {'B10': 'b10', 'B11': 'b11', 'B12': {'B20': 'b20'}},
                  'C0': [{'C100': 'c100', 'C101': 'c101'}, {'C110': 'c110'}]
                  }
        json_path_get(nested, ['B0', 'B12'])
        json_path_get(nested, ['C0', 0, 'C100'], '')

    """
    def _get_item(obj, key):
        try:
            return operator.getitem(obj, key)
        except (AttributeError, TypeError, KeyError, IndexError):
            return None
        except Exception as e:
            raise e

    val = reduce(_get_item, key_path, nested_data)
    return val if val is not None else default


def build_cookiejar_from_kvp(key_values):
    """
    build a CookieJar from key-value pairs of the form "cookie_key=cookie_value cookie_key2=cookie_value2"

    """
    if key_values:
        cookiejar = requests.cookies.RequestsCookieJar()
        kvps = key_values.split()
        for kvp in kvps:
            key, value = kvp.split("=")
            cookiejar.set(key, value)

        return cookiejar


def build_logger(logger_name, log_file_name, logger_level=logging.DEBUG, console_level=logging.INFO, file_level=logging.DEBUG):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logger_level)

    #ch = logging.StreamHandler(stream=sys.stdout)
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    cf = logging.Formatter('%(message)s')
    ch.setFormatter(cf)

    fh = RotatingFileHandler(log_file_name, mode='a', maxBytes=1024*1024*2, backupCount=1)
    fh.setLevel(file_level)
    ff = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - \n%(message)s')
    fh.setFormatter(ff)

    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger


def change_logging_level(logger_name, logger_level=None, console_level=None, file_level=None):
    logger = logging.getLogger(logger_name)

    if logger_level is not None:
        logger.setLevel(logger_level)

    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and console_level is not None:
            handler.setLevel(console_level)
        elif isinstance(handler, logging.FileHandler) and file_level is not None:
            handler.setLevel(file_level)


@contextmanager
def logging_with_pipe(logger, level, text=False, encoding='utf-8'):
    """
    From:
     https://codereview.stackexchange.com/questions/6567/redirecting-subprocesses-output-stdout-and-stderr-to-the-logging-module

    """
    fd_read, fd_write = os.pipe()

    def run():
        with os.fdopen(fd_read, mode='rb') as readp:
            for line in iter(readp.readline, b''):
                if not line.isspace():
                    logger.log(level, line.decode(encoding))

    def run_text():
        with os.fdopen(fd_read, mode='r', encoding=encoding) as readp:
            for line in iter(readp.readline, ''):
                if not line.isspace():
                    logger.log(level, line)

    if text:
        threading.Thread(target=run_text).start()
    else:
        threading.Thread(target=run).start()

    try:
        yield fd_write
    finally:
        os.close(fd_write)


class LogPipe(threading.Thread):
    """
        From:
         https://codereview.stackexchange.com/questions/6567/redirecting-subprocesses-output-stdout-and-stderr-to-the-logging-module

    """
    def __init__(self, logger, level, text=False, encoding='utf-8'):
        """Setup the object with a logger and a loglevel
        and start the thread
        """
        super().__init__()
        self.daemon = False
        self.logger = logger
        self.text = text
        self.encoding = encoding
        self.level = level
        self.fdRead, self.fdWrite = os.pipe()
        mode = 'r' if self.text else 'rb'
        self.pipeReader = os.fdopen(self.fdRead, mode=mode)
        self.start()

    def fileno(self):
        """Return the write file descriptor of the pipe
        """
        return self.fdWrite

    def run(self):
        """Run the thread, logging everything.
        """
        sentinel = '' if self.text else b''
        for line in iter(self.pipeReader.readline, sentinel):
            if not self.text:
                self.logger.log(self.level, line.decode(self.encoding))
            else:
                self.logger.log(self.level, line)

        self.pipeReader.close()

    def close(self):
        """Close the write end of the pipe.
        """
        os.close(self.fdWrite)


class MillProgress(object):
    """
    Print a mill while progressing.
    Source: grabbed from `clint.textui.progress`, adding support for unknown `expected_size`.
    Source_URL: https://github.com/kennethreitz-archive/clint/blob/master/clint/textui/progress.py
    """
    STREAM = sys.stderr
    MILL_TEMPLATE = '{}  {}  {:10,d}/{:<10,d} elapsed: {}\r'
    MILL_CHARS = ['|', '/', '-', '\\']  # '+', 'x'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.done()
        return False

    def __init__(self, label='', hide=None, expected_size=None, every=1):
        self.label = label
        self.hide = hide
        # Only show bar in terminals by default (better for piping, logging etc.)
        if hide is None:
            try:
                self.hide = not self.STREAM.isatty()
            except AttributeError:  # output does not support isatty()
                self.hide = True
        self.expected_size = expected_size or 0
        self.every = every
        self.last_progress = 0
        self.delta_progress = 0
        self.every_progress = 0
        self.start = time.time()
        self.elapsed = 0

        self.show(0)

    def format_time(self, seconds):
        return time.strftime('%H:%M:%S', time.gmtime(seconds))

    def mill_char(self, progress):
        # if self.expected_size and progress >= self.expected_size:
        #     return ' '
        # else:
        #     return self.MILL_CHARS[(progress // self.every) % len(self.MILL_CHARS)]
        return self.MILL_CHARS[(progress // self.every) % len(self.MILL_CHARS)]

    def show(self, progress, count=None):
        if count is not None:
            self.expected_size = count

        self.last_progress = progress
        self.elapsed = time.time() - self.start
        elapsed = self.format_time(self.elapsed)

        if not self.hide:
            #if ((progress % self.every) == 0 or  # True every "every" updates
            if ((progress % self.every) == 0 or (progress - self.delta_progress) // self.every >= 1 or  # True every "every" updates
                    (self.expected_size and progress == self.expected_size)):  # And when we're done

                # self.STREAM.write(self.MILL_TEMPLATE % (
                #     self.label, self.mill_char(progress), str(progress), expected, elapsed))
                self.STREAM.write(self.MILL_TEMPLATE.format(
                    self.label, self.mill_char(self.every_progress), progress, self.expected_size, elapsed))
                self.STREAM.flush()

                self.delta_progress = progress
                self.every_progress += self.every

    def done(self):
        self.elapsed = time.time() - self.start
        elapsed = self.format_time(self.elapsed)

        if not self.hide:
            self.STREAM.write(self.MILL_TEMPLATE.format(
                self.label, ' ', self.last_progress, self.expected_size, elapsed))
            self.STREAM.write('\n')
            self.STREAM.flush()


class Aria2Cg(object):
    """
    ctx = {
        "total_size": 2000,  # total size of all the to-be-downloaded files, maybe inaccurate due to chunked transfer encoding
        "accurate": True,  # Is `total_size` accurate?
        "files":{
            "file1":{
                "length": 2000,  # 0 means 'unkown', i.e. file size can't be pre-determined through any one of provided URLs
                "resumable": True,
                "urls":{"url1":{"accept_ranges": "bytes", "refcnt": 2}, "url2":{"accept_ranges": "none", "refcnt": 0}},
                "ranges":{
                    "bytes=0-999": {
                        "start": 0,  # start byte position
                        "end": 999,  # end byte position, None for 'unkown', see above
                        "offset": 0,  # current pointer position relative to 'start'(i.e. 0)
                        "start_time": 0,
                        "rt_dl_speed": 0,  # x seconds interval
                       "future": future1,
                       "url": [url1]
                    },
                    "bytes=1000-1999": {
                        "start":1000,
                        "end":1999,
                        "offset": 0,  # current pointer position relative to 'start'(i.e. 1000)
                        "start_time": 0,
                        "rt_dl_speed": 0,  # x seconds interval
                        "future": future2,
                        "url": [url1]
                    }
                }
            },
            "file2":{
            }
        },
        "futures": {
            future1: {"file": "file1", "range": "bytes=0-999"},
            future2: {"file": "file1", "range": "bytes=1000-1999"}
        }
    }
    """
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __init__(self, max_workers=None, min_split_size=1024*1024, chunk_size=1024*10, proxy=None, logger=None, progress='bar'):
        self.requester = requests_retry_session()
        self.proxy = proxy or ''
        self.requester.proxies = dict(http=self.proxy, https=self.proxy)

        self.executor = ThreadPoolExecutor(max_workers)
        self.mgmnt_thread = None
        self.stop = False   # Flag signaling waiting threads to exit
        self._dl_ctx = {"total_size": 0, "accurate": True, "files": {}, "futures": {}}  # see CTX structure definition
        self._logger = logger or logging.getLogger()
        self.min_split_size = min_split_size
        self.chunk_size = chunk_size

        self.progress = progress
        if self.progress not in ('bar', 'mill'):
            self._logger.error("Error: invalid Aria2Cg progress parameter '{}',\
             default to 'bar' if possible, 'mill' otherwise".format(self.progress))
            self.progress = 'bar'

    @staticmethod
    def calc_req_ranges(req_len, split_size, req_start=0):
        ranges = []
        range_cnt = req_len // split_size
        for piece_id in range(range_cnt):
            start = req_start + piece_id * split_size
            end = start + split_size - 1
            ranges.append((start, end))

        # get the range of the last file piece
        if req_len % split_size:
            start = req_start + range_cnt * split_size
            end = req_start + req_len - 1
            ranges.append((start, end))

        return ranges

    @staticmethod
    def list_split(li, chunk_size=5):
        """Break the list `li` into chunks of size `chunk_size`"""
        for i in range(0, len(li), chunk_size):
            yield li[i:i+chunk_size]

    def _is_parallel_downloadable(self, path_name):
        ctx_file = self._dl_ctx['files'][path_name]
        parallel = True if ctx_file['length'] and ctx_file['resumable'] else False
        return parallel

    def _is_download_resumable(self, path_name):
        return True if self._dl_ctx['files'][path_name]['resumable'] else False

    def _get_remote_file_multipart(self, path_name, req_range):
        ctx_range = self._dl_ctx['files'][path_name]['ranges'][req_range]
        url = ctx_range['url'][0]

        # request start position and end position, maybe resuming from a previous failed request
        range_start, range_end = ctx_range['start'] + ctx_range['offset'], ctx_range['end']
        ranges = self.calc_req_ranges(range_end - range_start + 1, self.chunk_size, range_start)
        with open(path_name, mode='r+b') as fd:
            fd.seek(range_start)

            for start, end in ranges:
                req_range_new = "bytes={}-{}".format(start, end)
                headers = {"Range": req_range_new}
                try:
                    r = self.requester.get(url, headers=headers, allow_redirects=True)
                    # r.raise_for_status()
                    if r.status_code == requests.codes.partial:
                        fd.write(r.content)
                        ctx_range['offset'] += len(r.content)
                    else:
                        return -1
                except Exception as e:
                    self._logger.error("Error while downloading {}(range:{}-{}/{}-{}): '{}'".format(
                        os.path.basename(path_name), range_start, range_end, ctx_range['start'], ctx_range['end'], str(e)))
                    raise

    def _get_remote_file_singlepart(self, path_name, req_range):
        ctx_range = self._dl_ctx['files'][path_name]['ranges'][req_range]
        url = ctx_range['url'][0]

        max_tries = 10
        resume_no_support = False  # In case the server responses with no-support status against a range request
        with open(path_name, mode='r+b') as fd:
            for tr in range(max_tries):
                if self._is_download_resumable(path_name) and not resume_no_support:
                    # request start position and end position(which here we don't care about), maybe resuming from a previous failed request
                    range_start = ctx_range['start'] + ctx_range['offset']
                    req_range_new = "bytes={}-{}".format(range_start, '')
                    headers = {"Range": req_range_new}
                    status_code = requests.codes.partial
                else:
                    range_start = ctx_range['start']
                    headers = {}
                    status_code = requests.codes.ok

                fd.seek(range_start)

                try:
                    r = self.requester.get(url, headers=headers, allow_redirects=True, stream=True)
                    r.raise_for_status()
                    if r.status_code == status_code:  # in (requests.codes.ok, requests.codes.partial)
                        for chunk in r.iter_content(chunk_size=None):
                            fd.write(chunk)
                            ctx_range['offset'] += len(chunk)

                            if headers:
                                range_start = ctx_range['start'] + ctx_range['offset']
                                req_range_new = "bytes={}-{}".format(range_start, '')
                                headers['Range'] = req_range_new

                        break
                    else:
                        resume_no_support = True
                        self._logger.error("Unexpected status code: {}, which should have been {}. This may be caused by unsupported range request.".format(r.status_code, status_code))
                        if tr < max_tries - 1:
                            self._logger.error("Retrying {}/{}...".format(tr + 1, max_tries - 1))
                            time.sleep(0.1)
                except requests.RequestException as e:
                    ctx_file = self._dl_ctx['files'][path_name]
                    if ctx_file['length']:
                        range_end = file_end = ctx_file['length']
                    else:
                        range_end = file_end = ''

                    self._logger.error("Error while downloading {}(range:{}-{}/{}-{}): '{}'".format(
                        os.path.basename(path_name), range_start, range_end, ctx_range['start'], file_end, str(e)))
                    if tr < max_tries - 1:
                        self._logger.error("Retrying {}/{}...".format(tr + 1, max_tries - 1))
                        time.sleep(0.1)
            else:
                raise

    def _pick_file_url(self, path_name):
        """Select one URL from multiple sources according to max-connection-per-server etc
        """
        ctx_file = self._dl_ctx['files'][path_name]
        orig_urls = list(ctx_file['urls'].keys())
        range_urls = [url for url, ctx_url in ctx_file['urls'].items() if ctx_url['accept_ranges'] == 'bytes']
        if self._is_download_resumable(path_name):
            return range_urls
        else:
            return orig_urls

    def _build_ctx_internal(self, path_name, url):
        file_name = os.path.basename(path_name)
        urls = url.split(r'\t')  # "maybe '\t' separated URLs"
        ctx_file = self._dl_ctx['files'][path_name] = {}
        ctx_file['length'] = 0
        ctx_file['resumable'] = False
        ctx_file['urls'] = {}
        ctx_file['ranges'] = {}

        ranges = []

        for idx, url in enumerate(urls):
            ctx_url = ctx_file['urls'][url] = {}
            ctx_url['accept_ranges'] = "none"
            ctx_url['refcnt'] = 0

            r = self.requester.get(url, allow_redirects=True, stream=True)
            if r.status_code == requests.codes.ok:
                file_len = int(r.headers.get('Content-Length', 0))
                if file_len:
                    if not ctx_file['length']:
                        ctx_file['length'] = file_len
                    else:
                        if file_len != ctx_file['length']:
                            self._logger.warning("File sizes of '{}' from '{}' don't match!".format(
                                file_name, 'and'.join(urls[:idx+1])
                            ))

                accept_ranges = r.headers.get('Accept-Ranges')
                if accept_ranges and accept_ranges != "none":
                    ctx_url['accept_ranges'] = accept_ranges
                    assert accept_ranges == "bytes"

                    if not ctx_file['resumable']:
                        ctx_file['resumable'] = True
            else:
                self._logger.warning("Status code: {}. Error while trying to determine the size of {} using '{}'".format(
                    r.status_code, file_name, url
                ))

            r.close()

        self._dl_ctx['total_size'] += ctx_file['length']
        if not ctx_file['length']:
            self._dl_ctx['accurate'] = False

        # calculate request ranges
        if ctx_file['length'] and ctx_file['resumable']:  # rewrite as `self._is_parallel_downloadable` for clarity
            ranges = self.calc_req_ranges(ctx_file['length'], self.min_split_size, 0)
        else:
            ranges.append((0, None))

        for start, end in ranges:
            req_range = "bytes={}-{}".format(start, end)
            ctx_range = ctx_file['ranges'][req_range] = {}
            ctx_range.update({
                'start': start,
                'end': end,
                'offset': 0,
                'start_time': 0,
                'rt_dl_speed': 0,
                'url': self._pick_file_url(path_name)
            })

    def _build_ctx(self, path_urls):
        for path_name, urls in path_urls:
            if self._build_ctx_internal(path_name, urls):
                return -1

    def _submit_dl_tasks(self, path_urls):
        for path_name, _ in path_urls:
            if self._is_parallel_downloadable(path_name):
                tsk = self._get_remote_file_multipart
            else:
                tsk = self._get_remote_file_singlepart

            for req_range, ctx_range in self._dl_ctx["files"][path_name]["ranges"].items():
                future = self.executor.submit(tsk, path_name, req_range)
                ctx_range["future"] = future
                ctx_range["start_time"] = time.time()
                self._dl_ctx["futures"][future] = {
                    "file": path_name,
                    "range": req_range
                }

    def _create_empty_downloads(self, path_urls):
        try:
            for path_name, _ in path_urls:
                # check if 'path_name' refers to a valid FILE (perhaps prefixed with a path), not a directory
                head, tail = os.path.split(path_name)
                if not tail or os.path.isdir(path_name):
                    self._logger.error("'{}' is not a valid pathname. Please make sure it ends with a filename.".format(path_name))
                    return -1
                if head and not os.path.exists(head):
                    os.makedirs(head, exist_ok=True)

                with open(path_name, mode='w') as _:
                    pass
        except OSError as e:
            self._logger.error("OS error number {}: '{}'".format(e.errno, e.strerror))
            return -1

    def _is_all_done(self):
        return all(f.done() for f in self._dl_ctx['futures'])

    def _manage_tasks(self):
        total_size = self._dl_ctx['total_size']

        if self._dl_ctx['accurate']:
            if self.progress == 'bar':
                accurate_progress_bar = progress.Bar(expected_size=total_size)
            else:
                accurate_progress_bar = MillProgress(label='Downloaded/Expected:', expected_size=total_size, every=1024)
        else:
            inaccurate_progress_bar = MillProgress(label='Downloaded/Expected(inaccurate):', expected_size=total_size, every=1024)

        done = False
        while True:
            completed = 0
            for ctx_path_name in self._dl_ctx['files'].values():
                ctx_ranges = ctx_path_name.get('ranges')
                if ctx_ranges:
                    for ctx_range in ctx_ranges.values():
                        completed += ctx_range.get('offset', 0)

            progress_bar = accurate_progress_bar if self._dl_ctx['accurate'] else inaccurate_progress_bar

            if not done:
                progress_bar.show(completed, count=self._dl_ctx['total_size'])

            if not self._is_all_done():
                done = False
                time.sleep(0.1)
            else:
                done = True
                if not self.stop:
                    time.sleep(1)
                else:
                    progress_bar.done()
                    break

    def downloads(self, path_urls):
        """path_urls: [('path1', r'url1\turl2\turl3'),('path2', 'url4'),]
        """
        for chunk_path_urls in self.list_split(path_urls, chunk_size=2):
            if self._create_empty_downloads(chunk_path_urls) or self._build_ctx(chunk_path_urls):
                self._logger.error("Download file(s) failed.")
                sys.exit(-1)

            self._submit_dl_tasks(chunk_path_urls)

        #done, not_done = wait(self._dl_ctx["futures"].keys())

        if self.mgmnt_thread is None:
            self.mgmnt_thread = threading.Thread(target=self._manage_tasks)
            self.mgmnt_thread.start()

    def download(self, path_name, url):
        return self.downloads([(path_name, url)])

    def wait_for_all(self):
        while True:
            if not self._is_all_done():
                time.sleep(0.1)
            else:
                break

    def close(self):
        self.wait_for_all()
        self.executor.shutdown()

        self.stop = True
        self.mgmnt_thread.join()


if __name__ == '__main__':
    MOD_DIR = os.path.dirname(os.path.abspath(__file__))
    logger = build_logger('MDL', os.path.normpath(os.path.join(MOD_DIR, 'log/mdl.log')))

    file_urls = [("g:/tmp/ffmpeg-4.2.2-win64-static.zip", "https://ffmpeg.zeranoe.com/builds/win64/static/ffmpeg-4.2.2-win64-static.zip"),
                ("g:/tmp/mkvtoolnix-64-bit-46.0.0.7z", "https://www.videohelp.com/download/mkvtoolnix-64-bit-46.0.0.7z"),
                ("g:/tmp/aria2-x86_64-win.zip", "https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/release-1.35.0/aria2-x86_64-win.zip")
                ]

    with Aria2Cg(max_workers=20, progress='mill', proxy='http://127.0.0.1:8080') as aria2:
        # aria2.download("g:/tmp/test1.exe", "https://download.virtualbox.org/virtualbox/6.0.18/VirtualBox-6.0.18-136238-Win.exe")
        aria2.download("g:/tmp/test1.tar.gz", "https://www.videohelp.com/download/mkvtoolnix-64-bit-46.0.0.7z")
        #aria2.download("g:/tmp/test1.tar.xz", "https://mirrors.tuna.tsinghua.edu.cn/gnu/binutils/binutils-2.32.tar.xz")
        #aria2.downloads(file_urls)

    # aria2.close()