import sys
import os
from shutil import which
from itertools import zip_longest
import codecs
from pathlib import Path
from argparse import ArgumentParser, ArgumentTypeError
from configparser import ConfigParser

import certifi

from .third_parties import exists_3rd_parties, third_party_progs_default
from .downloader import MDownloader
from .utils import build_logger, change_logging_level, json_path_get, CommentConfigParser

from mdl.sites import get_all_sites_vcs


MOD_DIR = os.path.dirname(os.path.abspath(__file__))
LOGGER = build_logger('MDL', os.path.normpath(os.path.join(MOD_DIR, 'log/mdl.log')))


def _validate_dir(directory):
    if directory and not os.path.isdir(directory):
        raise ArgumentTypeError('"{}" is not a valid directory!'.format(directory))

    return directory


def _segment_playlist_items(items):
    """Segment playlists' episode indices.

    >>> _segment_playlist_items("1, 2,5-10; ; 3 -; -3; 4 ,6")
    [[1, 2, (5, 10)], None, [(3, None)], [(1, 3)], [4, 6]]
    """
    res = []

    playlist = items.split(';')
    for pi in playlist:
        pl = []
        pli = pi.split(',')
        for it in pli:
            if '-' in it:
                itr = it.split('-')
                itr[0] = int(itr[0]) if itr[0].strip() else 1
                itr[1] = int(itr[1]) if itr[1].strip() else None
                pl.append(tuple(itr))
            else:
                if it.strip():
                    pl.append(int(it))

        if not pl:
            pl = None
        res.append(pl)

    return res


def arg_parser():
    parser = ArgumentParser()

    parser.add_argument('url', nargs='+', help='Episode or cover/playlist web page URL(s)')
    parser.add_argument('-D', '--dir', default=None, dest='dir', type=_validate_dir, help='path to downloaded videos')
    parser.add_argument('-d', '--definition', default=None, dest='definition', choices=['dolby', 'sfr_hdr', 'hdr10', 'uhd', 'fhd', 'shd', 'hd', 'sd'])
    parser.add_argument('-p', '--proxy', dest='proxy', help='proxy in the form of "http://[user:password@]host:port"')
    parser.add_argument('--playlist-items', default='', dest='playlist_items', type=_segment_playlist_items,
                        help='desired episode indices in a playlist separated by commas, while the playlists are separated by semicolons,'
                             'e.g. "--playlist-items 1,2,5-10", "--playlist-items 1,2,5-10;3-", and "--playlist-items 1,2,5-10;;-20"')

    parser.add_argument('--no-logo', dest='no_logo', default=None, const='True', nargs='?', choices=['True', 'False'])
    parser.add_argument('--merge-all', dest='merge_all', default=None, const='True', nargs='?', choices=['True', 'False'])
    parser.add_argument('--ts-convert', dest='ts_convert', default=None, const='True', nargs='?', choices=['True', 'False'])
    parser.add_argument('--proxy-dl-video', dest='enable_proxy_dl_video', default=None, const='True', nargs='?', choices=['True', 'False'])

    parser.add_argument('-A', '--aria2c', dest='aria2c', default=None, help='path to the aria2 executable')
    parser.add_argument('-F', '--ffmpeg', dest='ffmpeg', default=None, help='path to the ffmpeg executable')
    parser.add_argument('-M', '--mkvmerge', dest='mkvmerge', default=None, help='path to the mkvmerge executable')
    parser.add_argument('-N', '--node', dest='node', default=None, help='path to the node executable')

    parser.add_argument('-L', '--log-level', dest='log_level', default=None, choices=['debug', 'info', 'warning', 'error', 'critical'])
    parser.add_argument('--delay-delete', dest='delay_delete', default=None, const='True', nargs='?', choices=['True', 'False'])

    return parser


def conf_parser():
    confs = {}

    conf_dlops = os.path.join(MOD_DIR, 'conf/dlops.conf')
    conf_misc = os.path.join(MOD_DIR, 'conf/misc.conf')

    conf_all = (conf_dlops, conf_misc)

    for conf_path in conf_all:
        config = ConfigParser(interpolation=None, allow_no_value=True)
        config.read(conf_path)
        for section in config.sections():
            confs[section] = {}
            for option in config.options(section):
                confs[section][option] = config.get(section, option)

    return confs


def parse_3rd_party_progs(args, confs):
    """Option precedence: cmdline args > confs(config file) > default"""
    aria2c_default, ffmpeg_default, mkvmerge_default, node_default = third_party_progs_default

    prog_defaults = {
        'aria2c': aria2c_default,
        'ffmpeg': ffmpeg_default,
        'mkvmerge': mkvmerge_default,
        'node': node_default
    }

    for prog, default in prog_defaults.items():
        args[prog] = confs['progs'][prog] = args[prog] or json_path_get(confs, ['progs', prog]) or default
        path, exe = os.path.split(args[prog])
        if which(exe, path=path) is None:
            LOGGER.error('Could not find {} executable: "{}"'.format(prog, args[prog]))
            sys.exit(-1)


