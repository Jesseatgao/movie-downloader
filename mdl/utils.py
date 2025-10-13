from functools import reduce
import operator
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
from contextlib import contextmanager
import time
import random
import sys

import configparser
import io
import re

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
    """build a CookieJar from key-value pairs.

     Args:
         key_values (str): The cookies must take the form of ``'cookie_key=cookie_value'``, with multiple pairs separated
                by whitespace and/or semicolon if applicable, e.g. ``'key1=val1 key2=val2; key3=val3'``.

    """
    if key_values:
        cookiejar = requests.cookies.RequestsCookieJar()
        kvps = [cookie for cookies in key_values.split(";") for cookie in cookies.split()]
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


class CommentConfigParser(configparser.ConfigParser):
    """Comment preserving ConfigParser.
    Limitation: No support for indenting section headers,
    comments and keys. They should have no leading whitespace.

    From:
     https://gist.github.com/Jip-Hop/d82781da424724b4018bdfc5a2f1318b
     https://stackoverflow.com/a/78042480
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Backup _comment_prefixes
        comment_prefixes = kwargs.get('comment_prefixes', ('#', ';')) or ()
        self._comment_prefixes_backup = comment_prefixes

        # Unset _comment_prefixes so comments won't be skipped
        assert sys.version_info.major == 3
        if sys.version_info.minor < 13:
            self._comment_prefixes = ()
        elif sys.version_info.minor == 13:
            self._prefixes.full = ()
        else:
            # Python 3.14+
            inline_comment_prefixes = kwargs.get('inline_comment_prefixes', None) or ()
            self._comments = configparser._CommentSpec((), inline_comment_prefixes)

        # Starting point for the comment IDs
        self._comment_id = 0
        # Default delimiter to use
        delimiter = self._delimiters[0]
        # Template to store comments as key value pair
        self._comment_template = "#{0} " + delimiter + " {1}"
        # Regex to match the comment prefix
        self._comment_regex = re.compile(r"^#\d+\s*" + re.escape(delimiter) + r"[^\S\n]*")
        # Regex to match cosmetic newlines (skips newlines in multiline values):
        # consecutive whitespace from start of line followed by a line not starting with whitespace
        self._cosmetic_newlines_regex = re.compile(r"^(\s+)(?=^\S)", re.MULTILINE)
        # List to store comments above the first section
        self._top_comments = []

    def _find_cosmetic_newlines(self, text):
        # Indices of the lines containing cosmetic newlines
        cosmetic_newline_indices = set()
        for match in re.finditer(self._cosmetic_newlines_regex, text):
            start_index = text.count("\n", 0, match.start())
            end_index = start_index + text.count("\n", match.start(), match.end())
            cosmetic_newline_indices.update(range(start_index, end_index))

        return cosmetic_newline_indices

    def _read(self, fp, fpname):
        lines = fp.readlines()
        cosmetic_newline_indices = self._find_cosmetic_newlines("".join(lines))

        above_first_section = True
        # Preprocess config file to preserve comments
        for i, line in enumerate(lines):
            if line.startswith("["):
                above_first_section = False
            elif above_first_section:
                # Remove this line for now
                lines[i] = ""
                self._top_comments.append(line)
            elif i in cosmetic_newline_indices or line.startswith(
                self._comment_prefixes_backup
            ):
                # Store cosmetic newline or comment with unique key
                lines[i] = self._comment_template.format(self._comment_id, line)
                self._comment_id += 1

        # Feed the preprocessed file to the original _read method
        return super()._read(io.StringIO("".join(lines)), fpname)

    def write(self, fp, space_around_delimiters=True):
        # Write the config to an in-memory file
        with io.StringIO() as sfile:
            super().write(sfile, space_around_delimiters)
            # Start from the beginning of sfile
            sfile.seek(0)
            lines = sfile.readlines()

        cosmetic_newline_indices = self._find_cosmetic_newlines("".join(lines))

        for i, line in enumerate(lines):
            if i in cosmetic_newline_indices:
                # Remove newlines added below each section by .write()
                lines[i] = ""
                continue
            # Remove the comment prefix (if regex matches)
            lines[i] = self._comment_regex.sub("", line, 1)

        fp.write("".join(self._top_comments + lines).rstrip())

    def clear(self):
        # Also clear the _top_comments
        self._top_comments = []
        super().clear()


class SpinWithBackoff:
    def __init__(self, start_secs=1, backoff_factor=1.5, max_secs=60):
        self.cur_secs = start_secs
        self.backoff_factor = backoff_factor
        self.max_secs = max_secs
        self.nth = 0

    def sleep(self):
        secs = self.cur_secs + random.random() * 0.5
        time.sleep(secs)
        self.cur_secs = min(self.cur_secs * self.backoff_factor, self.max_secs)
        self.nth += 1
