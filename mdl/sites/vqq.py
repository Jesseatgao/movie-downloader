import json
import re

from ..commons import VIDEO_DEFINITIONS
from ..commons import VideoTypeCodes as VIDEO_TYPES
from ..videoconfig import VideoConfig
from ..utils import json_path_get


class QQVideoVC(VideoConfig):

    _VIDEO_URL_PATS = [
        {'pat': r'^https?://v\.qq\.com/x/cover/(\w+)\.html',
         'eg': 'https://v.qq.com/x/cover/nhtfh14i9y1egge.html'},  # 'video_cover'
        {'pat': r'^https?://v\.qq\.com/detail/([a-zA-Z0-9])/((?:\1)\w+)\.html',
         'eg': 'https://v.qq.com/detail/n/nhtfh14i9y1egge.html'},  # 'video_detail'
        {'pat': r'^https?://v\.qq\.com/x/cover/(\w+)/(\w+)\.html',
         'eg': 'https://v.qq.com/x/cover/nhtfh14i9y1egge/d00249ld45q.html'}, # 'video_episode'
        {'pat': r'^https?://v\.qq\.com/x/page/(\w+)\.html',
         'eg': 'https://v.qq.com/x/page/d00249ld45q.html'} # 'video_page'
    ]
    SOURCE_NAME = "Tencent"
    _VIP_TOKEN = {}

    _VQQ_TYPE_CODES = {
        1: VIDEO_TYPES.MOVIE,
        2: VIDEO_TYPES.TV
        # default: VideoTypes.TV
    }

    _VQQ_FORMAT_IDS_DEFAULT = {
        'fhd': 10209,
        'shd': 10201,
        'hd': 10212,
        'sd': 10203
    }

    def __init__(self, requester=None):
        super().__init__(requester)

        self._COVER_PAT_RE = re.compile(r"var\s+COVER_INFO\s*=\s*(.+?)var\s+COLUMN_INFO",
                                        re.MULTILINE | re.DOTALL | re.IGNORECASE)
        self._VIDEO_COVER_PREFIX = 'https://v.qq.com/x/cover/'

        # make sure _VIDEO_URL_PATS has a compiled version, which should have been done in @classmethod is_url_valid
        for pat in self._VIDEO_URL_PATS:
            if pat.get('cpat') is None:
                pat['cpat'] = re.compile(pat['pat'], re.IGNORECASE)

    # @classmethod
    # def is_url_valid(cls, url):
    #     return super().is_url_valid(url)

    def get_video_urls(self, vid, definition):
        urls = []
        ext = None
        format_name = None

        params = {
            'isHLS': False,
            'charge': 0,
            'vid': vid,
            'defn': definition,
            'defnpayver': 1,
            'otype': 'json',
            'platform': 10901,
            'sdtfrom': 'v1010',
            'host': 'v.qq.com',
            'fhdswitch': 0,
            'show1080p': 1,
        }
        r = self._requester.get('https://h5vv.video.qq.com/getinfo', params=params)
        if r.status_code == 200:
            try:
                data = json.loads(r.text[len('QZOutputJson='):-1])
            except json.JSONDecodeError:
                # logging
                return None, None, []

            if data:
                url_prefixes = []
                for url_dic in json_path_get(data, ['vl', 'vi', 0, 'ul', 'ui'], []):
                    if isinstance(url_dic, dict):
                        url = url_dic.get('url')
                        if url:
                            url_prefixes.append(url)

                if json_path_get(data, ['vl', 'vi', 0, 'drm']) == 0:  # DRM-free only, for now
                    for fmt_info in json_path_get(data, ['fl', 'fi'], []):
                        if isinstance(fmt_info, dict) and fmt_info.get('name') == definition:
                            format_id = fmt_info.get('id', self._VQQ_FORMAT_IDS_DEFAULT[definition])
                            vfilename = json_path_get(data, ['vl', 'vi', 0, 'fn'], '')
                            vfn = vfilename.split('.')  # e.g. ['egmovie', 'p201', 'mp4']
                            if len(vfn) != 3:
                                break
                            ext = vfn[-1]  # video extension, e.g. 'mp4'
                            vfmt = vfn[1]  # e.g. 'p201'
                            fmt_prefix = vfmt[0]  # e.g. 'p' in 'p201'
                            vfmt_new = fmt_prefix + str(format_id % 10000)

                            for chapter in json_path_get(data, ['vl', 'vi', 0, 'cl', 'ci'], []):
                                if isinstance(chapter, dict):
                                    keyid = chapter.get('keyid', '')
                                    keyid_new = keyid.split('.')
                                    if len(keyid_new) != 3:
                                        break
                                    keyid_new[1] = vfmt_new
                                    keyid_new = '.'.join(keyid_new)
                                    cfilename = keyid_new + '.' + ext
                                    params = {
                                        'otype': 'json',
                                        'vid': vid,
                                        'format': format_id,
                                        'filename': cfilename,
                                        'platform': 10901,
                                        'vt': 217,
                                        'charge': 0,
                                    }
                                    r = self._requester.get('https://h5vv.video.qq.com/getkey', params=params)
                                    if r.status_code == 200:
                                        try:
                                            key_data = json.loads(r.text[len('QZOutputJson='):-1])
                                        except json.JSONDecodeError:
                                            # logging
                                            return None, None, []

                                        if key_data and isinstance(key_data, dict) and key_data.get('key'):
                                            url_mirrors = '\t'.join(['%s%s?sdtfrom=v1010&vkey=%s' % (url_prefix, cfilename, key_data['key'])
                                                                    for url_prefix in url_prefixes])
                                            if url_mirrors:
                                                urls.append(url_mirrors)

                            # check if the URLs for the file parts have all been successfully obtained
                            if json_path_get(data, ['vl', 'vi', 0, 'cl', 'fc']) == len(urls):
                                format_name = fmt_info['name']

                            break

        return format_name, ext, urls

    def get_cover_info(self, cover_url):
        """"{
        "title":"" ,
        "year":"",
        "type":VideoTypes.TV,
        "cover_id":"",
        "normal_ids": [{
            "V": "d00249ld45q",
            "E": 1
        }, {
            "V": "q0024a27g9j",
            "E": 2
        }]
        }"""

        info = None

        r = self._requester.get(cover_url)
        if r.status_code == 200:
            r.encoding = 'utf-8'
            cover_match = self._COVER_PAT_RE.search(r.text)
            if cover_match:
                info = {}
                cover_group = cover_match.group(1).strip()
                try:
                    cover_info = json.loads(cover_group)
                except json.JSONDecodeError:
                    return None
                if cover_info and isinstance(cover_info, dict):
                    #video_ids = cover_info.get('video_ids') #cover_info['video_ids']
                    info['title'] = cover_info.get('title')
                    info['year'] = cover_info.get('year')
                    info['type'] = self._VQQ_TYPE_CODES.get(cover_info.get('typeid'), VIDEO_TYPES.TV)
                    info['cover_id'] = cover_info.get('cover_id')
                    normal_ids = cover_info.get('nomal_ids')
                    for d in normal_ids:
                        del d['F']
                    info['normal_ids'] = normal_ids

        return info


    def get_video_info(self, videourl):
        cover_info = None
        for typ, pat in enumerate(self._VIDEO_URL_PATS, 1):
            match = pat['cpat'].match(videourl)
            if match:
                if typ == 1:  # 'video_cover'
                    cover_info = self.get_cover_info(videourl)
                    break
                elif typ == 2:  # 'video_detail'
                    cover_id = match.group(2)
                    cover_url = self._VIDEO_COVER_PREFIX + cover_id + '.html'
                    cover_info = self.get_cover_info(cover_url)
                    break
                elif typ == 3:  # 'video_episode'
                    cover_id = match.group(1)
                    video_id = match.group(2)
                    cover_url = self._VIDEO_COVER_PREFIX + cover_id + '.html'
                    cover_info = self.get_cover_info(cover_url)
                    cover_info['normal_ids'] = [dic for dic in cover_info['normal_ids'] if dic['V'] == video_id]
                    break
                else:  # typ == 4 'video_page'
                    video_id = match.group(1)
                    cover_info = self.get_cover_info(videourl)
                    cover_info['normal_ids'] = [dic for dic in cover_info['normal_ids'] if dic['V'] == video_id]
                    break

        return cover_info


    def update_video_dwnld_info(self, coverinfo):
        """"
        {
            "title": "李师师",
            "year": "1989",
            "cover_id": "nhtfh14i9y1egge",
            "normal_ids": [{
                "V": "d00249ld45q",
                "E": 1,
                "defns": {
                    "hd": [{
                        "ext": "mp4",
                        "urls": ["https: //t.com/hdv1.1.mp4", "https://t.com/hdv1.2.mp4"]
                    }],
                    "sd": [{
                        "ext": "mp4",
                        "urls": ["https: //t.com/sdv1.1.mp4", "https://t.com/sdv1.2.mp4"]
                    }, {
                        "ext": "ts",
                        "urls": ["https: //t.com/sdv1.1.ts", "https://t.com/sdv1.2.ts"]
                    }]
                }
            }, {
                "V": "q0024a27g9j",
                "E": 2,
                "defns": {
                    "hd": [{
                        "ext": "mp4",
                        "urls": ["https: //t.com/hdv2.1.mp4", "https://t.com/hdv2.2.mp4"]
                    }],
                    "sd": [{
                        "ext": "mp4",
                        "urls": ["https: //t.com/sdv2.1.mp4", "https://t.com/sdv2.2.mp4"]
                    }, {
                        "ext": "ts",
                        "urls": ["https: //t.com/sdv2.1.ts", "https://t.com/sdv2.2.ts"]
                    }]
                }
            }]
        }
        """
        for vi in coverinfo['normal_ids']:
            if vi.get('defns') is None:
                vi['defns'] = {}

            for definition in VIDEO_DEFINITIONS:
                format_name, ext, urls = self.get_video_urls(vi['V'], definition)
                if format_name:  # same as definition
                    if format_name not in vi['defns'].keys():
                        vi['defns'][format_name] = []
                    fmt = dict(ext=ext, urls=urls)
                    vi['defns'][format_name].append(fmt)

    def get_video_config_info(self, url):
        config_info = self.get_video_info(url)
        if config_info:
            self.update_video_dwnld_info(config_info)

        return config_info