def parse_misc_default(args, confs):
    misc_defaults = {
        'log_level': 'INFO',
        'delay_delete': 'True'
    }

    for conf, default in misc_defaults.items():
        confs['misc'][conf] = args.get(conf) or json_path_get(confs, ['misc', conf]) or default

        lconf = confs['misc'][conf].lower()
        if lconf in ('true', 'false'):
            confs['misc'][conf] = True if lconf == 'true' else False


def parse_dlops_default(args, confs):
    conf_defaults = {
        'dir': str(Path.cwd()),
        'definition': 'uhd',
        'no_logo': 'True',
        'merge_all': 'True',
        'ts_convert': 'True',
        'episode_batch_size': '2',
        'proxy': '',
        'enable_proxy_dl_video': 'False',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        'enable_vip_apis': 'False',
        # Aria2:
        'max_concurrent_downloads': '5',
        'min_split_size': '200K',
        'split': '10',
        'max_connection_per_server': '16',
        'retry_wait': '5',
        'lowest_speed_limit': '100K',
        'max_file_not_found': '10',
        'max_tries': '5000',
        'retry_on_400': 'false',
        'retry_on_403': 'false',
        'retry_on_406': 'false',
        'retry_on_unknown': 'false',
        'retry_on_not_satisfied_206': 'false'
    }

    for site in confs:
        if site not in ('misc', 'progs'):
            for conf, default in conf_defaults.items():
                confs[site][conf] = args.get(conf) or json_path_get(confs, [site, conf]) or default

                lconf = confs[site][conf].lower()
                if lconf in ('true', 'false'):
                    confs[site][conf] = True if lconf == 'true' else False


def parse_ca_bundle(args, confs):
    """Combine the site-configured intermediate certificates with the CA bundle from `certifi`"""
    here = os.path.abspath(os.path.dirname(__file__))
    vc_ca_path = Path(os.path.join(here, 'certs'))

    for site in confs:
        if site not in ('misc', 'progs'):
            vc_ca_bundle = os.path.join(vc_ca_path, ''.join([site, '_', 'cacert.pem']))

            if not confs[site]['ca_cert']:
                if os.path.isfile(vc_ca_bundle):
                    os.remove(vc_ca_bundle)
                continue

            vc_ca_path.mkdir(parents=True, exist_ok=True)
            with codecs.open(vc_ca_bundle, 'w', 'utf-8') as vc_fd:
                vc_fd.write('\n')
                vc_fd.write(confs[site]['ca_cert'])
                vc_fd.write('\n')
                with codecs.open(certifi.where(), 'r', 'utf-8') as certifi_fd:
                    vc_fd.write(certifi_fd.read())

            confs[site]['ca_cert'] = vc_ca_bundle


def parse_callbacks(args, confs):
    callbacks = {
        'device_id': 'generate_device_id'
    }

    conf_dlops = os.path.join(MOD_DIR, 'conf/dlops.conf')
    config = CommentConfigParser(interpolation=None, allow_no_value=True)
    config.read(conf_dlops)

    changed = False
    for site in config.sections():
        for cf, cb in callbacks.items():
            if not confs[site][cf]:
                conf = getattr(get_all_sites_vcs()[site]['class'], cb)()
                if conf:
                    confs[site][cf] = config[site][cf] = conf
                    changed = True

    if changed:
        with codecs.open(conf_dlops, 'w', 'utf-8') as conf_fd:
            config.write(conf_fd)


def parse_other_ops(args, confs):
    # associate the playlist URLs with desired video episodes
    url_plist = zip_longest(args['url'], args['playlist_items']) if len(args['url']) >= len(args['playlist_items']) else zip(args['url'], args['playlist_items'])
    args['playlist_items'] = {url: items for url, items in url_plist}


def check_deps():
    if not exists_3rd_parties():
        LOGGER.error('The third-parties such as Aria2, FFmpeg, MKVToolnix and Nodejs are required. Before moving on, '
                     'simply run "mdl_3rd_parties" from within the Shell to automatically download and install them. '
                     'Note that "--proxy" option may be needed. '
                     'For how to get and install them manually, please refer to README.md.')
        sys.exit(-1)


def init(args, confs):
    change_logging_level('MDL', console_level=confs['misc']['log_level'].upper())


def main():
    check_deps()  # make sure the prerequisites are satisfied

    confs = conf_parser()  # parse the config file
    parser = arg_parser()
    args = vars(parser.parse_args())

    parse_misc_default(args, confs)
    parse_3rd_party_progs(args, confs)
    parse_dlops_default(args, confs)
    parse_ca_bundle(args, confs)
    parse_callbacks(args, confs)
    parse_other_ops(args, confs)

    init(args, confs)

    dl = MDownloader(args, confs)
    dl.download()

# __all__ = ["main"]
