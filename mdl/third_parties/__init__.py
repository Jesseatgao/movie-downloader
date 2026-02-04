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
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.37.0-win-linux--builder-win32-v1.8-el9/aria2-i686-win.zip',
                'ext': '.zip',
                'content-path': ['i686/'],
                'content-base': 'aria2c',
                'content-ext': '.exe',
                'sha512': 'c65b7128172352375d7bf4d1a6acf11165002b38b82c5cae69a77f83f7d986e397346cbcbd35def01825ce9789947b2877470271410753e1900007d39257b20a'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.37.0-win-linux--builder-win32-v1.8-el9/aria2-x86_64-win.zip',
                'ext': '.zip',
                'content-path': ['x86_64/'],
                'content-base': 'aria2c',
                'content-ext': '.exe',
                'sha512': 'a5d8feed8f973948cb70323d6388c5ae6da27f153f66529ab552932e4b3a575b0f2250e437b4f5fa1a0ec800a1a7b13b1b964ba77438c4bdeef1ba7fd649207b'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.37.0-win-linux--builder-win32-v1.8-el9/aria2-i686-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['i686/'],
                'content-base': 'aria2c',
                'content-ext': '',
                'sha512': 'a9a8c1fc1483f6911706ad4f3388990730b2165c7476373a0094a3e43af2d76d37f281fddff9017d5f6ed1fac9f6fd157ec3e12300844c3f363bd995c3e4db57'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/aria2-patched-static-build/releases/download/1.37.0-win-linux--builder-win32-v1.8-el9/aria2-x86_64-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['x86_64/'],
                'content-base': 'aria2c',
                'content-ext': '',
                'sha512': 'a18668d7dde41bfc334782fb1805764a5ac95f7dc12a6096638c0d7eb36acf65a3c42e262eb6bdee26f386769a133b7b140920ad1f30ecc70c9eec7384717476'
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
                'url': 'https://github.com/GyanD/codexffmpeg/releases/download/7.0.2/ffmpeg-7.0.2-full_build.zip',
                'ext': '.zip',
                'content-path': ['ffmpeg-7.0.2-full_build/', 'bin/'],
                'content-base': 'ffmpeg',
                'content-ext': '.exe',
                'sha512': '345bce3bc4c95f3bd8ad74c79c37354318d371cd854a3ef5be3512f9868f606226f8e75c364691adeb60764ad1f67d0e6b334a92e45a2ee0a7d12595549a2500'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-7.0.2-i686-static.tar.xz\t'
                       'https://johnvansickle.com/ffmpeg/releases/ffmpeg-7.0.2-i686-static.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['ffmpeg-7.0.2-i686-static/'],
                'content-base': 'ffmpeg',
                'content-ext': '',
                'sha512': '1b2d58d55158606e4e45edb60475cb36f023960d66f7cce42b8f6e38eb1ec9a1775c0e5b3b77fd012055d93465e9a9586fbbefccda07fcba301f5823e832c9b2'
            },
            '64-bit': {
                'url': 'https://www.johnvansickle.com/ffmpeg/old-releases/ffmpeg-7.0.2-amd64-static.tar.xz\t'
                       'https://johnvansickle.com/ffmpeg/releases/ffmpeg-7.0.2-amd64-static.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['ffmpeg-7.0.2-amd64-static/'],
                'content-base': 'ffmpeg',
                'content-ext': '',
                'sha512': 'e80880362208de7437f0eb98d25ec6676df122a04613a818bb14101c3e1ccf91feab06246d40359b887b147af65d80eef5dba99964cac469bcb560f1a063d737'
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
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.8el9/mkvtoolnix-i686-win.zip',
                'ext': '.zip',
                'content-path': ['i686/'],
                'content-base': 'mkvmerge',
                'content-ext': '.exe',
                'sha512': 'd6aec39e0c52d976ea1a56d77ee2c01b10e66cfcc9a722ce94cf988902a487302a55a0afe15ddd75579e0f4b67e1e1c1f3285f9c2bbfadb9a8759e2512bcba51'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.8el9/mkvtoolnix-x86_64-win.zip',
                'ext': '.zip',
                'content-path': ['x86_64/'],
                'content-base': 'mkvmerge',
                'content-ext': '.exe',
                'sha512': '04e93d9bcb07949188fac3c49611f6d184160681a6f1a3dead9ef8deed4cfa05b0de099dc4e51e21147d048e6c767c6cc16e624dfa23ccfe6440b3d0fc600d10'
            }
        },
        'Linux': {
            '32-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.8el9/mkvtoolnix-i686-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['i686/'],
                'content-base': 'mkvmerge',
                'content-ext': '',
                'sha512': '54dafa64a1277a59f5c30e1057b2fe6dc9ad4dc5f64b5189e34bc15ab6fdff4571ccb831f54e3756e8fe65b45250e11fa0fd211997a783251e8bbce2f5a96a68'
            },
            '64-bit': {
                'url': 'https://github.com/Jesseatgao/MKVToolNix-static-builds/releases/download/v58.0.0-mingw-w64-win32v1.8el9/mkvtoolnix-x86_64-linux.tar.xz',
                'ext': '.tar.xz',
                'content-path': ['x86_64/'],
                'content-base': 'mkvmerge',
                'content-ext': '',
                'sha512': '2d6877b2a70fed42e0230d535f01e417179462d32eb03afbbfe500118a89adb56ddbe3d0c82752e86671d3f2c2ce5ec206573f86e70c1a47dd2f028934768cf5'
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
                'url': 'https://nodejs.org/dist/v16.15.0/node-v16.15.0-win-x86.zip\t'
                       'https://kernel.nullivex.com/nodejs/release/v16.15.0/node-v16.15.0-win-x86.zip',
                'ext': '.zip',
                'content-path': ['node-v16.15.0-win-x86/'],
                'content-base': 'node',
                'content-ext': '.exe',
                'sha512': '75f44b97b361ea57697c02f0285b610683695357eaf364ecb2cdcb998d5eb1ca99d2a67d8eb61256ef8840a39c6d3c82b3a282f42ed6514400d69c03541161b9'
            },
            '64-bit': {
                'url': 'https://nodejs.org/dist/v16.15.0/node-v16.15.0-win-x64.zip\t'
                       'https://kernel.nullivex.com/nodejs/release/v16.15.0/node-v16.15.0-win-x64.zip',
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
                'url': 'https://nodejs.org/dist/v16.15.0/node-v16.15.0-linux-x64.tar.xz\t'
                       'https://kernel.nullivex.com/nodejs/release/v16.15.0/node-v16.15.0-linux-x64.tar.xz',
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
