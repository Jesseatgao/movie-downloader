import platform
import os
import sys
import logging
import hashlib

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
                'content-ext': '.exe',
                'sha512': '7cb8004479499703ae756d22ddef5159715a1524c86002515f9c893f009ea6c01a8263aedd6410f574c15e4a7b738879051f5611d8fbaa6e990c7d4f4ec90f8c'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-x86_64-win.zip',
                'ext': '.zip',
                'content-path': ['x86_64/'],
                'content-base': 'aria2c',
                'content-ext': '.exe',
                'sha512': 'ff10df7fb743e9f722b6146c622cb19b9728d8a78f00151e3c449e1fe2d87a43ab0c9cebc030cc1fd8a5276f710b8c687c62ea91be1f95954089ab4d9108eef2'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-i686-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['i686/'],
                'content-base': 'aria2c',
                'content-ext': '',
                'sha512': 'f4ff97ad84193d98d093c7217f446213e9fbc1ede60df4f6237bfcd88a33f80803c368cfb16cdfc8e275e63e7b1bf031db1153c4fba9ecbd7f3b514904c2a5f8'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.35.0-win-linux--builder-win32-v1.2/aria2-x86_64-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['x86_64/'],
                'content-base': 'aria2c',
                'content-ext': '',
                'sha512': 'd59b28893d05422f91f0a64d7d2df144c990a6b84fa1d867e763e460b1baf792289bde6eac83ddec4d85de33fb1958b2bc75b91cc90b57b879eeb25a0e1d91cc'
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'aria2c',
                'content-ext': '',
                'sha512': ''
            },
            '64-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'aria2c',
                'content-ext': '',
                'sha512': ''
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
                'content-ext': '.exe',
                'sha512': 'b384397b401c870041b21ae291f4e62e7030303057e4b6a81ed473b23613528ce4e5dcf10c4753e8321a17b78bac8c34de6c5e52ae8acf034718a2214aa669cb'
            },
            '64-bit': {
                'url': 'https://www.videohelp.com/download/ffmpeg-4.2.2-win64-static.zip',
                'ext': '.zip',
                'content-path': ['ffmpeg-4.2.2-win64-static/', 'bin/'],
                'content-base': 'ffmpeg',
                'content-ext': '.exe',
                'sha512': '53dac6f1f8c23777bd01aac585e991d1b44390e0195bb76b10980cfef2d85a2187fa8fea59b109eaa01407d3f94a8df0952b5b950f3ae26c3c40752c3a9c70bd'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-i686-static.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['ffmpeg-4.2.2-i686-static/'],
                'content-base': 'ffmpeg',
                'content-ext': '',
                'sha512': '9d92ef3bf8a3c19daa82835e7e039dc1ef228d41d7278c724beab4bc9c6ddf362382a7e351128d09951470262394b45262fa861e7f3e6039d0e8a073b5960aa8'
            },
            '64-bit': {
                'url': 'https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-4.2.2-amd64-static.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['ffmpeg-4.2.2-amd64-static/'],
                'content-base': 'ffmpeg',
                'content-ext': '',
                'sha512': 'a666230e1b6de563c6ab95f804c6ce7bb4599f6bbe738a2c69f74062d3a6f68c82aab5026de12b550292f0565598dc7d21b3e14f0ccb89786e3a36f1537378dc'
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'ffmpeg',
                'content-ext': '',
                'sha512': ''
            },
            '64-bit': {
                'url': '',
                'ext': '.zip',
                'content-path': ['.'],
                'content-base': 'ffmpeg',
                'content-ext': '',
                'sha512': ''
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
                'content-ext': '.exe',
                'sha512': '9d9398d095c60c80035229100d16f26acca71e419ddae7fd20b301c273c708a389872fd51fa995e8162b57b6068434d44482025b2fcc904fd8c76eb6e0c148b0'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-x86_64-win.zip',
                'ext': '.zip',
                'content-path': ['x86_64/'],
                'content-base': 'mkvmerge',
                'content-ext': '.exe',
                'sha512': 'bfe3bc0dd7be2e2e8f9034ad692bf8d922f8db6f4c04a7cba84ba305fd969beaa2afec8a3158836e1c14121a82a5d678969585dc3026298714f1dbaa365e5756'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-i686-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['i686/'],
                'content-base': 'mkvmerge',
                'content-ext': '',
                'sha512': '19b8442ced7bd44796d2f4bbc8ebdfa0ddf37662f29cdd600f4a06ac29c71d0b33c75f18cfd3243a851b292ac5ea5c30039d83c61571194450caf6e9a9596ce5'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.4/mkvtoolnix-x86_64-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['x86_64/'],
                'content-base': 'mkvmerge',
                'content-ext': '',
                'sha512': '6a31cd267a024bae9309e2bd6533b60c47010c3758549cf7a70db7ebafc30e5d6a3e681a01a7b1bb6b4a4c63413fc5ac210837d4bfdfd2e305cf62d26836fcaa'
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'mkvmerge',
                'content-ext': '',
                'sha512': ''
            },
            '64-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': 'mkvmerge',
                'content-ext': '',
                'sha512': ''
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
                'content-ext': '.wasm',
                'sha512': '3891da8d5080c981fe49fb553b8fe5f99e504fa2550c3a6fb353a18572dd12393234f210ff1d67b1fec48c87fc83a1f1ee7d817757e8406003beeac9218e5107'
            },
            '64-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm',
                'sha512': '3891da8d5080c981fe49fb553b8fe5f99e504fa2550c3a6fb353a18572dd12393234f210ff1d67b1fec48c87fc83a1f1ee7d817757e8406003beeac9218e5107'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm',
                'sha512': '3891da8d5080c981fe49fb553b8fe5f99e504fa2550c3a6fb353a18572dd12393234f210ff1d67b1fec48c87fc83a1f1ee7d817757e8406003beeac9218e5107'
            },
            '64-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm',
                'sha512': '3891da8d5080c981fe49fb553b8fe5f99e504fa2550c3a6fb353a18572dd12393234f210ff1d67b1fec48c87fc83a1f1ee7d817757e8406003beeac9218e5107'
            }
        },
        'Darwin': {
            '32-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm',
                'sha512': '3891da8d5080c981fe49fb553b8fe5f99e504fa2550c3a6fb353a18572dd12393234f210ff1d67b1fec48c87fc83a1f1ee7d817757e8406003beeac9218e5107'
            },
            '64-bit': {
                'url': 'https://vm.gtimg.cn/tencentvideo/txp/js/ckey.wasm?v=20171208',
                'ext': '.wasm',
                'content-path': [''],
                'content-base': 'ckey',
                'content-ext': '.wasm',
                'sha512': '3891da8d5080c981fe49fb553b8fe5f99e504fa2550c3a6fb353a18572dd12393234f210ff1d67b1fec48c87fc83a1f1ee7d817757e8406003beeac9218e5107'
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
                'content-ext': '.exe',
                'sha512': '75f44b97b361ea57697c02f0285b610683695357eaf364ecb2cdcb998d5eb1ca99d2a67d8eb61256ef8840a39c6d3c82b3a282f42ed6514400d69c03541161b9'
            },
            '64-bit': {
                'url': 'https://nodejs.org/dist/v16.15.0/node-v16.15.0-win-x64.zip',
                'ext': '.zip',
                'content-path': ['node-v16.15.0-win-x64/'],
                'content-base': 'node',
                'content-ext': '.exe',
                'sha512': 'bb704f2b95ca361c9573eceb7e762e0c3fe8ba2327f19e3deae076513a8a24152d275b6c7cd92baed6d6cf050803ba163065bfa9fba62aeadb10eae553623cac'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://unofficial-builds.nodejs.org/download/release/v16.15.0/node-v16.15.0-linux-x86.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['node-v16.15.0-linux-x86/'],
                'content-base': 'bin/node',
                'content-ext': '',
                'sha512': '090f5af497cc4daa5f053b55ddb7b8a26741e99d583d113abc08a25aad310cf2ff213cdd851e73f11cbbf3f921b6f595ae9929d2013fcbd056ae41402c6a50e8'
            },
            '64-bit': {
                'url': 'https://nodejs.org/dist/v16.15.0/node-v16.15.0-linux-x64.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['node-v16.15.0-linux-x64/'],
                'content-base': 'bin/node',
                'content-ext': '',
                'sha512': 'bb9f8c371419c64b1d4c96b97c71f6956faa5cfc40d2648285fbea7044d6778141b175d2e457c3b7822fb45ab4481b70d565de698bb7f4755c6a72dc39358d4a'
            }
        },
        'Darwin': {
            '32-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': '',
                'content-ext': '',
                'sha512': ''
            },
            '64-bit': {
                'url': '',  # FIXME
                'ext': '.tar.xz',
                'content-path': ['.'],
                'content-base': '',
                'content-ext': '',
                'sha512': ''
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
        LOGGER.error('Downloading 3rd-party files has failed. Try re-run the download, with "--proxy" option if possible')
        sys.exit(result)


def integrity_check():
    pkgs_hashes = [progs_conf[prog][system][bitness]['sha512'] for prog in progs_name]

    for pkg, sha512 in zip(pkgs_full_path, pkgs_hashes):
        hashf = hashlib.sha512()
        with open(pkg, mode='rb') as f:
            hashf.update(f.read())
        md = hashf.hexdigest()

        if md != sha512:
            LOGGER.error("Hash check failed: {!r}".format(pkg))
            sys.exit(-1)


def extract():
    for pkg in pkgs_full_path:
        if pkg.endswith('.zip'):
            with zipfile.ZipFile(pkg) as zip_prog:
                zip_prog.extractall(path=os.path.dirname(pkg))
        elif pkg.endswith('.tar.xz'):
            with tarfile.open(name=pkg, mode='r:xz') as xz_prog:
                xz_prog.extractall(path=os.path.dirname(pkg))
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

    LOGGER.info("Downloading ...")
    download(**kwargs)

    LOGGER.info("Verifying  ...")
    integrity_check()

    LOGGER.info("Extracting ...")
    extract()

    LOGGER.info("Finalizing ...")
    finalize()

    LOGGER.info("All set!")


progs_full_path = [os.path.normpath(os.path.join(base, progs_conf[prog][system][bitness]['content-base'] + progs_conf[prog][system][bitness]['content-ext'])) for prog, base in zip(progs_name, progs_base_path)]


def exists_3rd_parties():
    return all(map(os.path.exists, progs_full_path))


# aria2c ffmpeg mkvmerge node
third_party_progs_default = [os.path.normpath(os.path.join(MOD_DIR, prog, progs_conf[prog][system][bitness]['content-base'])) for prog in ('aria2', 'ffmpeg', 'mkvtoolnix', 'node')]


if __name__ == '__main__':
    download_3rd_parties()
