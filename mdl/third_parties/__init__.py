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
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-i686-win.zip',
                'ext': '.zip',
                'content-path': ['i686/'],
                'content-base': 'aria2c',
                'content-ext': '.exe'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-x86_64-win.zip',
                'ext': '.zip',
                'content-path': ['x86_64/'],
                'content-base': 'aria2c',
                'content-ext': '.exe'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-i686-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['i686/'],
                'content-base': 'aria2c',
                'content-ext': ''
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-x86_64-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['x86_64/'],
                'content-base': 'aria2c',
                'content-ext': ''
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'aria2c',
                'content-ext': ''
            },
            '64-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'aria2c',
                'content-ext': ''
            }
        }
    },
    'ffmpeg': {
        'Windows': {
            '32-bit': {
                'url': 'https://www.videohelp.com/download/ffmpeg-4.2.2-win32-static.zip',
                'ext': '.zip',
                'content-path': ['ffmpeg-4.2.2-win32-static/', 'bin/'],
                'content-base': 'ffmpeg',
                'content-ext': '.exe'
            },
            '64-bit': {
                'url': 'https://www.videohelp.com/download/ffmpeg-4.2.2-win64-static.zip',
                'ext': '.zip',
                'content-path': ['ffmpeg-4.2.2-win64-static/', 'bin/'],
                'content-base': 'ffmpeg',
                'content-ext': '.exe'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-i686-static.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['ffmpeg-4.2.2-i686-static/'],
                'content-base': 'ffmpeg',
                'content-ext': ''
            },
            '64-bit': {
                'url': 'https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-amd64-static.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['ffmpeg-4.2.2-amd64-static/'],
                'content-base': 'ffmpeg',
                'content-ext': ''
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'ffmpeg',
                'content-ext': ''
            },
            '64-bit': {
                'url': 'https://evermeet.cx/pub/ffmpeg/ffmpeg-4.2.2.zip',
                'ext': '.zip',
                'content-path': ['.'],
                'content-base': 'ffmpeg',
                'content-ext': ''
            }
        }
    },
    'mkvtoolnix': {
        'Windows': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-i686-win.zip',
                'ext': '.zip',
                'content-path': ['i686/'],
                'content-base': 'mkvmerge',
                'content-ext': '.exe'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-x86_64-win.zip',
                'ext': '.zip',
                'content-path': ['x86_64/'],
                'content-base': 'mkvmerge',
                'content-ext': '.exe'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-i686-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['i686/'],
                'content-base': 'mkvmerge',
                'content-ext': ''
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-x86_64-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['x86_64/'],
                'content-base': 'mkvmerge',
                'content-ext': ''
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'mkvmerge',
                'content-ext': ''
            },
            '64-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'mkvmerge',
                'content-ext': ''
            }
        }
    },
    'ckey': {
        'Windows': {
            '32-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm'
            },
            '64-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm'
            },
            '64-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm'
            }
        },
        'Darwin': {
            '32-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm'
            },
            '64-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm'
            }
        }
    },
    'node': {
        'Windows': {
            '32-bit': {
                'url': 'https://nodejs.org/dist/v16.15.0/node-v16.15.0-win-x86.zip',
                'ext': '.zip',
                'content-path': ['node-v16.15.0-win-x86/'],
                'content-base': 'node',
                'content-ext': '.exe'
            },
            '64-bit': {
                'url': 'https://nodejs.org/dist/v16.15.0/node-v16.15.0-win-x64.zip',
                'ext': '.zip',
                'content-path': ['node-v16.15.0-win-x64/'],
                'content-base': 'node',
                'content-ext': '.exe'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://unofficial-builds.nodejs.org/download/release/v16.15.0/node-v16.15.0-linux-x86.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['node-v16.15.0-linux-x86/'],
                'content-base': 'bin/node',
                'content-ext': ''
            },
            '64-bit': {
                'url': 'https://nodejs.org/dist/v16.15.0/node-v16.15.0-linux-x64.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['node-v16.15.0-linux-x64/'],
                'content-base': 'bin/node',
                'content-ext': ''
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': '',
                'content-ext': ''
            },
            '64-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': '',
                'content-ext': ''
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
                def is_within_directory(directory, target):
                    
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    
                    return prefix == abs_directory
                
                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                
                    tar.extractall(path, members, numeric_owner=numeric_owner) 
                    
                
                safe_extract(xz_prog, path=os.path.dirname(pkg))
        elif pkg.endswith('.wasm'):
            continue
        else:
            LOGGER.error("Unsupported compression package format: {!r}".format(pkg))
            sys.exit(-1)

        os.remove(pkg)


def finalize():
    tmp_progs_bin_path = [os.path.normpath(os.path.join(base, *progs_conf[prog][system][bitness]['content-path'])) for prog, base in zip(progs_name, progs_base_path)]
    tmp_progs_base_path = [os.path.normpath(os.path.join(base, progs_conf[prog][system][bitness]['content-path'][0])) for prog, base in zip(progs_name, progs_base_path)]

    for idx, src_path in enumerate(tmp_progs_bin_path):
        dst_path = progs_base_path[idx]
        if not os.path.samefile(src_path, dst_path):
            copy_tree(src_path, dst_path)

        src_base_path = tmp_progs_base_path[idx]
        if not os.path.samefile(src_base_path, dst_path):
            remove_tree(src_base_path)


def download_3rd_parties():
    args = arg_parser().parse_args()
    kwargs = vars(args)

    download(**kwargs)
    extract()
    finalize()


progs_full_path = [os.path.normpath(os.path.join(base, progs_conf[prog][system][bitness]['content-base'] + progs_conf[prog][system][bitness]['content-ext'])) for prog, base in zip(progs_name, progs_base_path)]


def exists_3rd_parties():
    return all(map(os.path.exists, progs_full_path))


# aria2c ffmpeg mkvmerge node
third_party_progs_default = [os.path.normpath(os.path.join(MOD_DIR, prog, progs_conf[prog][system][bitness]['content-base'])) for prog in ('aria2', 'ffmpeg', 'mkvtoolnix', 'node')]


if __name__ == '__main__':
    download_3rd_parties()
