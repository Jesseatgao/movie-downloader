
import sys
import os
import logging
import errno
from shutil import which

from argparse import ArgumentParser
from configparser import ConfigParser

from .downloader import MDownloader
from .utils import build_logger, change_logging_level


MOD_DIR = os.path.dirname(os.path.abspath(__file__))
LOGGER = build_logger('MDL', os.path.normpath(os.path.join(MOD_DIR, 'log/mdl.log')))


def arg_parser():
    parser = ArgumentParser()

    '''
    url_help_str = """Video URL or cover page URL.
    e.g.
      {}
      {}
      {}""".format(*[val['eg'] for val in g_video_pat_urls.values()])

    parser.add_argument('url', help=url_help_str)
    '''
    parser.add_argument('url', nargs='+', help='')
    parser.add_argument('-D', '--dir', default='', dest='dir', help='path to downloaded videos')
    parser.add_argument('-d', '--definition', default='', dest='definition', choices=['fhd', 'shd', 'hd', 'sd'])
    parser.add_argument('-p', '--proxy', dest='proxy')

    parser.add_argument('--QQVideo-no-logo', dest='QQVideo_no_logo', default='', choices=['True', 'False'])

    parser.add_argument('-A', '--aria2c', dest='aria2c', default='', help='path to the aria2 executable')
    parser.add_argument('-F', '--ffmpeg', dest='ffmpeg', default='', help='path to the ffmpeg executable')
    parser.add_argument('-M', '--mkvmerge', dest='mkvmerge', default='', help='path to the mkvmerge executable')

    parser.add_argument('-L', '--log-level', dest='log_level', default='', choices=['debug', 'info', 'warning', 'error', 'critical'])
    # parser.add_argument('-x', '--max-connection-per-server', dest='mcps', default=16)
    # parser.add_argument('-k', '--min-split-size')

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

    aria2c_default = os.path.normpath(os.path.join(MOD_DIR, '3rd-parties/aria2/aria2c'))
    ffmpeg_default = os.path.normpath(os.path.join(MOD_DIR, '3rd-parties/ffmpeg/ffmpeg'))
    mkvmerge_default = os.path.normpath(os.path.join(MOD_DIR, '3rd-parties/mkvtoolnix/mkvmerge'))

    aria2c_path = args.aria2c or confs['progs']['aria2c'] or aria2c_default
    ffmpeg_path = args.ffmpeg or confs['progs']['ffmpeg'] or ffmpeg_default
    mkvmerge_path = args.mkvmerge or confs['progs']['mkvmerge'] or mkvmerge_default

    progs = (aria2c_path, ffmpeg_path, mkvmerge_path)
    try:
        for prog in progs:
            path, exe = os.path.split(prog)
            if which(exe, path=path) is None:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), exe)
    except Exception as e:
        # logging
        print(str(e))
        sys.exit(-1)

    # update config info
    confs['progs']['aria2c'] = aria2c_path
    confs['progs']['ffmpeg'] = ffmpeg_path
    confs['progs']['mkvmerge'] = mkvmerge_path


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

            definition = args.definition or confs[site]['definition'] or definition_default
            confs[site]['definition'] = definition

            if args.proxy:
                confs[site]['proxy'] = args.proxy


def main():

    confs = conf_parser()  # parse the config file
    parser = arg_parser()
    args = parser.parse_args()

    parse_con_log_level(args, confs)
    change_logging_level('MDL', console_level=confs['misc']['log_level'])

    parse_3rd_party_progs(args, confs)
    parse_dlops_default(args, confs)

    '''
    if not is_url_valid(args.url):
        parser.print_help()
        sys.exit(0)
    '''

    if not (os.path.exists(args.dir) and os.path.isdir(args.dir)):
        print('"{}" is not a valid path!'.format(args.dir))
        sys.exit(-1)



    dl = MDownloader(args, confs)
    dl.download(args.url)



# __all__ = ["main"]
