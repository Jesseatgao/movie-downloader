import os
import subprocess
import tempfile
import shutil
import errno
import logging
from time import sleep

# from requests.exceptions import ConnectionError, Timeout
# import requests

from .commons import VIDEO_DEFINITIONS
from .commons import VideoTypeCodes as VIDEO_TYPES
from .sites import get_all_sites_vcs
# from .utils import RequestsWrapper
from .utils import requests_retry_session
from .utils import logging_with_pipe


class MDownloader(object):
    def __init__(self, args=None, confs=None):
        self._vcs = get_all_sites_vcs()
        self.args = args
        self.confs = confs

        logger_name = '.'.join(['MDL', 'MDownloader'])  # 'MDL.MDownloader'
        self._logger = logging.getLogger(logger_name)

    def download(self, urls):
        for url in urls:
            config_info = self.extract_config_info(url)
            if config_info:
                cover_dir, episodes = self.dwnld_videos_with_aria2(
                    config_info, savedir=self.confs[config_info["vc_name"]]["dir"],
                    defn=self.confs[config_info["vc_name"]]['definition'])
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

            config_info = vci.get_video_config_info(url)
            if config_info:
                config_info["source_name"] = vcc.SOURCE_NAME
                config_info["vc_name"] = vcc.VC_NAME
            return config_info
        else:
            # check site domain name against URL
            self._logger.error("Video URL {!r} is invalid".format(url))
            return None

    def dwnld_videos_with_aria2(self, configinfo, savedir='.', defn=None):
        '''
        :return:
        (abs_cover_dir, [(abs_episode1_dir, [fname1.1.mp4, fname1.2.mp4]),(abs_episode2_dir, [fname2.1.mp4, fname2.2.mp4])])
        '''

        def pick_highest_definition(defns):
            for definition in VIDEO_DEFINITIONS:
                if defns.get(definition):
                    return definition

        def pick_format(formats):
            for format in formats:
                if format['ext'] != 'ts':
                    return format

            return formats[0]

        video_list = configinfo.get('normal_ids', [])
        if video_list:
            cover_name = '.'.join([configinfo.get('title') if configinfo.get('title') else configinfo['source_name'] + '_' + configinfo.get('cover_id', ''),
                                   configinfo.get('year', '1900')])
            cover_default_dir = '.'.join([cover_name, configinfo.get('type', VIDEO_TYPES.MOVIE).value])
            cover_dir = os.path.abspath(os.path.join(savedir, cover_default_dir))

            urls = []  # URLs file info for aria2c
            episodes = []  # [(abs_episode1_dir, [fname1.1.mp4, fname1.2.mp4]), ]

            # number of valid episodes
            ep_num = sum([1 for vi in video_list if vi.get('defns') if any(vi['defns'].values())])

            for vi in video_list:
                if vi.get('defns') and any(vi['defns'].values()):
                    if not (defn and vi['defns'].get(defn)):
                        defn = pick_highest_definition(vi['defns'])
                    if configinfo['type'] == VIDEO_TYPES.MOVIE and ep_num == 1:
                        episode_default_dir = '.'.join([cover_name, 'WEBRip', configinfo['source_name'] + '_' + defn])
                    else:  # VIDEO_TYPES.TV or (VIDEO_TYPES.MOVIE and ep_num > 1)
                        episode_default_dir = '.'.join([cover_name, 'EP' + '{:02}'.format(vi['E']), 'WEBRip',
                                                        configinfo['source_name'] + '_' + defn])
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

            aria2c = self.confs['progs']['aria2c']
            mod_dir = os.path.dirname(os.path.abspath(__file__))
            cert_path = os.path.join(mod_dir, 'third_parties/aria2/ca-bundle.crt')
            # user_agent_qq = 'MQQBrowser/26 MicroMessenger/5.4.1 Mozilla/5.0 (Linux; U; Android 2.3.7; zh-cn; MB200 Build/GRJ22; CyanogenMod-7) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1'
            user_agent = 'Mozilla/5.0 (Linux; U; Android 2.3.7; zh-cn) AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1'
            proxy = self.confs[configinfo['vc_name']]['proxy'] \
                if self.confs[configinfo['vc_name']]['enable_proxy_dl_video'].lower() == "true" else ''

            cmd_aria2c = [aria2c, '-c', '-j5', '-k128K', '-s128', '-x128', '--max-file-not-found=5000', '-m0',
                          '--retry-wait=5', '--lowest-speed-limit=10K', '--no-conf', '-i-', '--console-log-level=warn',
                          '--download-result=hide', '--summary-interval=0', '--stream-piece-selector=inorder',
                          '--ca-certificate', cert_path, '--retry-on-400=true', '--retry-on-403=true',
                          '--retry-on-406=true', '--retry-on-unknown=true', '-U', user_agent, '--all-proxy', proxy]
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
            self._logger.warning("No files to download.")

        return "", []

    def join_videos_with_ffmpeg_mkvmerge(self, coverdir, episodedir, fnames):
        """abs_cover_dir > abs_episode_dir > video files """

        if coverdir and episodedir and fnames:
            # determine the extension (i.e. video format)
            suffix = '.' + fnames[0].split('.')[-1]
            episode_name = os.path.basename(episodedir) + suffix
            episode_name = os.path.join(coverdir, episode_name)

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
                                with open(os.path.join(episodedir, fn), 'rb') as f:
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
                flist = ["{}".format(os.path.join(episodedir, fn)) for fn in fnames]
                episode_name = episode_name.rpartition('.')[0] + '.mkv'

                mkvmerge = self.confs['progs']['mkvmerge']
                cmd = [mkvmerge, '-o', episode_name] + ' + '.join(flist).split()
                try:
                    with logging_with_pipe(self._logger, level=logging.INFO, text=True) as log_pipe:
                        with subprocess.Popen(cmd, bufsize=1, text=True, encoding='utf-8',
                                              stdout=log_pipe, stderr=subprocess.STDOUT) as proc:
                            pass
                except OSError as e:
                    self._logger.error("OS error number {}: '{}'".format(e.errno, e.strerror))

            if proc and proc.returncode == 0:
                return True

    def join_videos(self, coverdir, episodes):
        for episode_dir, fnames in episodes:
            if len(fnames) > 0:
                res = self.join_videos_with_ffmpeg_mkvmerge(coverdir, episode_dir, fnames)
                if res:
                    shutil.rmtree(episode_dir, ignore_errors=True)
                else:
                    self._logger.error('Join videos failed! <{}>'.format(episode_dir))


    '''
    def dwnld_video_with_progressbar(self, url, fn):
        resp = requests.get(url, allow_redirects=True, stream=True)
        if resp.status_code == 200:
            try:
                with open(fn, 'wb') as f:
                    total_length = resp.headers.get('content-length')
                    if total_length:
                        dl = 0
                        total_length = int(total_length)
                        for data in resp.iter_content(chunk_size=4096):
                            dl += len(data)
                            f.write(data)
                            done = int(50 * dl / total_length)
                            sys.stdout.write("\r[%s%s] %d/%d" % ('=' * done, ' ' * (50 - done), dl, total_length))
                            sys.stdout.flush()
                    else:  # no content length header
                        f.write(resp.content)
    
            except OSError as e:
                print('File error: {}. {}'.format(fn, e))  # logging
    
    
    def dwnld_videos_with_requests(self, coverinfo, savedir='.'):
        cover_dir = os.path.join(savedir, coverinfo['default_dir'])
        try:
            os.mkdir(cover_dir)
        except FileExistsError:
            pass
    
        for vi in coverinfo['normal_ids']:
            if vi['defns']:
                defn = vi['defns'][0]  # Highest definition
                episode_dir = os.path.join(cover_dir, vi['default_dir'][defn])
                try:
                    os.mkdir(episode_dir)
                except FileExistsError:
                    pass
    
                for url in vi[defn]:
                    match = re.search(r'/([a-zA-Z0-9\.]+)\?', url)
                    if match:
                        fn = match.group(1)
                    else:
                        continue  # logging, shouldn't go here
    
                    fn = os.path.join(episode_dir, fn)
                    dwnld_video_with_progressbar(url, fn)
    '''
