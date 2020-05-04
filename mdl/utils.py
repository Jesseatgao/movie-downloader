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


def requests_retry_session(
        retries=7,
        backoff_factor=0.2,
        status_forcelist=(500, 502, 504),
        session=None,
):
    """
    Ref: https://www.peterbe.com/plog/best-practice-with-retries-with-requests

    """
    session = session or requests.Session()
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


def retry(exceptions, tries=10, backoff_factor=0.1, logger=logging.getLogger()):
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

                    if logger:
                        logger.warning('{!r}, Retrying {}/{} in {:.2f} seconds...'.format(e, ntries, tries, backoff))

                    time.sleep(backoff)

            try:
                return f(*args, **kwargs)
            except exceptions as e:
                if logger:
                    logger.warning('{!s}, Having retried {} times, finally failed...'.format(e, ntries))

                raise e  # sys.exit(-1)

        return f_retry  # true decorator

    return deco_retry


class RequestsWrapper(object):
    def __init__(self):
        # super().__init__()
        self._requester = requests_retry_session()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0',
            #'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
            'Accept-Encoding': 'gzip, identity, deflate, br, *'
        }
        self._requester.headers = headers

    @retry(requests.exceptions.RequestException)
    def get(self, url, params=None, timeout=3.5, verify=True, **kwargs):
        return self._requester.get(url, params=params, timeout=timeout, verify=verify, **kwargs)

    @retry(requests.exceptions.RequestException)
    def head(self, url, **kwargs):
        return self._requester.head(url, **kwargs)


class RequestsSessionWrapper(Session):
    def __init__(self):
        super().__init__()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0',
            # 'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
            'Accept-Encoding': 'gzip, identity, deflate, br, *'
        }
        self.headers = headers

    @retry(requests.exceptions.RequestException)
    def get(self, url, params=None, timeout=3.5, verify=True, **kwargs):
        return super().get(url, params=params, timeout=timeout, verify=verify, **kwargs)


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

    ch = logging.StreamHandler(stream=sys.stdout)
    #ch.flush = sys.stdout.flush
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


class Aria2Cg(object):
    """
    ctx = {
        "total_size": 2000,  # total size of all the to-be-downloaded files, maybe inaccurate due to chunked transfer encoding
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
    def __init__(self, max_workers=None, min_split_size=1024*1024, chunk_size=10240):
        self.requester = RequestsWrapper()
        self.executor = ThreadPoolExecutor(max_workers)
        self._dl_ctx = {"total_size": 0, "files": {}, "futures": {}}  # see CTX structure definition
        logger_name = '.'.join(['MDL', 'Aria2Cg'])
        self._logger = logging.getLogger(logger_name)
        self.min_split_size = min_split_size
        self.chunk_size = chunk_size

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

        with open(path_name, mode='r+b') as fd:
            if self._is_download_resumable(path_name):
                # request start position and end position(which here we don't care about), maybe resuming from a previous failed request
                range_start = ctx_range['start'] + ctx_range['offset']
                req_range_new = "bytes={}-{}".format(range_start, '')
                headers = {"Range": req_range_new}
            else:
                range_start = ctx_range['start']
                headers = {}

            fd.seek(range_start)

            try:
                timeout = (3.1, 3.1)
                r = self.requester.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
                #r.raise_for_status()
                if r.status_code in (requests.codes.ok, requests.codes.partial):
                    for chunk in r.iter_content(chunk_size=None):
                        fd.write(chunk)
                        ctx_range['offset'] += len(chunk)

                        if headers:
                            range_start = ctx_range['start'] + ctx_range['offset']
                            req_range_new = "bytes={}-{}".format(range_start, '')
                            headers['Range'] = req_range_new
                else:
                    self._logger.error("Status code: {}".format(r.status_code))

            except Exception as e:
                ctx_file = self._dl_ctx['files'][path_name]
                if ctx_file['length']:
                    range_end = file_end = ctx_file['length']
                else:
                    range_end = file_end = ''

                self._logger.error("Error while downloading {}(range:{}-{}/{}-{}): '{}'".format(
                    os.path.basename(path_name), range_start, range_end, ctx_range['start'], file_end,
                    str(e)))
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

    def _submit_dl_tasks(self):
        for path_name in self._dl_ctx["files"]:
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

    def _manage_tasks(self):
        total_size = self._dl_ctx['total_size']
        bar = progress.Bar(expected_size=total_size)

        while True:
            completed = 0
            for ctx_path_name in self._dl_ctx['files'].values():
                for ctx_range in ctx_path_name['ranges'].values():
                    completed += ctx_range['offset']

            bar.show(completed)

            if all(f.done() for f in self._dl_ctx['futures']):
                break

            time.sleep(0.1)

        bar.done()

    def downloads(self, path_urls):
        """path_urls: [('path1', r'url1\turl2\turl3'),('path2', 'url4'),]
        """
        if self._create_empty_downloads(path_urls) or self._build_ctx(path_urls):
            self._logger.error("Download file(s) failed.")
            return -1

        self._submit_dl_tasks()

        #done, not_done = wait(self._dl_ctx["futures"].keys())

        mgmnt_thread = threading.Thread(target=self._manage_tasks)
        mgmnt_thread.start()
        mgmnt_thread.join()

    def download(self, path_name, url):
        return self.downloads([(path_name, url)])

    ## ContextManager
    def close(self):
        self.executor.shutdown()


if __name__ == '__main__':
    MOD_DIR = os.path.dirname(os.path.abspath(__file__))
    logger = build_logger('MDL', os.path.normpath(os.path.join(MOD_DIR, 'log/mdl.log')))

    aria2 = Aria2Cg(max_workers=10)
    #aria2.download("g:/tmp/test1.exe", "https://download.virtualbox.org/virtualbox/6.0.18/VirtualBox-6.0.18-136238-Win.exe")
    #aria2.download("g:/tmp/test1.tar.gz", "https://github.com/aria2/aria2/archive/release-1.35.0.tar.gz")
    #aria2.download("g:/tmp/test1.tar.gz", "http://117.128.6.11/cache/download.cpuid.com/cpu-z/cpu-z_1.91-en.zip?ich_args2=468-09144517038142_81f32f2247db3ae7e8963d8a4efff09a_10001002_9c896c2fd0c0f7d29533518939a83798_b98418dd38a074b80b0874faf12173e2")
    aria2.download("g:/tmp/test1.tar.xz", "https://mirrors.tuna.tsinghua.edu.cn/gnu/binutils/binutils-2.32.tar.xz")

    aria2.close()