import time
import re
import random
import hashlib

# from requests.cookies import RequestsCookieJar

from ..videoconfig import VideoConfig
from ..commons import VideoTypeCodes

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
    _VIP_TOKEN = {}

    def __init__(self, requester=None):
        super().__init__(requester)

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

        self._VIDEO_COVER_FORMAT = 'https://www.1905.com/mdb/film/{}/video'
        self._PROFILE_CONFIG_URL = "http://profile.m1905.com/mvod/config.php"
        self._apikey = ""

        # make sure _VIDEO_URL_PATS has a compiled version, which should have been done in @classmethod is_url_valid
        for pat in self._VIDEO_URL_PATS:
            if pat.get('cpat') is None:
                pat['cpat'] = re.compile(pat['pat'], re.IGNORECASE)

    def _get_episode_info_sd(self, epurl):
        info = None

        r = self._requester.get(epurl, allow_redirects=True)
        if r.status_code == 200:  # requests.codes.ok
            r.encoding = 'utf-8'
            conf_match = self._SD_CONF_PAT_RE.search(r.text)
            if conf_match:
                info = {}
                info['title'] = conf_match.group(2)
                # info['year'] = video_info.get('year')  # extract it from the cover page
                info['cover_id'] = conf_match.group(3)
                info['vid'] = conf_match.group(1)

                self._apikey = conf_match.group(4)

        return info

    def _get_episode_info_hd(self, epurl):
        '''Parse VIP webpage'''

        info = None
        regex_vip = r"movie-title\s*\"\s*>(?P<title>[^<]+)</h1>.*?年份[^\d]+(?P<year>\d+).*?www\.1905\.com/mdb/film/(?P<cover_id>\d+)"

        r = self._requester.get(epurl, allow_redirects=True)
        if r.status_code == 200:
            r.encoding = 'utf-8'
            conf_match = re.search(regex_vip, r.text, flags=re.MULTILINE|re.DOTALL|re.IGNORECASE)
            if conf_match:
                info = {}
                info['title'] = conf_match.group('title')
                info['year'] = conf_match.group('year')
                info['cover_id'] = conf_match.group('cover_id')
                info['vid'] = epurl.split('/')[-1].split('.')[0]

        return info


    def _get_cover_info(self, cvurl):
        """

        :param cvurl:
        :return: "1983", {"sd": "https://t.com", "hd": "https://u.com"}
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

    def _get_video_info(self, url):
        conf_info = None
        episode_info = None

        for typ, pat in enumerate(self._VIDEO_URL_PATS, 1):
            match = pat['cpat'].match(url)
            if match:
                conf_info = {}
                # conf_info["normal_ids"] = []
                if typ == 1:  # 'video_episode_sd'
                    episode_info = self._get_episode_info_sd(url)
                    if episode_info:
                        year, _ = self._get_cover_info(self._VIDEO_COVER_FORMAT.format(episode_info['cover_id']))
                        episode_info['year'] = year

                        conf_info["normal_ids"] = [dict(V=episode_info['vid'], E=1, defns=dict(sd=[]))]
                elif typ == 2:  # 'video_cover'
                    year, urls_dict = self._get_cover_info(self._VIDEO_COVER_FORMAT.format(match.group(1)))
                    if urls_dict:
                        conf_info["normal_ids"] = []
                        ep_num = 0
                        if urls_dict.get('sd'):
                            episode_info = self._get_episode_info_sd(urls_dict['sd'])
                            if episode_info:
                                episode_info['year'] = year
                                ep_num += 1
                                conf_info["normal_ids"].append(dict(V=episode_info['vid'], E=ep_num, defns=dict(sd=[])))

                        if urls_dict.get('hd'):
                            episode_info = self._get_episode_info_hd(urls_dict['hd'])
                            if episode_info:
                                ep_num += 1
                                conf_info["normal_ids"].append(dict(V=episode_info['vid'], E=ep_num, defns=dict(hd=[])))
                else:  # video_episode_hd
                    episode_info = self._get_episode_info_hd(url)
                    if episode_info:
                        conf_info["normal_ids"] = [dict(V=episode_info['vid'], E=1, defns=dict(hd=[]))]

                if episode_info:
                    conf_info["title"] = episode_info["title"]
                    conf_info["year"] = episode_info["year"]
                    conf_info["type"] = VideoTypeCodes.MOVIE
                    conf_info["cover_id"] = episode_info["cover_id"]

                break

        return conf_info

    def _update_video_dwnld_info_sd(self, vi):
        '''vi: item of confinfo['normal_ids']'''

        random.seed()
        params = {
            "k": self._apikey[10:18],
            "t": str(time.time() * 1000)[:13],
            "i": vi['V'],
            "p": str(random.random())[-15:],
            "v": 1
        }
        params["s"] = hashlib.md5((params["k"] + params["t"] + params["i"] + params["p"]).encode('utf-8')).hexdigest()

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

            mo = re.search(r"item\s+id\s*=.*?url\s*=\s*\"([^\"]+)", r.text)
            if mo:
                loader_url = mo.group(1)
                loader_url = loader_url.replace("%2F", "/").replace("&amp;", "&")

                try:
                    # r = self._requester.get(loader_url, headers=headers, cookies=cookie_jar, timeout=3.5)
                    r = self._requester.get(loader_url)  # Requests Session persists cookies across all requests
                    if r.status_code == 200:
                        mpeg_urls = [url for url in r.text.splitlines() if url[:4] == "http"]
                        vi["defns"]["sd"].append(dict(ext="ts", urls=mpeg_urls))
                except Exception:
                    print("Failed to fetch {!r}".format(loader_url))  # logging


    def _update_video_dwnld_info_hd(self, vi):
        pass


    def _update_video_dwnld_info(self, confinfo):
        for vi in confinfo.get('normal_ids'):
            for defn in vi["defns"].keys():
                if defn == "sd":
                    self._update_video_dwnld_info_sd(vi)
                elif defn == "hd":
                    self._update_video_dwnld_info_hd(vi)



    def get_video_config_info(self, url):
        conf_info = self._get_video_info(url)
        if conf_info:
            self._update_video_dwnld_info(conf_info)

        return conf_info

