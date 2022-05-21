
import sys
import os
import logging
import errno
from shutil import which
from itertools import zip_longest

from argparse import ArgumentParser
from configparser import ConfigParser

from .third_parties import exists_3rd_parties, third_party_progs_default
from .downloader import MDownloader
from .utils import build_logger, change_logging_level


MOD_DIR = os.path.dirname(os.path.abspath(__file__))
LOGGER = build_logger('MDL', os.path.normpath(os.path.join(MOD_DIR, 'log/mdl.log')))


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
    parser.add_argument('-D', '--dir', default='', dest='dir', help='path to downloaded videos')
    parser.add_argument('-d', '--definition', default='', dest='definition', choices=['fhd', 'shd', 'hd', 'sd'])
    parser.add_argument('-p', '--proxy', dest='proxy', help='proxy in the form of "http://[user:password@]host:port"')
    parser.add_argument('--playlist-items', default='', dest='playlist_items', type=_segment_playlist_items,
                        help='desired episode indices in a playlist separated by commas, while the playlists are separated by semicolons,'
                             'e.g. "--playlist-items 1,2,5-10", "--playlist-items 1,2,5-10;3-", and "--playlist-items 1,2,5-10;;-20"')

    parser.add_argument('--QQVideo-no-logo', dest='QQVideo_no_logo', default='', choices=['True', 'False'])

    parser.add_argument('-A', '--aria2c', dest='aria2c', default='', help='path to the aria2 executable')
    parser.add_argument('-F', '--ffmpeg', dest='ffmpeg', default='', help='path to the ffmpeg executable')
    parser.add_argument('-M', '--mkvmerge', dest='mkvmerge', default='', help='path to the mkvmerge executable')
    parser.add_argument('-N', '--node', dest='node', default='', help='path to the node executable')

    parser.add_argument('-L', '--log-level', dest='log_level', default='', choices=['debug', 'info', 'warning', 'error', 'critical'])

    return parser


def conf_parser():
    confs = {}

    conf_dlops = os.path.join(MOD_DIR, 'conf/dlops.conf')
    conf_misc = os.path.join(MOD_DIR, 'conf/misc.conf')

    conf_all = (conf_dlops, conf_misc)

    for conf_path in conf_all:
        config = ConfigParser()
        config.read(conf_path)
        for section in config.sections():
            confs[section] = {}
            for option in config.options(section):
                confs[section][option] = config.get(section, option)

    return confs


def parse_3rd_party_progs(args, confs):
    """Option precedence: cmdline args > confs(config file) > default"""

    aria2c_default, ffmpeg_default, mkvmerge_default, node_default = third_party_progs_default

    aria2c_path = args.aria2c or confs['progs']['aria2c'] or aria2c_default
    ffmpeg_path = args.ffmpeg or confs['progs']['ffmpeg'] or ffmpeg_default
    mkvmerge_path = args.mkvmerge or confs['progs']['mkvmerge'] or mkvmerge_default
    node_path = args.node or confs['progs']['node'] or node_default

    progs = (aria2c_path, ffmpeg_path, mkvmerge_path, node_path)
    try:
        for prog in progs:
            path, exe = os.path.split(prog)
            if which(exe, path=path) is None:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), exe)
    except Exception as e:
        LOGGER.error(str(e))
        LOGGER.info('For how to get and install Aria2, FFmpeg, MKVToolnix(mkvmerge) and Nodejs, please refer to README.md. '
                    'Or simply run "mdl_3rd_parties" from within the Shell. Note that "--proxy" option may be needed.')
        sys.exit(-1)

    # update config info
    confs['progs']['aria2c'] = aria2c_path
    confs['progs']['ffmpeg'] = ffmpeg_path
    confs['progs']['mkvmerge'] = mkvmerge_path
    confs['progs']['node'] = node_path


def parse_con_log_level(args, confs):
    log_level_default = "info"

    con_log_level = args.log_level or confs['misc']['log_level'] or log_level_default
    con_log_level = getattr(logging, con_log_level.upper())

    confs['misc']['log_level'] = con_log_level


def parse_dlops_default(args, confs):
    save_dir_default = '.'
    definition_default = 'fhd'

    for site in confs:
        if site not in ('misc', 'progs'):
            save_dir = args.dir or confs[site]['dir'] or save_dir_default
            confs[site]['dir'] = save_dir
            # Validate the file save directory
            if not (os.path.exists(save_dir) and os.path.isdir(save_dir)):
                LOGGER.error('"{}" is not a valid path!'.format(save_dir))
                sys.exit(-1)

            definition = args.definition or confs[site]['definition'] or definition_default
            confs[site]['definition'] = definition

            if args.proxy:
                confs[site]['proxy'] = args.proxy


def parse_other_ops(args, confs):
    # associate the playlist URLs with desired video episodes
    url_plist = zip_longest(args.url, args.playlist_items) if len(args.url) >= len(args.playlist_items) else zip(args.url, args.playlist_items)
    confs['playlist_items'] = {url: items for url, items in url_plist}


def check_deps():
    if not exists_3rd_parties():
        LOGGER.error('The third-parties such as Aria2, FFmpeg, MKVToolnix and Nodejs are required. Before moving on, '
                     'simply run "mdl_3rd_parties" from within the Shell to automatically download and install them. '
                     'Note that "--proxy" option may be needed.'
                     'For how to get and install them manually, please refer to README.md.')
        sys.exit(-1)


def main():
    check_deps()  # make sure the prerequisites are satisfied

    confs = conf_parser()  # parse the config file
    parser = arg_parser()
    args = parser.parse_args()

    parse_con_log_level(args, confs)
    change_logging_level('MDL', console_level=confs['misc']['log_level'])

    parse_3rd_party_progs(args, confs)
    parse_dlops_default(args, confs)
    parse_other_ops(args, confs)

    dl = MDownloader(args, confs)
    dl.download(args.url)

# __all__ = ["main"]
