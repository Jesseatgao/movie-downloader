from functools import reduce
import operator
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
from contextlib import contextmanager

import requests


ILLEGAL_FILENAME_CHARS = (' ', '#', '%', '&', '{', '}', '\\', '<', '>', '*', '?', '/', '$', '!', '\'', '"', ':', '@', '+', '`', '|', '=')


def normalize_filename(fn, repl='_'):
    norm = [c if c not in ILLEGAL_FILENAME_CHARS else repl for c in fn]

    return ''.join(norm)


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
