import platform
import os
import sys
import logging

from argparse import ArgumentParser
import zipfile
import tarfile
from distutils.dir_util import copy_tree, remove_tree

from bdownload.download import BDownloader, BDownloaderException
from bdownload.cli import install_signal_handlers, ignore_termination_signals


MOD_DIR = os.path.dirname(os.path.abspath(__file__))
LOGGER = logging.getLogger('MDL.third_parties')

progs_conf = {
    'aria2': {
        'Windows': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux/aria2-i686-win.zip',
                'content-path': ['i686/'],
                'ext': '.zip'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux/aria2-x86_64-win.zip',
                'content-path': ['x86_64/'],
                'ext': '.zip'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux/aria2-i686-linux.tar.xz',
                'content-path': ['i686/'],
                'ext': '.tar.xz'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux/aria2-x86_64-linux.tar.xz',
                'content-path': ['x86_64/'],
                'ext': '.tar.xz'
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'content-path': ['.'],
                'ext': '.tar.xz'
            },
            '64-bit': {
                'url': '',  # FIXME
                'content-path': ['.'],
                'ext': '.tar.xz'
            }
        }
    },
    'ffmpeg': {
        'Windows': {
            '32-bit': {
                'url': 'https://archive.org/download/zeranoe/win32/static/ffmpeg-4.2.2-win32-static.zip'
                       '\thttps://www.videohelp.com/download/ffmpeg-4.2.2-win32-static.zip',
                'content-path': ['ffmpeg-4.2.2-win32-static/', 'bin/'],
                'ext': '.zip'
            },
            '64-bit': {
                'url': 'https://archive.org/download/zeranoe/win64/static/ffmpeg-4.2.2-win64-static.zip'
                       '\thttps://www.videohelp.com/download/ffmpeg-4.2.2-win64-static.zip',
                'content-path': ['ffmpeg-4.2.2-win64-static/', 'bin/'],
                'ext': '.zip'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-i686-static.tar.xz',
                'content-path': ['ffmpeg-4.2.2-i686-static/'],
                'ext': '.tar.xz'
            },
            '64-bit': {
                'url': 'https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-amd64-static.tar.xz',
                'content-path': ['ffmpeg-4.2.2-amd64-static/'],
                'ext': '.tar.xz'
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'content-path': ['.'],
                'ext': '.tar.xz'
            },
            '64-bit': {
                'url': 'https://evermeet.cx/pub/ffmpeg/ffmpeg-4.2.2.zip',
                'content-path': ['.'],
                'ext': '.zip'
            }
        }
    },
    'mkvtoolnix': {
        'Windows': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v47.0.0-mingw-w64-win32v1.0/mkvtoolnix-i686-win.zip',
                'content-path': ['i686/'],
                'ext': '.zip'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v47.0.0-mingw-w64-win32v1.0/mkvtoolnix-x86_64-win.zip',
                'content-path': ['x86_64/'],
                'ext': '.zip'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v47.0.0-mingw-w64-win32v1.0/mkvtoolnix-i686-linux.tar.xz',
                'content-path': ['i686/'],
                'ext': '.tar.xz'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v47.0.0-mingw-w64-win32v1.0/mkvtoolnix-x86_64-linux.tar.xz',
                'content-path': ['x86_64/'],
                'ext': '.tar.xz'
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'content-path': ['.'],
                'ext': '.tar.xz'
            },
            '64-bit': {
                'url': '',  # FIXME
                'content-path': ['.'],
                'ext': '.tar.xz'
            }
        }
    }
}


def arg_parser():
    parser = ArgumentParser()

    parser.add_argument('-p', '--proxy', dest='proxy', help='Proxy of the form "http://[user:pass@]host:port" or "socks5://[user:pass@]host:port" ')

    return parser


def determine_target():

    system = platform.system()
    machine = platform.machine()

    if system == 'Windows':
        if 'PROGRAMFILES(X86)' in os.environ:
            bitness = '64-bit'
        else:
            bitness = '32-bit'
    elif system in ('Linux', 'Darwin'):
        if machine.endswith('64'):
            bitness = '64-bit'
        else:
            bitness = '32-bit'
    else:
        LOGGER.error('Not supported platform: {}'.format(system))
        sys.exit(-1)

    return system, bitness


system, bitness = determine_target()

progs_name = [prog for prog in progs_conf]
progs_base_path = [os.path.join(MOD_DIR, prog) for prog in progs_name]
pkgs_full_path = [os.path.join(base, prog + progs_conf[prog][system][bitness]['ext']) for prog, base in zip(progs_name, progs_base_path)]


def download(**kwargs):
    urls = [progs_conf[prog][system][bitness]['url'] for prog in progs_name]
    pkgs_urls = list(zip(pkgs_full_path, urls))

    ignore_termination_signals()
    downloader = BDownloader(referrer='*', **kwargs)
    install_signal_handlers(downloader)

    try:
        downloader.downloads(pkgs_urls)
    except BDownloaderException as e:
        LOGGER.error(str(e))

    downloader.wait_for_all()
    downloader.close()

    succeeded, failed = downloader.results()
    if succeeded:
        LOGGER.info('Succeeded in downloading: {!r}'.format(succeeded))
    if failed:
        LOGGER.error('Failed to download: {!r}'.format(failed))

    result = downloader.result()
    if not result:
        LOGGER.info("Downloading 3rd-party files has succeeded.")
    else:
        LOGGER.error("Downloading 3rd-party files has failed.")
        sys.exit(result)


def extract():
    for pkg in pkgs_full_path:
        if pkg.endswith('.zip'):
            with zipfile.ZipFile(pkg) as zip_prog:
                zip_prog.extractall(path=os.path.dirname(pkg))
        elif pkg.endswith('.tar.xz'):
            with tarfile.open(name=pkg, mode='r:xz') as xz_prog:
                xz_prog.extractall(path=os.path.dirname(pkg))
        else:
            LOGGER.error("Unsupported compression package format: {!r}".format(pkg))
            sys.exit(-1)

        os.remove(pkg)


def finalize():
    tmp_progs_bin_path = [os.path.normpath(os.path.join(base, *progs_conf[prog][system][bitness]['content-path'])) for prog, base in zip(progs_name, progs_base_path)]
    tmp_progs_base_path = [os.path.normpath(os.path.join(base, progs_conf[prog][system][bitness]['content-path'][0])) for prog, base in zip(progs_name, progs_base_path)]

    for idx, src_path in enumerate(tmp_progs_bin_path):
        dst_path = progs_base_path[idx]
        copy_tree(src_path, dst_path)

        src_base_path = tmp_progs_base_path[idx]
        if src_base_path != dst_path:
            remove_tree(src_base_path)


def download_3rd_parties():
    args = arg_parser().parse_args()
    kwargs = vars(args)

    download(**kwargs)
    extract()
    finalize()


if __name__ == '__main__':
    download_3rd_parties()
