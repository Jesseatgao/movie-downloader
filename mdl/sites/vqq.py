import json
import re
import random
import string

from ..commons import VideoTypeCodes, VideoTypes
from ..videoconfig import VideoConfig
from ..utils import json_path_get, build_cookiejar_from_kvp


class QQVideoPlatforms:
    P10901 = '11'
    P10801 = '10801'  # '10601'


class QQVideoVC(VideoConfig):

    _VIDEO_URL_PATS = [
        {'pat': r'^https?://v\.qq\.com/x/cover/(\w+)\.html',
         'eg': 'https://v.qq.com/x/cover/nhtfh14i9y1egge.html'},  # 'video_cover'
        {'pat': r'^https?://v\.qq\.com/detail/([a-zA-Z0-9])/((?:\1)\w+)\.html',
         'eg': 'https://v.qq.com/detail/n/nhtfh14i9y1egge.html'},  # 'video_detail'
        {'pat': r'^https?://v\.qq\.com/x/cover/(\w+)/(\w+)\.html',
         'eg': 'https://v.qq.com/x/cover/nhtfh14i9y1egge/d00249ld45q.html'},  # 'video_episode'
        {'pat': r'^https?://v\.qq\.com/x/page/(\w+)\.html',
         'eg': 'https://v.qq.com/x/page/d00249ld45q.html'}  # 'video_page'
    ]
    SOURCE_NAME = "Tencent"
    VC_NAME = "QQVideo"
    # _VIP_TOKEN = {}

    _VQQ_TYPE_CODES = {
        VideoTypeCodes.MOVIE: VideoTypes.MOVIE,
        VideoTypeCodes.TV: VideoTypes.TV,
        VideoTypeCodes.CARTOON: VideoTypes.CARTOON,
        VideoTypeCodes.SPORTS: VideoTypes.SPORTS,
        VideoTypeCodes.ENTMT: VideoTypes.ENTMT,
        VideoTypeCodes.GAME: VideoTypes.GAME,
        VideoTypeCodes.DOCU: VideoTypes.DOCU,
        VideoTypeCodes.VARIETY: VideoTypes.VARIETY,
        VideoTypeCodes.MUSIC: VideoTypes.MUSIC,
        VideoTypeCodes.NEWS: VideoTypes.NEWS,
        VideoTypeCodes.FINANCE: VideoTypes.FINANCE,
        VideoTypeCodes.FASHION: VideoTypes.FASHION,
        VideoTypeCodes.TRAVEL: VideoTypes.TRAVEL,
        VideoTypeCodes.EDUCATION: VideoTypes.EDUCATION,
        VideoTypeCodes.TECH: VideoTypes.TECH,
        VideoTypeCodes.AUTO: VideoTypes.AUTO,
        VideoTypeCodes.HOUSE: VideoTypes.HOUSE,
        VideoTypeCodes.LIFE: VideoTypes.LIFE,
        VideoTypeCodes.FUN: VideoTypes.FUN,
        VideoTypeCodes.BABY: VideoTypes.BABY,
        VideoTypeCodes.CHILD: VideoTypes.CHILD,
        VideoTypeCodes.ART: VideoTypes.ART
        # default: VideoTypes.MOVIE
    }

    _VQQ_FORMAT_IDS_DEFAULT = {
        QQVideoPlatforms.P10901: {
            'fhd': 10209,
            'shd': 10201,
            'hd': 10212,  # 10202
            'sd': 10203
        },
        QQVideoPlatforms.P10801: {
            'fhd': 321004,
            'shd': 321003,
            'hd': 321002,
            'sd': 321001
        }
    }

    _VQQ_FMT2DEFN_MAP = {10209: 'fhd', 10201: 'shd', 10212: 'hd', 10203: 'sd',
                         321004: 'fhd', 321003: 'shd', 321002: 'hd', 321001: 'sd',
                         320090: 'hd', 320089: 'sd'}

    def __init__(self, requester, args, confs):
        super().__init__(requester, args, confs)

        self._COVER_PAT_RE = re.compile(r"var\s+COVER_INFO\s*=\s*(.+?);?var\s+COLUMN_INFO",
                                        re.MULTILINE | re.DOTALL | re.IGNORECASE)
        self._VIDEO_INFO_RE = re.compile(r"var\s+VIDEO_INFO\s*=\s*(.+?);?</script>"
                                         r"|\"storeEpisodeSinglePlay\".+?\"item_params\"\s*:\s*({.+?})",
                                         re.MULTILINE | re.DOTALL | re.IGNORECASE)
        self._VIDEO_COVER_PREFIX = 'https://v.qq.com/x/cover/'

        # make sure _VIDEO_URL_PATS has a compiled version, which should have been done in @classmethod is_url_valid
        for pat in self._VIDEO_URL_PATS:
            if pat.get('cpat') is None:
                pat['cpat'] = re.compile(pat['pat'], re.IGNORECASE)

        # get user tokens/cookies from configuration file
        self._regular_token = build_cookiejar_from_kvp(confs[self.VC_NAME]['regular_user_token'])
        self._vip_token = build_cookiejar_from_kvp(confs[self.VC_NAME]['vip_user_token'])
        self.user_token = self._vip_token if self._vip_token else self._regular_token
        self.has_vip = True if self._vip_token else False

        # parse cmdline args and config file for "QQVideo" site
        no_logo_default = 'True'
        no_logo = args.QQVideo_no_logo or confs[self.VC_NAME]['no_logo'] or no_logo_default
        self.no_logo = True if no_logo.lower() == 'true' else False

        use_cdn = confs[self.VC_NAME].get('use_cdn')
        self.use_cdn = True if use_cdn and use_cdn.lower() == 'true' else False

        cdn_blacklist = confs[self.VC_NAME].get('cdn_blacklist')
        self.cdn_blacklist = tuple(cdn_blacklist.split()) if cdn_blacklist else ()

        self.preferred_defn = confs[self.VC_NAME]['definition']

    # @classmethod
    # def is_url_valid(cls, url):
    #     return super().is_url_valid(url)

    def _get_video_urls_p10801(self, vid, definition):
        urls = []
        ext = None
        format_name = None

        params = {
            'vid': vid,
            'defn': definition,
            'otype': 'json',
            'platform': QQVideoPlatforms.P10801,
            'fhdswitch': 1,
            'show1080p': 1,
            'dtype': 3
        }
        r = self._requester.get('https://vv.video.qq.com/getinfo', params=params, cookies=self.user_token)
        if r.status_code == 200:
            try:
                data = json.loads(r.text[len('QZOutputJson='):-1])
            except json.JSONDecodeError:
                # logging
                return format_name, ext, urls

            if data:
                url_prefixes = []
                for url_dic in json_path_get(data, ['vl', 'vi', 0, 'ul', 'ui'], []):
                    if isinstance(url_dic, dict):
                        url = url_dic.get('url')
                        if url and not url.startswith(self.cdn_blacklist):
                            url_prefixes.append(url)

                chosen_url_prefixes = [prefix for prefix in url_prefixes if prefix[:prefix.find('/', 8)].endswith('.tc.qq.com')]
                if not chosen_url_prefixes:
                    chosen_url_prefixes = url_prefixes

                if self.use_cdn:
                    # use all URL prefixes but with default servers coming before CDN mirrors
                    cdn = [prefix for prefix in url_prefixes if prefix not in chosen_url_prefixes]
                    chosen_url_prefixes += cdn

                drm = json_path_get(data, ['vl', 'vi', 0, 'drm'])
                preview = data.get('preview')

                formats = {str(fmt.get('id')): fmt.get('name') for fmt in json_path_get(data, ['fl', 'fi'], [])}
                keyid = json_path_get(data, ['vl', 'vi', 0, 'keyid'], '')
                format_id = keyid.split('.')[-1]
                ret_defn = formats.get(format_id)  # not necessarily equal to requested `definition`
                if not ret_defn:
                    # determine the definition from the returned formats
                    fmt_names = list(formats.values())
                    if definition not in fmt_names:
                        for definition in self._VQQ_FORMAT_IDS_DEFAULT[QQVideoPlatforms.P10801]:
                            if definition in fmt_names:
                                break
                    ret_defn = definition

                vfilename = json_path_get(data, ['vl', 'vi', 0, 'fn'], '')
                vfn = vfilename.rpartition('.')  # e.g. ['egmovie.321003', '.', 'ts']

                ext = vfn[-1]  # e.g. 'ts' 'mp4'
                fc = json_path_get(data, ['vl', 'vi', 0, 'fc'])
                start = 0 if fc == 0 else 1  # start counting number of the video clip file indexes

                if ext == 'ts':
                    if drm == 1 and not preview and not self.has_vip:
                        return format_name, ext, urls

                    for idx in range(start, fc + 1):
                        vfilename_new = '.'.join([vfn[0], str(idx), 'ts'])
                        url_mirrors = '\t'.join(
                            ['%s%s' % (prefix, vfilename_new) for prefix in chosen_url_prefixes])
                        urls.append(url_mirrors)
                else:  # 'mp4'
                    if drm == 1 and not self.has_vip:
                        return format_name, ext, urls

                    logo = json_path_get(data, ['vl', 'vi', 0, 'logo'])
                    if logo == 0:  # logo == 0 or drm == 1
                        ext = 'ts'

                        playlist_m3u8 = json_path_get(data, ['vl', 'vi', 0, 'ul', 'ui', -1, 'hls', 'pname'])
                        playlist_url = chosen_url_prefixes[0] + playlist_m3u8

                        r = self._requester.get(playlist_url, cookies=self.user_token)
                        if r.status_code == 200:
                            r.encoding = 'utf-8'
                            for line in r.iter_lines(decode_unicode=True):
                                if line and not line.startswith('#'):
                                    url_mirrors = '\t'.join(
                                        ['%s%s/%s' % (prefix, vfilename, line) for prefix in chosen_url_prefixes])
                                    urls.append(url_mirrors)
                    else:
                        return self._get_video_urls_p10901(vid, definition)

                format_name = ret_defn

        return format_name, ext, urls

    def _get_video_urls_p10901(self, vid, definition):
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
            'platform': QQVideoPlatforms.P10901,
            'sdtfrom': 'v1010',
            'host': 'v.qq.com',
            'fhdswitch': 0,
            'show1080p': 1,
        }
        r = self._requester.get('https://h5vv.video.qq.com/getinfo', params=params, cookies=self.user_token)
        if r.status_code == 200:
            try:
                data = json.loads(r.text[len('QZOutputJson='):-1])
            except json.JSONDecodeError:
                # logging
                return format_name, ext, urls

            if data:
                url_prefixes = []
                for url_dic in json_path_get(data, ['vl', 'vi', 0, 'ul', 'ui'], []):
                    if isinstance(url_dic, dict):
                        url = url_dic.get('url')
                        if url and not url.startswith(self.cdn_blacklist):
                            url_prefixes.append(url)

                chosen_url_prefixes = [prefix for prefix in url_prefixes if
                                       prefix[:prefix.find('/', 8)].endswith('.tc.qq.com')]
                if not chosen_url_prefixes:
                    chosen_url_prefixes = url_prefixes

                if self.use_cdn:
                    # use all URL prefixes but with default servers coming before CDN mirrors
                    cdn = [prefix for prefix in url_prefixes if prefix not in chosen_url_prefixes]
                    chosen_url_prefixes += cdn

                # drm = json_path_get(data, ['vl', 'vi', 0, 'drm'])

                # pick the best matched definition from available formats
                formats = {fmt.get('name'): fmt.get('id') for fmt in json_path_get(data, ['fl', 'fi'], [])}
                if definition not in formats:
                    for definition in self._VQQ_FORMAT_IDS_DEFAULT[QQVideoPlatforms.P10901]:
                        if definition in formats:
                            break

                format_id = formats.get(definition) or self._VQQ_FORMAT_IDS_DEFAULT[QQVideoPlatforms.P10901][definition]
                vfilename = json_path_get(data, ['vl', 'vi', 0, 'fn'], '')
                vfn = vfilename.split('.')  # e.g. ['egmovie', 'p201', 'mp4'], ['egmovie', 'mp4']
                ext = vfn[-1]  # video extension, e.g. 'mp4'
                # vfmt = vfn[1]  # e.g. 'p201'
                # fmt_prefix = vfmt[0]  # e.g. 'p' in 'p201'
                vfmt_new = vfn[1][0] + str(format_id % 10000) if len(vfn) == 3 else ''

                fc = json_path_get(data, ['vl', 'vi', 0, 'cl', 'fc'])
                keyids = [chap.get('keyid') for chap in json_path_get(data, ['vl', 'vi', 0, 'cl', 'ci'], [])] if fc \
                    else [json_path_get(data, ['vl', 'vi', 0, 'cl', 'keyid'])]
                for keyid in keyids:
                    keyid_new = keyid.split('.')
                    if len(keyid_new) == 3:
                        keyid_new[1] = vfmt_new
                        keyid_new = '.'.join(keyid_new)
                    else:
                        keyid_new = '.'.join(vfn[:-1])
                    cfilename = keyid_new + '.' + ext
                    params = {
                        'otype': 'json',
                        'vid': vid,
                        'format': format_id,
                        'filename': cfilename,
                        'platform': QQVideoPlatforms.P10901,
                        'vt': 217,
                        'charge': 0,
                    }
                    r = self._requester.get('https://h5vv.video.qq.com/getkey', params=params,
                                            cookies=self.user_token)
                    if r.status_code == 200:
                        try:
                            key_data = json.loads(r.text[len('QZOutputJson='):-1])
                        except json.JSONDecodeError:
                            # logging
                            return format_name, ext, urls

                        if key_data and isinstance(key_data, dict) and key_data.get('key'):
                            url_mirrors = '\t'.join(['%s%s?sdtfrom=v1010&vkey=%s' % (url_prefix, cfilename, key_data['key'])
                                                    for url_prefix in chosen_url_prefixes])
                            if url_mirrors:
                                urls.append(url_mirrors)

                # check if the URLs for the file parts have all been successfully obtained
                if len(keyids) == len(urls):
                    format_name = definition

        return format_name, ext, urls

    def _get_video_urls(self, vid, definition):
        if self.no_logo:
            return self._get_video_urls_p10801(vid, definition)
        else:
            return self._get_video_urls_p10901(vid, definition)

    def _extract_video_cover_info(self, regex, text):
        result = (None, None)

        cover_match = regex.search(text)
        if cover_match:
            info = {}
            cover_group = cover_match.group(1) or cover_match.group(2)
            try:
                cover_info = json.loads(cover_group)
            except json.JSONDecodeError:
                return result
            if cover_info and isinstance(cover_info, dict):
                info['title'] = cover_info.get('title', '') or cover_info.get('title_new', '')
                info['year'] = cover_info.get('year', '1900')
                info['cover_id'] = cover_info.get('cover_id', '')

                type_id = int(cover_info.get('type') or VideoTypeCodes.MOVIE)
                info['type'] = self._VQQ_TYPE_CODES.get(type_id, VideoTypes.MOVIE)

                video_id = cover_info.get('vid')
                if video_id is None:
                    normal_ids = cover_info.get('nomal_ids') or []

                    for cnt, vi in enumerate(normal_ids, start=1):
                        # del vi['F']
                        vi['E'] = cnt  # add/update episode number 'cause the returned info may not include it
                else:
                    normal_ids = [{"V": video_id, "E": 1}]
                info['normal_ids'] = normal_ids

                result = (info, cover_match.end)

        return result

    def _get_cover_info(self, cover_url):
        """"{
        "referrer": "https://v.qq.com/x/cover/nhtfh14i9y1egge.html",
        "title":"" ,
        "year":"",
        "type":VideoTypes.TV,
        "cover_id":"",
        "episode_all": 16,
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
            info, pos_end = self._extract_video_cover_info(self._COVER_PAT_RE, r.text)
            if info:
                if not info['normal_ids']:
                    info, _ = self._extract_video_cover_info(self._VIDEO_INFO_RE, r.text[pos_end:])
            else:
                info, _ = self._extract_video_cover_info(self._VIDEO_INFO_RE, r.text)

        if info:
            info['episode_all'] = len(info['normal_ids']) if info['normal_ids'] else 1
            info['referrer'] = cover_url  # set the Referer to the address of the cover web page

        return info

    def get_cover_info(self, videourl):
        cover_info = None
        for typ, pat in enumerate(self._VIDEO_URL_PATS, 1):
            match = pat['cpat'].match(videourl)
            if match:
                if typ == 1:  # 'video_cover'
                    cover_info = self._get_cover_info(videourl)
                    break
                elif typ == 2:  # 'video_detail'
                    cover_id = match.group(2)
                    cover_url = self._VIDEO_COVER_PREFIX + cover_id + '.html'
                    cover_info = self._get_cover_info(cover_url)
                    break
                elif typ == 3:  # 'video_episode'
                    cover_id = match.group(1)
                    video_id = match.group(2)
                    cover_url = self._VIDEO_COVER_PREFIX + cover_id + '.html'
                    cover_info = self._get_cover_info(cover_url)
                    if cover_info:
                        cover_info['normal_ids'] = [dic for dic in cover_info['normal_ids'] if dic['V'] == video_id]
                    break
                else:  # typ == 4 'video_page'
                    video_id = match.group(1)
                    cover_info = self._get_cover_info(videourl)
                    if cover_info:
                        cover_info['normal_ids'] = \
                            [dic for dic in cover_info['normal_ids'] if dic['V'] == video_id] if cover_info['normal_ids'] else \
                            [{"V": video_id, "E": 1}]

                        if not cover_info['cover_id']:
                            cover_info['cover_id'] = video_id
                    break

        return cover_info

    def update_video_dwnld_info(self, cover_info):
        """"
        {
            "referrer": "https://v.qq.com/x/cover/nhtfh14i9y1egge.html",
            "title": "李师师",
            "year": "1989",
            "type": VideoTypes.TV,
            "cover_id": "nhtfh14i9y1egge",
            "episode_all": 16,
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
        for vi in cover_info['normal_ids']:
            vi.setdefault('defns', {})

            format_name, ext, urls = self._get_video_urls(vi['V'], self.preferred_defn)
            if format_name:  # may not be same as preferred definition
                fmt = dict(ext=ext, urls=urls)
                vi['defns'].setdefault(format_name, []).append(fmt)

    def get_video_config_info(self, url):
        cover_info = self.get_cover_info(url)
        if cover_info:
            self.update_video_dwnld_info(cover_info)

        return cover_info
