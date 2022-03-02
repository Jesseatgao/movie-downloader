import json
import time
import re
import random
import hashlib
from urllib.parse import quote as urllib_parse_quote
from math import floor as math_floor

# from requests.cookies import RequestsCookieJar

from ..videoconfig import VideoConfig
from ..commons import VideoTypes
from ..utils import json_path_get


class M1905VC(VideoConfig):
    _VIDEO_URL_PATS = [
        {'pat': r'^https?://www\.1905\.com/vod/play/(\d+)\.shtml',
         'eg': 'https://www.1905.com/vod/play/1287886.shtml'}, # 'video_episode_sd'
        {'pat': r'^https?://www\.1905\.com/mdb/film/(\d+)/?',
         'eg': 'https://www.1905.com/mdb/film/2245563'},  # 'video_cover'
        {'pat': r'https?://vip\.1905\.com/play/(\d+)\.shtml',
         'eg': 'https://vip.1905.com/play/535547.shtml'}  # 'VIP: video_episode_hd'
    ]
    SOURCE_NAME = "m1905"
    VC_NAME = "m1905"
    #_VIP_TOKEN = {}

    _M1905_DEFINITION = ['uhd', 'hd', 'sd']  # decremental! FIXME: VIP user
    _M1905_DEFN_MAP_I2S = {'uhd': 'shd', 'hd': 'hd', 'sd': 'sd'}  # internal format name -> standard format name
    _M1905_DEFN_MAP_S2I = {'fhd': 'fhd', 'shd': 'uhd', 'hd': 'hd', 'sd': 'sd'}  # standard -> internal | FIXME: VIP fhd?

    def __init__(self, requester, args, confs):
        super().__init__(requester, args, confs)

        self._SD_CONF_PAT_RE = re.compile(
            r"VODCONFIG.*vid\s*:\s*\"(\d+)\".*title\s*:\s*\"(.*?)\".*mdbfilmid\s*:\s*\"(\d+)\".*apikey\s*:\s*\"(.*?)\"",
            re.MULTILINE | re.DOTALL | re.IGNORECASE
        )
        self._COVER_YEAR_RE = re.compile(r"header-wrapper-h1.*?\(\s*(\d+)\s*\)",
                                         re.MULTILINE | re.DOTALL | re.IGNORECASE
                                         )
        self._ONLINE_COVER_RE = re.compile(
            r"class\s*=\s*\"\s*watch-online.+?正片.+?(<ul\s+class\s*=\s*\"watch-online-list.*?</ul>)",
            re.MULTILINE | re.DOTALL | re.IGNORECASE
        )
        self._ONLINE_EPISODE_RE = re.compile(
            r"<a\s+href\s*=\s*\"([^\"]+)\"\s+class=\"online-list-positive.*?right-gray\">(.*?)</span>",
            re.MULTILINE | re.DOTALL | re.IGNORECASE
        )

        self._VIDEO_COVER_FORMAT = "https://www.1905.com/mdb/film/{}/video"
        self._PROFILE_CONFIG_URL = "https://profile.m1905.com/mvod/getVideoinfo.php"
        self._apikey = ""
        self._appid = "dde3d61a0411511d"

        # make sure _VIDEO_URL_PATS has a compiled version, which should have been done in @classmethod is_url_valid
        for pat in self._VIDEO_URL_PATS:
            if pat.get('cpat') is None:
                pat['cpat'] = re.compile(pat['pat'], re.IGNORECASE)

        self.preferred_defn = confs[self.VC_NAME]['definition']

    @staticmethod
    def _random_string():
        def translate(c):
            n = math_floor(16 * random.random())
            t = "{:x}".format(n) if 'x' == c else "{:x}".format(3 & n | 8) if 'y' == c else c
            return t

        random.seed()
        return ''.join(map(translate, "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"))

    @staticmethod
    def _signature(params, appid):
        query = ""
        ks = sorted(params.keys())
        for k in ks:
            if k != "signature":
                q = k + "=" + urllib_parse_quote(str(params[k]), safe="")
                query += "&" + q if query else q

        return hashlib.sha1((query + "." + appid).encode("utf-8")).hexdigest()

    def _get_episode_info_sd(self, epurl):
        info = None

        r = self._requester.get(epurl, allow_redirects=True)
        if r.status_code == 200:  # requests.codes.ok
            r.encoding = 'utf-8'
            conf_match = self._SD_CONF_PAT_RE.search(r.text)
            if conf_match:
                info = {'vid': conf_match.group(1), 'title': conf_match.group(2), 'cover_id': conf_match.group(3)}
                # info['year'] = video_info.get('year')  # extract it from the cover page

                self._apikey = conf_match.group(4)

        return info

    def _get_episode_info_hd(self, epurl):
        """Parse VIP webpage"""

        info = None
        regex_vip = r"movie-title\s*\"\s*>(?P<title>[^<]+)</h1>.*?年份[^\d]+(?P<year>\d+).*?www\.1905\.com/mdb/film/(?P<cover_id>\d+)"

        r = self._requester.get(epurl, allow_redirects=True)
        if r.status_code == 200:
            r.encoding = 'utf-8'
            conf_match = re.search(regex_vip, r.text, flags=re.MULTILINE|re.DOTALL|re.IGNORECASE)
            if conf_match:
                info = {'title': conf_match.group('title'), 'year': conf_match.group('year'),
                        'cover_id': conf_match.group('cover_id'), 'vid': epurl.split('/')[-1].split('.')[0]}

        return info

    def _get_cover_info(self, cvurl):
        """

        :param cvurl:
        :returns: "1983", {"sd": "https://t.com", "hd": "https://u.com"}.
        """
        year = ""
        defns = {
            "VIP免广告": "hd",
            "免费": "sd"
        }
        urls = {}

        r = self._requester.get(cvurl)
        if r.status_code == 200:
            r.encoding = 'utf-8'
            year_match = self._COVER_YEAR_RE.search(r.text)
            if year_match:
                year = year_match.group(1)
                cover_match = self._ONLINE_COVER_RE.search(r.text[year_match.end(0):])
            else:
                cover_match = self._ONLINE_COVER_RE.search(r.text)

            if cover_match:
                episodes_match = self._ONLINE_EPISODE_RE.finditer(cover_match.group(1))
                for mo in episodes_match:
                    urls[defns[mo.group(2)]] = mo.group(1)
        else:
            print("Request webpage failed: {}".format(cvurl))  # logging

        return year, urls

    def get_cover_info(self, url):
        cover_info = None
        episode_info = None

        for typ, pat in enumerate(self._VIDEO_URL_PATS, 1):
            match = pat['cpat'].match(url)
            if match:
                cover_info = {}
                if typ == 1:  # 'video_episode_sd'
                    episode_info = self._get_episode_info_sd(url)
                    if episode_info:
                        year, _ = self._get_cover_info(self._VIDEO_COVER_FORMAT.format(episode_info['cover_id']))
                        episode_info['year'] = year

                        cover_info["normal_ids"] = [dict(V=episode_info['vid'], E=1, vip=False, defns={}, page=url)]
                elif typ == 2:  # 'video_cover'
                    year, urls_dict = self._get_cover_info(self._VIDEO_COVER_FORMAT.format(match.group(1)))
                    if urls_dict:
                        cover_info["normal_ids"] = []
                        ep_num = 0
                        if urls_dict.get('sd'):
                            episode_info = self._get_episode_info_sd(urls_dict['sd'])
                            if episode_info:
                                episode_info['year'] = year
                                ep_num += 1
                                cover_info["normal_ids"].append(dict(V=episode_info['vid'], E=ep_num, vip=False, defns={}, page=urls_dict['sd']))

                        if urls_dict.get('hd'):
                            episode_info = self._get_episode_info_hd(urls_dict['hd'])
                            if episode_info:
                                ep_num += 1
                                cover_info["normal_ids"].append(dict(V=episode_info['vid'], E=ep_num, vip=True, defns={}, page=urls_dict['hd']))
                else:  # video_episode_hd
                    episode_info = self._get_episode_info_hd(url)
                    if episode_info:
                        cover_info["normal_ids"] = [dict(V=episode_info['vid'], E=1, vip=True, defns={}, page=url)]

                if episode_info:
                    cover_info["title"] = episode_info["title"]
                    cover_info["year"] = episode_info["year"]
                    cover_info["type"] = VideoTypes.MOVIE
                    cover_info["cover_id"] = episode_info["cover_id"]
                    cover_info["episode_all"] = len(cover_info["normal_ids"])
                    cover_info["referrer"] = url

                break

        return cover_info

    def _update_video_dwnld_info_sd(self, vi):
        """
        :param vi: item of cover_info['normal_ids'].
        """
        nonce = math_floor(time.time())
        params = {
            'cid': vi['V'],
            'expiretime': nonce + 600,
            'nonce': nonce,
            'page': vi['page'],
            'playerid': self._random_string().replace('-', '')[5:20],
            'type': "hls",
            'uuid': self._random_string()
        }
        params['signature'] = self._signature(params, self._appid)

        r = self._requester.get(self._PROFILE_CONFIG_URL, params=params)
        if r.status_code == 200:
            # cookie_jar = RequestsCookieJar()
            # set_cookie = r.headers.get("Set-Cookie")
            # if set_cookie:
            #     cookie_info = set_cookie.split(";")
            #     name, val = cookie_info[0].split("=")
            #     _, path = cookie_info[-2].split("=")
            #     _, domain = cookie_info[-1].split("=")
            #     cookie_jar.set(name, val, path=path, domain=domain)
            try:
                data = json.loads(r.text[len("null("):-1]).get('data')
            except json.JSONDecodeError:
                return

            playlist_m3u8 = ""
            defn = self._M1905_DEFN_MAP_S2I[self.preferred_defn]
            defns = [defn] if json_path_get(data, ['sign', defn]) else self._M1905_DEFINITION
            for defn in defns:
                host = json_path_get(data, ['quality', defn, 'host'])
                sign = json_path_get(data, ['sign', defn, 'sign'])
                path = json_path_get(data, ['path', defn, 'path'])

                if host and sign and path:
                    playlist_m3u8 = (host + sign + path).replace('\\', '')
                    break

            if playlist_m3u8:
                try:
                    # r = self._requester.get(loader_url, headers=headers, cookies=cookie_jar, timeout=3.5)
                    r = self._requester.get(playlist_m3u8)  # Requests Session persists cookies across all requests
                    if r.status_code == 200:
                        url_prefix = playlist_m3u8.rpartition('/')[0]
                        mpeg_urls = ["%s/%s" % (url_prefix, line) for line in r.text.splitlines() if line and not line.startswith('#')]

                        std_defn = self._M1905_DEFN_MAP_I2S[defn]
                        vi["defns"].setdefault(std_defn, []).append(dict(ext="ts", urls=mpeg_urls))
                except Exception:
                    print("Failed to fetch {!r}".format(playlist_m3u8))  # logging

    def _update_video_dwnld_info_hd(self, vi):
        pass

    def update_video_dwnld_info(self, cover_info):
        vl = cover_info.get('normal_ids', [])
        for vi in vl:
            if not vi['vip']:
                self._update_video_dwnld_info_sd(vi)
            else:
                self._update_video_dwnld_info_hd(vi)

    def get_video_config_info(self, url):
        cover_info = self.get_cover_info(url)
        if cover_info:
            self.update_video_dwnld_info(cover_info)

        return cover_info
