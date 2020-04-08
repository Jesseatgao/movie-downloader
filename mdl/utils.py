import time
import random
from functools import wraps, reduce
import operator
import logging
from sys import stdout

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests import Session


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
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def retry(exceptions, tries=10, backoff_factor=0.1, logger=print):
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
                    steps = random.randrange(0, 2**(ntries % NTRIES))
                    backoff = steps * backoff_factor

                    if logger:
                        logger('{!r}, Retrying {}/{} in {:.2f} seconds...'.format(e, ntries, tries, backoff))

                    time.sleep(backoff)

            try:
                return f(*args, **kwargs)
            except exceptions as e:
                if logger:
                    logger('{!s}, Having retried {} times, finally failed...'.format(e, ntries))

                raise e  # sys.exit(-1)

        return f_retry  # true decorator

    return deco_retry


class RequestsWrapper(object):
    def __init__(self):
        self._requester = requests_retry_session()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0',
            #'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
            'Accept-Encoding': 'gzip, identity, deflate, br, *'
        }
        self._requester.headers = headers

    @retry(Exception)
    def get(self, url, params=None, timeout=3.5, verify=True, **kwargs):
        return self._requester.get(url, params=params, timeout=timeout, verify=verify, **kwargs)


class RequestsSessionWrapper(Session):
    def __init__(self):
        super().__init__()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0',
            # 'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
            'Accept-Encoding': 'gzip, identity, deflate, br, *'
        }
        self.headers = headers

    @retry(Exception)
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

    ch = logging.StreamHandler(stream=stdout)
    ch.setLevel(console_level)
    cf = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(cf)

    fh = logging.FileHandler(log_file_name)
    fh.setLevel(file_level)
    ff = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
