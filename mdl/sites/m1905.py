import json
import time
import re
import random
import hashlib
from urllib.parse import quote as urllib_parse_quote, urlencode, urljoin
from math import floor as math_floor

# from requests.cookies import RequestsCookieJar
from requests import RequestException

from ..videoconfig import VideoConfig
from ..commons import VideoTypes
from ..utils import json_path_get


class M1905VC(VideoConfig):
    _VIDEO_URL_PATS = [
        {'pat': r'^https?://www\.1905\.com/(?:vod|video)/play/(\d+)\.shtml',
         'eg': 'https://www.1905.com/vod/play/1287886.shtml'}, # 'video_episode_sd'
        {'pat': r'^https?://www\.1905\.com/mdb/film/(\d+)/?',
         'eg': 'https://www.1905.com/mdb/film/2245563'},  # 'video_cover'
        {'pat': r'https?://vip\.1905\.com/play/(\d+)\.shtml',
         'eg': 'https://vip.1905.com/play/535547.shtml'}  # 'VIP: video_episode_hd'
    ]
    SOURCE_NAME = "m1905"
    VC_NAME = "m1905"
    #_VIP_TOKEN = {}

    _M1905_DEFINITION = ['fhd', 'uhd', 'hd', 'sd']  # decremental! FIXME: VIP user
    _M1905_DEFN_MAP_I2S = {'fhd': 'fhd', 'uhd': 'shd', 'hd': 'hd', 'sd': 'sd'}  # internal format name -> standard format name
    _M1905_DEFN_MAP_S2I = {'dolby': 'fhd', 'sfr_hdr': 'fhd', 'hdr10': 'fhd', 'uhd': 'fhd', 'fhd': 'fhd', 'shd': 'uhd', 'hd': 'hd', 'sd': 'sd'}  # standard -> internal | FIXME: VIP fhd?

    def __init__(self, requester, args, confs):
        super().__init__(requester, args, confs)

        self._SD_CONF_PAT_RE = re.compile(
            r"(?:VODCONFIG|VIDEOCONFIG).*vid\s*:\s*\"(\d+)\".*?(?<!vip)title\s*:\s*\"(.*?)\".*?apikey\s*:\s*\"(.*?)\"",  # (mdbfilmid\s*:\s*\"(\d+)\")?
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

        try:
            r = self._requester.get(epurl)
            if r.status_code == 200:  # requests.codes.ok
                r.encoding = 'utf-8'
                conf_match = self._SD_CONF_PAT_RE.search(r.text)
                if conf_match:
                    info = {'vid': conf_match.group(1), 'title': conf_match.group(2)}
                    # info['year'] = video_info.get('year')  # extract it from the cover page
                    self._apikey = conf_match.group(3)

                    video_config = conf_match.group(0)  # VODCONFIG | VIDEOCONFIG
                    re_cover_id = r"mdbfilmid\s*:\s*\"(\d+)\""
                    cover_id_match = re.search(re_cover_id, video_config, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)
                    info['cover_id'] = cover_id_match.group(1) if cover_id_match else ""
            else:
                raise RequestException("Unexpected status code %i" % r.status_code)
        except RequestException as e:
            self._logger.error("Request webpage '%s' failed: '%r'", epurl, e)

        return info

    def _get_episode_info_hd(self, epurl):
        """Parse VIP webpage"""

        info = None
        regex_vip = r"movie-title\s*\"\s*>(?P<title>[^<]+)</h1>.*?年份[^\d]+(?P<year>\d+).*?www\.1905\.com/mdb/film/(?P<cover_id>\d+)"

        try:
            r = self._requester.get(epurl)
            if r.status_code == 200:
                r.encoding = 'utf-8'
                conf_match = re.search(regex_vip, r.text, flags=re.MULTILINE|re.DOTALL|re.IGNORECASE)
                if conf_match:
                    info = {'title': conf_match.group('title'), 'year': conf_match.group('year'),
                            'cover_id': conf_match.group('cover_id'), 'vid': epurl.split('/')[-1].split('.')[0]}
            else:
                raise RequestException("Unexpected status code %i" % r.status_code)
        except RequestException as e:
            self._logger.error("Request webpage '%s' failed: '%r'", epurl, e)

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

        try:
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
                raise RequestException("Unexpected status code %i" % r.status_code)
        except RequestException as e:
            self._logger.error("Request webpage '%s' failed: '%r'", cvurl, e)

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
                        if episode_info['cover_id']:
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
                    cover_info["title"] = episode_info.get("title") or ""
                    cover_info["year"] = episode_info.get("year") or ""
                    cover_info["type"] = VideoTypes.MOVIE
                    cover_info["cover_id"] = episode_info.get("cover_id") or ""
                    cover_info["episode_all"] = len(cover_info["normal_ids"])
                    cover_info["referrer"] = url

                break

        return cover_info

    @staticmethod
    def _pick_highest_bandwidth_m3u8(playlist_variants):
        bandwidth, m3u = 0, ""
        streams = playlist_variants.splitlines()
        i = 0
        while i < len(streams):
            stream = streams[i]
            if stream and stream.startswith("#EXT-X-STREAM-INF:"):
                # skip the blank and comment lines, if any
                while not streams[i + 1] or streams[i + 1].startswith("#"):
                    i += 1

                stream_match = re.search(r"BANDWIDTH\s*=\s*(\d+)", stream)
                if stream_match:
                    matched = int(stream_match.group(1))
                    if matched > bandwidth:
                        bandwidth = matched
                        m3u = streams[i + 1]

                i += 2
            else:
                i += 1

        return bandwidth, m3u

    def _get_ts_playlist(self, m3u8_url):
        playlist = m3u8_url
        try:
            for _ in range(2):
                r = self._requester.get(playlist)
                if r.status_code == 200:
                    r.encoding = "utf-8"
                    for line in r.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        if line.startswith("#EXT-X-STREAM-INF:"):  # in master playlist
                            _, m3u = self._pick_highest_bandwidth_m3u8(r.text)
                            playlist = urljoin(playlist, m3u)
                            break
                        elif line.startswith("#EXTINF:"):  # in media playlist
                            mpeg_urls = [urljoin(playlist, ts) for ts in r.text.splitlines() if
                                         ts and not ts.startswith('#') and (ts.endswith('.ts') or '.ts?' in ts)]
                            return mpeg_urls
                else:
                    raise RequestException("Unexpected status code %i" % r.status_code)
        except RequestException as e:
            self._logger.error("Failed to fetch '%s': '%r'", playlist, e)

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

        try:
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

                defn = self._M1905_DEFN_MAP_S2I[self.preferred_defn]
                defns = [defn] if json_path_get(data, ['sign', defn]) else self._M1905_DEFINITION
                for defn in defns:
                    host = json_path_get(data, ['quality', defn, 'host'])
                    sign = json_path_get(data, ['sign', defn, 'sign'])
                    path = json_path_get(data, ['path', defn, 'path'])

                    if host and sign and path:
                        playlist_m3u8 = (host + sign + path).replace('\\', '')
                        mpeg_urls = self._get_ts_playlist(playlist_m3u8)
                        if mpeg_urls:
                            std_defn = self._M1905_DEFN_MAP_I2S[defn]
                            vi["defns"].setdefault(std_defn, []).append(dict(ext="ts", urls=mpeg_urls))

                            break
            else:
                raise RequestException("Unexpected status code %i" % r.status_code)
        except RequestException as e:
            request_url = "%s?%s" % (self._PROFILE_CONFIG_URL, urlencode(params))
            self._logger.error("Failed to fetch '%s': '%r'", request_url, e)

    def _update_video_dwnld_info_hd(self, vi):
        pass

    def update_video_dwnld_info(self, cover_info):
        vl = cover_info.get('normal_ids', [])
        for vi in vl:
            if not vi['vip']:
                self._update_video_dwnld_info_sd(vi)
            else:
                self._update_video_dwnld_info_hd(vi)
