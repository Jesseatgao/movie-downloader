import os
import subprocess
import shutil
import errno
import logging
from math import trunc, log10, ceil
import random
from pathlib import Path

from certifi import where

from .commons import pick_highest_definition, VideoTypes, DEFAULT_YEAR
from .sites import get_all_sites_vcs
from .utils import logging_with_pipe, normalize_filename


class MDownloader(object):
    def __init__(self, args=None, confs=None):
        self._vcs = get_all_sites_vcs()
        self.args = args
        self.confs = confs

        logger_name = '.'.join(['MDL', 'MDownloader'])  # 'MDL.MDownloader'
        self._logger = logging.getLogger(logger_name)

    def download(self):
        for url in self.args['url']:
            vci = self.get_video_extractor(url)
            if not vci:
                self._logger.error("Video URL {!r} is invalid".format(url))
                continue

            cover_info = vci.get_cover_config_info(url)
            if not cover_info or not cover_info.get('normal_ids'):
                self._logger.warning("No files to download for '{}'.".format(url))
                continue

            # download the list of videos in batches, instead of all at once
            batch_size = int(vci.confs['episode_batch_size'])
            batch_cover_info = cover_info.copy()
            video_list = cover_info['normal_ids']

            for batch_start in range(0, len(video_list), batch_size):
                batch_cover_info['normal_ids'] = video_list[batch_start:batch_start + batch_size]

                vci.update_cover_dwnld_info(batch_cover_info)
                cover_dir, episodes = self.dwnld_videos_with_aria2(batch_cover_info,
                                                                   save_dir=vci.confs['dir'],
                                                                   defn=vci.confs['definition'])

                if vci.confs['merge_all']:
                    self.join_videos(cover_dir, episodes, ts_convert=vci.confs['ts_convert'])

    def get_video_extractor(self, url):
        for name, vc in self._vcs.items():
            vcc = vc['class']
            # check site domain name against URL
            if not vcc.is_url_valid(url):
                continue

            vci = vc.get('instance')
            if vci is None:
                vci = vcc(self.args, self.confs[vcc.VC_NAME])
                vc['instance'] = vci

            return vci

    @staticmethod
    def _rand_min_split_size(mss, fallback=False):
        mss = mss.upper()
        bytes = 1024 * int(mss[:-1]) if mss[-1] == 'K' else 1024 * 1024 * int(mss[:-1]) if mss[-1] == 'M' else int(mss)
        if bytes >= 1 << 30:
            return mss

        if fallback and bytes < 1 << 20:
            bytes = 1 << 20

        random.seed()
        bytes += 20 * 1024 * random.randint(0, 20)
        bytes = ceil(bytes / 1024) * 1024

        return str(min(1 << 30, bytes))

    def _cmd_aria2c(self, cover_info):
        aria2c = self.confs['progs']['aria2c']
        user_agent = self.confs[cover_info['vc_name']]['user_agent']
        proxy = self.confs[cover_info['vc_name']]['proxy'] \
            if self.confs[cover_info['vc_name']]['enable_proxy_dl_video'] else ''
        mcd = self.confs[cover_info['vc_name']]['max_concurrent_downloads']
        mss = self._rand_min_split_size(self.confs[cover_info['vc_name']]['min_split_size'])
        split = self.confs[cover_info['vc_name']]['split']
        mcps = self.confs[cover_info['vc_name']]['max_connection_per_server']
        mfnf = self.confs[cover_info['vc_name']]['max_file_not_found']
        max_tries = self.confs[cover_info['vc_name']]['max_tries']
        retry_wait = self.confs[cover_info['vc_name']]['retry_wait']
        speed_limit = self.confs[cover_info['vc_name']]['lowest_speed_limit']
        retry_on_400 = '--retry-on-400=true' if self.confs[cover_info['vc_name']]['retry_on_400'] else '--retry-on-400=false'
        retry_on_403 = '--retry-on-403=true' if self.confs[cover_info['vc_name']]['retry_on_403'] else '--retry-on-403=false'
        retry_on_406 = '--retry-on-406=true' if self.confs[cover_info['vc_name']]['retry_on_406'] else '--retry-on-406=false'
        retry_on_unknown = '--retry-on-unknown=true' if self.confs[cover_info['vc_name']]['retry_on_unknown'] else '--retry-on-unknown=false'
        retry_on_not_satisfied_206 = '--retry-on-not-satisfied-206=true' \
            if self.confs[cover_info['vc_name']]['retry_on_not_satisfied_206'] else '--retry-on-not-satisfied-206=false'
        retry_on_lowest_speed = '--retry-on-lowest-speed=true' \
            if self.confs[cover_info['vc_name']]['retry_on_lowest_speed'] else '--retry-on-lowest-speed=false'
        referer = cover_info['referrer']
        cert_path = self.confs[cover_info['vc_name']]['ca_cert'] or where()

        cmd_aria2c = [aria2c, '-c', '-j', mcd, '-k', mss, '-s', split, '-x', mcps, '--max-file-not-found', mfnf, '-m', max_tries,
                      '--retry-wait', retry_wait, '--lowest-speed-limit', speed_limit, '--no-conf', '-i-',
                      '--console-log-level=warn', '--download-result=hide', '--summary-interval=0',
                      '--uri-selector=adaptive',
                      '--referer', referer, '--ca-certificate', cert_path, '-U', user_agent, '--all-proxy', proxy,
                      retry_on_400, retry_on_403, retry_on_406, retry_on_unknown, retry_on_not_satisfied_206, retry_on_lowest_speed]

        # fallback cmd with standard options/values only
        fallback_aria2c = cmd_aria2c.copy()
        fallback_aria2c = fallback_aria2c[:-6]  # remove the augmented retry-on options
        fallback_aria2c[5] = self._rand_min_split_size(self.confs[cover_info['vc_name']]['min_split_size'],
                                                       fallback=True)  # possible value for `--min-split-size`: 1M - 1024M
        fallback_aria2c[9] = "16" if int(mcps) > 16 else mcps  # possible value for `--max-connection-per-server`: 1 - 16

        return cmd_aria2c, fallback_aria2c

    @staticmethod
    def _rm_failed_pieces(episode_dir, pattern='*.aria2'):
        f_progresses = [str(p) for p in Path(episode_dir).glob(pattern)]
        for f_progress in f_progresses:
            f_failed = f_progress.rpartition('.')[0]
            if os.path.isfile(f_failed):
                os.remove(f_failed)
            os.remove(f_progress)

    def dwnld_videos_with_aria2(self, cover_info, save_dir='.', defn=None):
        """
        :returns:
        (abs_cover_dir, [(abs_episode1_dir, [fname1.1.mp4, fname1.2.mp4]),(abs_episode2_dir, [fname2.1.mp4, fname2.2.mp4])])
        """
        def pick_format(formats):
            for fmt in formats:
                if fmt['ext'] != 'ts':
                    return fmt

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
            cover_name = '.'.join([cover_info.get('title') or cover_info['source_name'] + '_' + (cover_info.get('cover_id') or video_list[0]['V']),
                                   (cover_info.get('year') or DEFAULT_YEAR)])
            cover_name = normalize_filename(cover_name, repl='_')
            cover_default_dir = '.'.join([cover_name, cover_info['source_name'] + '_' + cover_info.get('type', VideoTypes.MOVIE)])
            cover_dir = os.path.abspath(os.path.join(save_dir, cover_default_dir))

            urls = []  # URLs file info for aria2c
            episodes = []  # [(abs_episode1_dir, [fname1.1.mp4, fname1.2.mp4]), ]

            ep_fmt_numbering, ep_fmt_width = determine_ep_naming_fmt()

            for vi in video_list:
                if vi.get('defns') and any(vi['defns'].values()):
                    if not (defn and vi['defns'].get(defn)):
                        defn = pick_highest_definition(vi['defns'])
                    if ep_fmt_numbering:
                        ep_name = vi.get('title')
                        ep_name = '-({})'.format(ep_name) if ep_name else ''

                        episode_default_dir = '.'.join(
                            [cover_name, 'EP' + '{:0{width}}'.format(vi['E'], width=ep_fmt_width) + ep_name,
                             'WEBRip', cover_info['source_name'] + '_' + defn])
                    else:
                        episode_default_dir = '.'.join([cover_name, 'WEBRip', cover_info['source_name'] + '_' + defn])
                    episode_dir = os.path.join(cover_dir, episode_default_dir)

                    episode_pattern = episode_default_dir + '.*'
                    downloaded = list(Path(cover_dir).glob(episode_pattern))
                    if len(downloaded) and not os.path.exists(episode_dir):
                        self._logger.warning(f"Already downloaded: {downloaded[0]}")
                        continue
                    self._rm_failed_pieces(episode_dir)

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

            if urllist:
                cmd_aria2c, fallback_aria2c = self._cmd_aria2c(cover_info)
                for _ in range(2):
                    try:
                        with logging_with_pipe(self._logger, level=logging.INFO, text=True) as log_pipe:
                            with subprocess.Popen(cmd_aria2c, bufsize=1, universal_newlines=True, encoding='utf-8',
                                                  stdin=subprocess.PIPE, stdout=log_pipe, stderr=subprocess.STDOUT) as proc:
                                proc.stdin.write(urllist)
                                proc.stdin.close()

                        break
                    except OSError as e:
                        if cmd_aria2c is not fallback_aria2c:
                            self._logger.error("Error while running 'aria2c' with augmented options. OS error number {}: '{}'\n"
                                               "Trying to fall back on standard options...\n".format(e.errno, e.strerror))

                            cmd_aria2c = fallback_aria2c

                if proc and not proc.returncode:
                    return cover_dir, episodes
                else:
                    self._logger.error(f"Download failed: '{cover_info['url']}'.")
                    return "", []

        self._logger.warning("No files to download for '{}'.".format(cover_info['url']))
        return "", []

    def _join_videos_with_ffmpeg_mkvmerge(self, cover_dir, episode_dir, fnames, ts_convert=True):
        """abs_cover_dir > abs_episode_dir > video files """

        if cover_dir and episode_dir and fnames:
            # determine the extension (i.e. video format)
            suffix = '.' + fnames[0].split('.')[-1]
            episode_name = os.path.basename(episode_dir) + suffix
            episode_name = os.path.join(cover_dir, episode_name)

            proc = None
            if suffix in ['.ts', '.265ts', '.mpg', '.mpeg']:
                if suffix in ('.ts', '.265ts'):
                    if not ts_convert:
                        if len(fnames) == 1:
                            # just rename and move it into parent directory, no need to merge
                            fn_whole = os.path.join(episode_dir, fnames[0])
                            shutil.move(fn_whole, episode_name)
                            return True

                        with open(episode_name, 'wb') as tsf:
                            for fn in fnames:
                                fn_abs = os.path.join(episode_dir, fn)
                                with open(fn_abs, 'rb') as f:
                                    tsf.write(f.read())
                                if not self.confs['misc']['delay_delete']:
                                    os.remove(fn_abs)  # timely free up the disk space
                        return True

                    episode_name = episode_name.rpartition('.')[0] + '.mp4'
                ffmpeg = self.confs['progs']['ffmpeg']
                cmd = [ffmpeg, '-y', '-i', 'pipe:0', '-safe', '0', '-c', 'copy', '-hide_banner', episode_name]
                try:
                    with logging_with_pipe(self._logger, level=logging.INFO) as log_pipe:
                        with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log_pipe, stderr=subprocess.STDOUT) as proc:
                            for fn in fnames:
                                fn_abs = os.path.join(episode_dir, fn)
                                with open(fn_abs, 'rb') as f:
                                    try:
                                        proc.stdin.write(f.read())
                                    except IOError as e:
                                        if e.errno == errno.EPIPE or e.errno == errno.EINVAL:
                                            break
                                        else:
                                            raise
                                if not self.confs['misc']['delay_delete']:
                                    os.remove(fn_abs)

                            proc.stdin.close()
                except OSError as e:
                    self._logger.error("OS error number {}: '{}'".format(e.errno, e.strerror))
            else:
                if len(fnames) > 1:
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
                else:
                    # just rename and move it into parent directory, no need to merge or transcode
                    fn_whole = os.path.join(episode_dir, fnames[0])
                    shutil.move(fn_whole, episode_name)

                    return True

            if proc and proc.returncode == 0:
                return True

    def join_videos(self, cover_dir, episodes, ts_convert=True):
        for episode_dir, fnames in episodes:
            if len(fnames) > 0:
                res = self._join_videos_with_ffmpeg_mkvmerge(cover_dir, episode_dir, fnames, ts_convert=ts_convert)
                if res:
                    shutil.rmtree(episode_dir, ignore_errors=True)
                else:
                    self._logger.error('Join videos failed! <{}>'.format(episode_dir))
