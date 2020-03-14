
import sys
import os
import logging

from argparse import ArgumentParser

from mdl.downloader import MDownloader


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
    parser.add_argument('-D', '--dir', default='.', dest='dir', help='path to downloaded videos')
    parser.add_argument('-d', '--definition', default=None, dest='definition', choices=['fhd', 'shd', 'hd', 'sd'])
    parser.add_argument('-p', '--proxy', dest='proxy')
    parser.add_argument('-A', '--aria2', dest='aria2', default='', help='path to the aria2 executable')
    parser.add_argument('-F', '--ffmpeg', dest='ffmpeg', default='', help='path to the ffmpeg executable')
    parser.add_argument('-L', '--log-level', dest='log', default='info', choices=['debug', 'info', 'warning', 'error', 'critical'])
    parser.add_argument('-x', '--max-connection-per-server', dest='mcps', default=16)
    parser.add_argument('-k', '--min-split-size')

    return parser


def main():

    parser = arg_parser()
    args = parser.parse_args()

    '''
    if not is_url_valid(args.url):
        parser.print_help()
        sys.exit(0)
    '''

    if not (os.path.exists(args.dir) and os.path.isdir(args.dir)):
        print('"{}" is not a valid path!'.format(args.dir))
        sys.exit(0)

    log_level = getattr(logging, args.log.upper())
    logging.basicConfig(level=log_level)

    dl = MDownloader(args)
    dl.download(args.url)



# __all__ = ["main"]