"""
def dump_videos_urls2files(coverinfo):
    """"""
    cover_dir = (coverinfo['title'] or '') + '_' + (coverinfo['year'] or '') + '_' + coverinfo['cover_id']
    try:
        os.mkdir(cover_dir)
    except FileExistsError:
        pass

    for vi in coverinfo['normal_ids']:
        for defn in ('fhd', 'shd', 'hd', 'sd'):
            if defn in vi['defns']:
                episode_fn = '_'.join(['ep' + "{:02}".format(vi['E']), vi['V'], defn])
                # episode_fn += '.txt'
                try:
                    with open('/'.join([cover_dir, episode_fn]), mode='wt') as f:
                        fns = []
                        f.write('URLs:\n\n')
                        for url in vi[defn]:
                            f.write(url)
                            f.write('\n')

                            match = re.search(r'/([a-zA-Z0-9\.]+)\?', url)
                            if match:
                                fn = match.group(1)
                                fns.append(fn)

                        if len(fns) >= 1:
                            cmd_str = 'mp4box -add ' + fns[0]
                            ext = fns[0].split('.')[-1]

                            for i in range(1, len(fns)):
                                cmd_str += ' -cat ' + fns[i]
                            cmd_str += ' ' + episode_fn + '.' + ext

                            f.write('\n\nJoiner:\n\n')
                            f.write(cmd_str)

                except FileExistsError:
                    pass

                break

"""

