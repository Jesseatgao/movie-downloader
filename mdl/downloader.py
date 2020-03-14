import os
import subprocess
import tempfile
import shutil

# from requests.exceptions import ConnectionError, Timeout
# import requests

from .commons import VIDEO_DEFINITIONS
from .commons import VideoTypeCodes as VIDEO_TYPES
from .sites import get_all_sites_vcs
from .utils import requests_retry_session
from .utils import retry


class MDownloader(object):
    def __init__(self, args=None):
        self._requester = requests_retry_session()
        self._vcs = get_all_sites_vcs()
        # self._args = args  # taken from sys.argv
        opts = {
            'save_dir': '.',
            'definition': None
        }
        proxies = {}
        if args:
            if args.dir:
                opts['save_dir'] = args.dir
            if args.definition:
                opts['definition'] = args.definition
            if args.proxy:
                proxies = dict(http=args.proxy, https=args.proxy)

        self._opts = opts
        self._requester.proxies = proxies

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0',
            #'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
            'Accept-Encoding': 'gzip, identity, deflate, br, *'
        }
        self._requester.headers = headers

    @retry(Exception)
    def get(self, url, params=None, timeout=3.5, **kwargs):
        return self._requester.get(url, params=params, timeout=timeout, **kwargs)

    def download(self, urls):
        for url in urls:
            config_info = self.extract_config_info(url)
            if config_info:
                cover_dir, episodes = self.dwnld_videos_with_aria2(
                    config_info, savedir=self._opts['save_dir'], defn=self._opts['definition'])
                self.join_videos(cover_dir, episodes)

    def extract_config_info(self, url):
        for name, vc in self._vcs.items():
            vcc = vc['class']
            if not vcc.is_url_valid(url):
                continue

            vci = vc.get('instance')
            if vci is None:
                vci = vcc(self)
                vc['instance'] = vci

            config_info = vci.get_video_config_info(url)
            if config_info:
                config_info["source_name"] = vcc.SOURCE_NAME
            return config_info
        else:
            # check site domain name against URL
            print("Video URL {!r} is invalid".format(url))  # logging
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
            cover_name = '.'.join([configinfo.get('title', configinfo['source_name'] + '_' + configinfo.get('cover_id', '')),
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
            mod_dir = os.path.dirname(os.path.abspath(__file__))
            cert_path = os.path.join(mod_dir, '3rd-parties/aria2/ca-bundle.crt')
            cmd_aria2c = ['aria2c', '-c', '-j5', '-k128K', '-s128', '-x128', '-m1000', '--retry-wait', '5',
                          '--lowest-speed-limit', '10K', '--no-conf', '-i-', '--console-log-level', 'warn',
                          '--download-result', 'hide', '--summary-interval', '0', '--ca-certificate',
                          cert_path]
            cp = subprocess.run(cmd_aria2c, input=urllist.encode('utf-8'))
            if not cp.returncode:
                return cover_dir, episodes
        else:
            # logging
            print("No files to download.")

        return "", []

    def join_videos_with_ffmpeg(self, coverdir, episodedir, fnames):
        """abs_cover_dir > abs_episode_dir > video files """

        if coverdir and episodedir and fnames:
            # determine the extension (i.e. video format)
            suffix = '.' + fnames[0].split('.')[-1]
            episode_name = os.path.basename(episodedir) + suffix
            episode_name = os.path.join(coverdir, episode_name)

            cp = None
            if suffix in ['.ts']:  # ['.ts', '.mpg', '.mpeg']
                with tempfile.TemporaryFile(mode='w+b', suffix=suffix, dir=coverdir) as tmpf:
                    for fn in fnames:
                        with open(os.path.join(episodedir, fn), 'rb') as f:
                            tmpf.write(f.read())
                    tmpf.flush()
                    tmpf.seek(0)

                    if suffix == '.ts':
                        episode_name = episode_name.replace('.ts', '.mp4')

                    cmd = ['ffmpeg', '-y', '-i', 'pipe:0', '-safe', '0', '-c', 'copy', '-hide_banner', episode_name]
                    cp = subprocess.run(cmd, input=tmpf.read())
            else:
                flist = ["file '{}'".format(os.path.join(episodedir, fn)) for fn in fnames]
                flist = '\n'.join(flist)

                cmd = ['ffmpeg', '-y', '-safe', '0', '-protocol_whitelist', 'file,pipe', '-f', 'concat',
                       '-i', 'pipe:0', '-c', 'copy', '-hide_banner', episode_name]
                cp = subprocess.run(cmd, input=flist.encode('utf-8'))

            if cp and cp.returncode == 0:
                return True


    def join_videos(self, coverdir, episodes):
        for episode_dir, fnames in episodes:
            if len(fnames) > 1:
                res = self.join_videos_with_ffmpeg(coverdir, episode_dir, fnames)
                if res:
                    shutil.rmtree(episode_dir, ignore_errors=True)
                else:
                    print('Join videos failed! <{}>\n'.format(episode_dir))


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
