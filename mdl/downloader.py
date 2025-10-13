import os
import subprocess
import shutil
import errno
import logging
from math import trunc, log10, ceil
import random
from pathlib import Path
import glob

from certifi import where

from .commons import pick_highest_definition, VideoTypes, DEFAULT_YEAR
from .sites import get_all_sites_vcs
from .utils import logging_with_pipe, normalize_filename, json_path_get


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
                cover_dir, episodes = self.dwnld_videos_with_aria2(batch_cover_info, vci.confs)

                self.join_videos(cover_dir, episodes, vci.confs)

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

    def _determine_ep_naming_fmt(self, cover_info):
        width = 2  # default episode numbering format width
        total_ep = cover_info.get('episode_all')
        if total_ep:
            ndigits = trunc(log10(total_ep)) + 1
            width = ndigits

        normal_ids = cover_info.get('normal_ids', [])
        ep_cnt = sum([1 for vi in normal_ids if vi.get('defns') and any(vi['defns'].values())])  # number of valid episodes
        numbering = False if (total_ep and total_ep == 1) or (not total_ep and ep_cnt == 1) else True

        return numbering, width

    def _cover_naming(self, cover_info, save_dir):
        cover_name = '.'.join([cover_info.get('title') or (cover_info['source_name'] + '_' + (
                    cover_info.get('cover_id') or json_path_get(cover_info, ['normal_ids', 0, 'V'], ''))),
                               (cover_info.get('year') or DEFAULT_YEAR)])
        cover_name = normalize_filename(cover_name, repl='_')
        cover_default_dir = '.'.join(
            [cover_name, cover_info['source_name'] + '_' + cover_info.get('type', VideoTypes.MOVIE)])
        cover_dir = os.path.abspath(os.path.join(save_dir, cover_default_dir))

        return cover_name, cover_dir

    def _episode_naming(self, vi, cover_name, cover_dir, source_name, ep_fmt_numbering, ep_fmt_width, defn=''):
        if ep_fmt_numbering:
            ep_name = vi.get('title')
            ep_name = '-({})'.format(ep_name) if ep_name else ''

            episode_default_dir = '.'.join(
                [cover_name, 'EP' + '{:0{width}}'.format(vi['E'], width=ep_fmt_width) + ep_name,
                 'WEBRip', source_name + '_' + defn])
        else:
            episode_default_dir = '.'.join([cover_name, 'WEBRip', source_name + '_' + defn])
        episode_dir = os.path.join(cover_dir, episode_default_dir)

        return episode_default_dir, episode_dir

    def dwnld_videos_with_aria2(self, cover_info, vc_confs):
        """
        :returns:
        (abs_cover_dir, [(abs_episode1_dir, [fname1.1.mp4, fname1.2.mp4]),(abs_episode2_dir, [fname2.1.mp4, fname2.2.mp4])])
        """
        def pick_format(formats):
            for fmt in formats:
                if fmt['ext'] != 'ts':
                    return fmt

            return formats[0]

        video_list = cover_info.get('normal_ids')
        if video_list:
            save_dir = vc_confs['dir']
            orig_defn = vc_confs['definition']
            ts_convert = vc_confs['ts_convert']

            urls = []  # URLs file info for aria2c
            episodes = []  # [(abs_episode1_dir, [fname1.1.mp4, fname1.2.mp4]), ]

            cover_name, cover_dir = self._cover_naming(cover_info, save_dir)
            ep_fmt_numbering, ep_fmt_width = self._determine_ep_naming_fmt(cover_info)

            for vi in video_list:
                if vi.get('defns') and any(vi['defns'].values()):
                    defn = orig_defn
                    if not (defn and vi['defns'].get(defn)):
                        defn = pick_highest_definition(vi['defns'])

                    format = pick_format(vi['defns'][defn])
                    ext = format['ext']

                    episode_default_dir, episode_dir = self._episode_naming(vi, cover_name, cover_dir,
                                                                            cover_info['source_name'], ep_fmt_numbering,
                                                                            ep_fmt_width, defn=defn)

                    episode_pattern = glob.escape(episode_default_dir) + '.*'
                    downloaded = [str(ep) for ep in Path(cover_dir).glob(episode_pattern)]
                    exts = {ep.rpartition('.')[-1] for ep in downloaded}
                    if len(downloaded) and not os.path.exists(episode_dir) and (
                            (ext != 'ts' and 'mkv' in exts) or (ext == 'ts' and ts_convert and 'mp4' in exts) or (
                            ext == 'ts' and not ts_convert and 'ts' in exts)):
                        self._logger.warning(f"Already downloaded: {downloaded}")
                        continue
                    self._rm_failed_pieces(episode_dir)

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
                    proc = None
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

    def _join_ts(self, cover_dir, episode_dir, fnames):
        episode_name = episode_dir + '.ts'

        if len(fnames) == 1:
            # just rename and move it into parent directory, no need to merge
            fn_whole = os.path.join(episode_dir, fnames[0])
            shutil.move(fn_whole, episode_name)
            return

        with open(episode_name, 'wb') as tsf:
            for fn in fnames:
                fn_abs = os.path.join(episode_dir, fn)
                with open(fn_abs, 'rb') as f:
                    tsf.write(f.read())
                if not self.confs['misc']['delay_delete']:
                    os.remove(fn_abs)  # timely free up the disk space

    def _join_with_ffmpeg(self, cover_dir, episode_dir, fnames, ts_convert=True):
        # determine the extension (i.e. video format): ['.ts',]
        suffix = '.' + fnames[0].split('.')[-1]
        episode_name = os.path.basename(episode_dir) + suffix
        episode_name = os.path.join(cover_dir, episode_name)

        try:
            if suffix == '.ts':
                if not ts_convert:
                    self._join_ts(cover_dir, episode_dir, fnames)
                    return True

                episode_name = episode_name.rpartition('.')[0] + '.mp4'

            ffmpeg = self.confs['progs']['ffmpeg']
            cmd_ffmpeg = [ffmpeg, '-y', '-i', 'pipe:0', '-safe', '0', '-c', 'copy', '-hide_banner', episode_name]
            with logging_with_pipe(self._logger, level=logging.INFO) as log_pipe:
                with subprocess.Popen(cmd_ffmpeg, stdin=subprocess.PIPE, stdout=log_pipe,
                                      stderr=subprocess.STDOUT) as proc:
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

            if proc and proc.returncode == 0:
                return True

            # fall back on merging when converting failed
            if suffix == '.ts' and self.confs['misc']['delay_delete']:
                self._logger.warning("Conversion to '%s' failed, switching to TS merging...", episode_name)
                self._join_ts(cover_dir, episode_dir, fnames)
                if os.path.isfile(episode_name):
                    os.remove(episode_name)
                return True
        except OSError as e:
            self._logger.error("OS error number {}: '{}'".format(e.errno, e.strerror))

    def _join_with_mkvmerge(self, cover_dir, episode_dir, fnames):
        # determine the extension (i.e. video format)
        suffix = '.' + fnames[0].split('.')[-1]
        episode_name = os.path.basename(episode_dir) + suffix
        episode_name = os.path.join(cover_dir, episode_name)

        if len(fnames) == 1:
            # just rename and move it into parent directory, no need to merge or transcode
            fn_whole = os.path.join(episode_dir, fnames[0])
            shutil.move(fn_whole, episode_name)

            return True

        '''
        flist = ["file '{}'".format(os.path.join(episodedir, fn)) for fn in fnames]
        flist = '\n'.join(flist)

        cmd_ffmpeg = ['ffmpeg', '-y', '-safe', '0', '-protocol_whitelist', 'file,pipe', '-f', 'concat',
               '-i', 'pipe:0', '-c', 'copy', '-hide_banner', episode_name]
        cp = subprocess.run(cmd_ffmpeg, input=flist.encode('utf-8'))
        '''
        flist = ["{}".format(os.path.join(episode_dir, fn)) for fn in fnames]
        episode_name = episode_name.rpartition('.')[0] + '.mkv'

        proc = None
        mkvmerge = self.confs['progs']['mkvmerge']
        cmd_mkvmerge = [mkvmerge, '-o', episode_name, '['] + flist + [']']
        try:
            with logging_with_pipe(self._logger, level=logging.INFO, text=True) as log_pipe:
                with subprocess.Popen(cmd_mkvmerge, bufsize=1, universal_newlines=True, encoding='utf-8',
                                      stdout=log_pipe, stderr=subprocess.STDOUT) as proc:
                    pass

            if proc and proc.returncode == 0:
                return True
        except OSError as e:
            self._logger.error("OS error number {}: '{}'".format(e.errno, e.strerror))

    def join_videos(self, cover_dir, episodes, vc_confs):
        if not vc_confs['merge_all']:
            return

        for episode_dir, fnames in episodes:
            suffix = '.' + fnames[0].split('.')[-1]

            if suffix == '.ts':
                res = self._join_with_ffmpeg(cover_dir, episode_dir, fnames, ts_convert=vc_confs['ts_convert'])
            else:
                res = self._join_with_mkvmerge(cover_dir, episode_dir, fnames)

            if res:
                shutil.rmtree(episode_dir, ignore_errors=True)
            else:
                self._logger.error('Join videos failed! <{}>'.format(episode_dir))
