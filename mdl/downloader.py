import os
import subprocess
import tempfile
import shutil
import errno
import logging
from math import trunc, log10

from certifi import where
from bdownload.download import requests_retry_session

from .commons import VIDEO_DEFINITIONS
from .commons import VideoTypes
from .sites import get_all_sites_vcs
from .utils import logging_with_pipe, normalize_filename


cert_path = where()


class MDownloader(object):
    def __init__(self, args=None, confs=None):
        self._vcs = get_all_sites_vcs()
        self.args = args
        self.confs = confs

        logger_name = '.'.join(['MDL', 'MDownloader'])  # 'MDL.MDownloader'
        self._logger = logging.getLogger(logger_name)

    def download(self, urls):
        for url in urls:
            cover_info = self.extract_config_info(url)
            if cover_info:
                cover_dir, episodes = self.dwnld_videos_with_aria2(
                    cover_info, save_dir=self.confs[cover_info["vc_name"]]["dir"],
                    defn=self.confs[cover_info["vc_name"]]['definition'])
                self.join_videos(cover_dir, episodes)

    def extract_config_info(self, url):
        for name, vc in self._vcs.items():
            vcc = vc['class']
            if not vcc.is_url_valid(url):
                continue

            vci = vc.get('instance')
            if vci is None:
                requester = requests_retry_session()
                vci = vcc(requester, self.args, self.confs)
                vc['instance'] = vci

            cover_info = vci.get_video_config_info(url)
            if cover_info:
                cover_info["source_name"] = vcc.SOURCE_NAME
                cover_info["vc_name"] = vcc.VC_NAME
                cover_info['url'] = url
            return cover_info
        else:
            # check site domain name against URL
            self._logger.error("Video URL {!r} is invalid".format(url))
            return None

    def dwnld_videos_with_aria2(self, cover_info, save_dir='.', defn=None):
        """
        :returns:
        (abs_cover_dir, [(abs_episode1_dir, [fname1.1.mp4, fname1.2.mp4]),(abs_episode2_dir, [fname2.1.mp4, fname2.2.mp4])])
        """

        def pick_highest_definition(defns):
            for definition in VIDEO_DEFINITIONS:
                if defns.get(definition):
                    return definition

        def pick_format(formats):
            for format in formats:
                if format['ext'] != 'ts':
                    return format

            return formats[0]

        def determine_ep_naming_fmt():
            width = 2  # default episode numbering format width
            total_ep = cover_info.get('episode_all')
            if total_ep:
                ndigits = trunc(log10(total_ep)) + 1
                width = ndigits

            normal_ids = cover_info.get('normal_ids', [])
            ep_cnt = sum([1 for vi in normal_ids if vi.get('defns') and any(vi['defns'].values())])  # number of valid episodes
            numbering = False if (total_ep and total_ep == 1) or (not total_ep and ep_cnt == 1) else True

            return numbering, width

        video_list = cover_info.get('normal_ids')
        if video_list:
            cover_name = '.'.join([cover_info.get('title') if cover_info.get('title') else cover_info['source_name'] + '_' + cover_info.get('cover_id', ''),
                                   cover_info.get('year', '1900')])
            cover_name = normalize_filename(cover_name, repl='_')
            cover_default_dir = '.'.join([cover_name, cover_info.get('type', VideoTypes.MOVIE)])
            cover_dir = os.path.abspath(os.path.join(save_dir, cover_default_dir))

            urls = []  # URLs file info for aria2c
            episodes = []  # [(abs_episode1_dir, [fname1.1.mp4, fname1.2.mp4]), ]

            ep_fmt_numbering, ep_fmt_width = determine_ep_naming_fmt()

            for vi in video_list:
                if vi.get('defns') and any(vi['defns'].values()):
                    if not (defn and vi['defns'].get(defn)):
                        defn = pick_highest_definition(vi['defns'])
                    if ep_fmt_numbering:
                        episode_default_dir = '.'.join(
                            [cover_name, 'EP' + '{:0{width}}'.format(vi['E'], width=ep_fmt_width),
                             'WEBRip', cover_info['source_name'] + '_' + defn])
                    else:
                        episode_default_dir = '.'.join([cover_name, 'WEBRip', cover_info['source_name'] + '_' + defn])
                    episode_dir = os.path.join(cover_dir, episode_default_dir)

                    format = pick_format(vi['defns'][defn])
                    ext = format['ext']

                    fnames = []
                    for idx, url in enumerate(format['urls']):
                        # fname ~ seg_0000.mp4 seg_0001.mp4 seg_0002.mp4 ...
                        fname = "seg_{:04}.{}".format(idx, ext)
                        fnames.append(fname)
                        urls.append('{}\n  dir={}\n  out={}'.format(url, episode_dir, fname))

                    episodes.append((episode_dir, fnames))

            urllist = '\n'.join(urls)

            if not urllist:
                self._logger.warning("No files to download for '{}'.".format(cover_info['url']))
                return "", []

            aria2c = self.confs['progs']['aria2c']
            user_agent = self.confs[cover_info['vc_name']]['user_agent']
            proxy = self.confs[cover_info['vc_name']]['proxy'] \
                if self.confs[cover_info['vc_name']]['enable_proxy_dl_video'].lower() == "true" else ''
            mcd = self.confs[cover_info['vc_name']]['max_concurrent_downloads']
            mss = self.confs[cover_info['vc_name']]['min_split_size']
            split = self.confs[cover_info['vc_name']]['split']
            mcps = self.confs[cover_info['vc_name']]['max_connection_per_server']
            retry_wait = self.confs[cover_info['vc_name']]['retry_wait']
            speed_limit = self.confs[cover_info['vc_name']]['lowest_speed_limit']
            referer = cover_info['referrer']

            cmd_aria2c = [aria2c, '-c', '-j', mcd,  '-k', mss, '-s', split, '-x', mcps, '--max-file-not-found=5000', '-m0',
                          '--retry-wait', retry_wait, '--lowest-speed-limit', speed_limit, '--no-conf', '-i-',
                          '--console-log-level=warn', '--download-result=hide', '--summary-interval=0', '--uri-selector=adaptive',
                          '--referer', referer, '--ca-certificate', cert_path, '-U', user_agent, '--all-proxy', proxy,
                          '--retry-on-400=true', '--retry-on-403=true', '--retry-on-406=true', '--retry-on-unknown=true']
            try:
                with logging_with_pipe(self._logger, level=logging.INFO, text=True) as log_pipe:
                    with subprocess.Popen(cmd_aria2c, bufsize=1, universal_newlines=True, encoding='utf-8',
                                          stdin=subprocess.PIPE, stdout=log_pipe, stderr=subprocess.STDOUT) as proc:
                        proc.stdin.write(urllist)
                        proc.stdin.close()
            except OSError as e:
                self._logger.error("OS error number {}: '{}'".format(e.errno, e.strerror))

            if not proc.returncode:
                return cover_dir, episodes
        else:
            self._logger.warning("No files to download for '{}'.".format(cover_info['url']))

        return "", []

    def join_videos_with_ffmpeg_mkvmerge(self, cover_dir, episode_dir, fnames):
        """abs_cover_dir > abs_episode_dir > video files """

        if cover_dir and episode_dir and fnames:
            # determine the extension (i.e. video format)
            suffix = '.' + fnames[0].split('.')[-1]
            episode_name = os.path.basename(episode_dir) + suffix
            episode_name = os.path.join(cover_dir, episode_name)

            proc = None
            if suffix in ['.ts', '.mpg', '.mpeg']:
                if suffix == '.ts':
                    episode_name = episode_name.rpartition('.')[0] + '.mp4'
                '''
                with tempfile.TemporaryFile(mode='w+b', suffix=suffix, dir=coverdir) as tmpf:
                    for fn in fnames:
                        with open(os.path.join(episodedir, fn), 'rb') as f:
                            tmpf.write(f.read())
                    tmpf.flush()
                    tmpf.seek(0)

                    cmd = ['ffmpeg', '-y', '-i', 'pipe:0', '-safe', '0', '-c', 'copy', '-hide_banner', episode_name]
                    proc = subprocess.run(cmd, input=tmpf.read())
                '''
                ffmpeg = self.confs['progs']['ffmpeg']
                cmd = [ffmpeg, '-y', '-i', 'pipe:0', '-safe', '0', '-c', 'copy', '-hide_banner', episode_name]
                try:
                    with logging_with_pipe(self._logger, level=logging.INFO) as log_pipe:
                        with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log_pipe, stderr=subprocess.STDOUT) as proc:
                            for fn in fnames:
                                with open(os.path.join(episode_dir, fn), 'rb') as f:
                                    try:
                                        proc.stdin.write(f.read())
                                    except IOError as e:
                                        if e.errno == errno.EPIPE or e.errno == errno.EINVAL:
                                            break
                                        else:
                                            raise

                            proc.stdin.close()
                except OSError as e:
                    self._logger.error("OS error number {}: '{}'".format(e.errno, e.strerror))
            else:
                '''
                flist = ["file '{}'".format(os.path.join(episodedir, fn)) for fn in fnames]
                flist = '\n'.join(flist)

                cmd = ['ffmpeg', '-y', '-safe', '0', '-protocol_whitelist', 'file,pipe', '-f', 'concat',
                       '-i', 'pipe:0', '-c', 'copy', '-hide_banner', episode_name]
                cp = subprocess.run(cmd, input=flist.encode('utf-8'))
                '''
                flist = ["{}".format(os.path.join(episode_dir, fn)) for fn in fnames]
                episode_name = episode_name.rpartition('.')[0] + '.mkv'

                mkvmerge = self.confs['progs']['mkvmerge']
                cmd = [mkvmerge, '-o', episode_name, '['] + flist + [']']
                try:
                    with logging_with_pipe(self._logger, level=logging.INFO, text=True) as log_pipe:
                        with subprocess.Popen(cmd, bufsize=1, universal_newlines=True, encoding='utf-8',
                                              stdout=log_pipe, stderr=subprocess.STDOUT) as proc:
                            pass
                except OSError as e:
                    self._logger.error("OS error number {}: '{}'".format(e.errno, e.strerror))

            if proc and proc.returncode == 0:
                return True

    def join_videos(self, cover_dir, episodes):
        for episode_dir, fnames in episodes:
            if len(fnames) > 0:
                res = self.join_videos_with_ffmpeg_mkvmerge(cover_dir, episode_dir, fnames)
                if res:
                    shutil.rmtree(episode_dir, ignore_errors=True)
                else:
                    self._logger.error('Join videos failed! <{}>'.format(episode_dir))
