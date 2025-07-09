import re
import logging

from bdownload.download import requests_retry_session
from .utils import build_cookiejar_from_kvp


class VideoConfig(object):
    # [{'pat': r'^https?://v\.qq\.com/x/cover/(\w+)\.html', 'eg': 'https://v.qq.com/x/cover/nhtfh14i9y1egge.html'}]
    _VIDEO_URL_PATS = []
    _requester = None  # Web content downloader, e.g. requests
    SOURCE_NAME = 'vc'
    VC_NAME = 'vc'

    def __init__(self, args, confs):
        self.args = args
        self.confs = confs
        logger_name = '.'.join(['MDL', self.VC_NAME])  # 'MDL.vc'
        self._logger = logging.getLogger(logger_name)

        verify = self.confs['ca_cert'] or True
        self._requester = requests_retry_session(verify=verify)

        # set proxy
        proxy = self.confs['proxy']
        if proxy:
            proxies = dict(http=proxy, https=proxy)
            self._requester.proxies = proxies

        # get user tokens/cookies from configuration file
        self._regular_token = build_cookiejar_from_kvp(self.confs['regular_user_token'])
        self._vip_token = build_cookiejar_from_kvp(self.confs['vip_user_token'])
        self.has_vip = True if self._vip_token else False
        self.user_token = self._vip_token if self._vip_token else self._regular_token
        if self.user_token:
            # set regular/VIP user cookie for the requesting session
            self._requester.cookies = self.user_token

        # set default user agent
        user_agent = self.confs['user_agent']
        if user_agent:
            self._requester.headers.update({'User-Agent': user_agent})

        self.preferred_defn = self.confs['definition']

    @classmethod
    def is_url_valid(cls, url):
        for pat in cls._VIDEO_URL_PATS:
            if pat.get('cpat') is None:
                pat['cpat'] = re.compile(pat['pat'], re.IGNORECASE)
            match = pat['cpat'].match(url)
            if match:
                return True

        return False

    @classmethod
    def generate_device_id(cls):
        pass

    def get_video_cover_info(self, url):
        pass

    def update_video_dwnld_info(self, vi):
        pass

    @staticmethod
    def _in_rangeset(ep, rangeset):
        for rng in rangeset:
            if isinstance(rng, tuple):
                if ep >= rng[0] and ((rng[1] is None) or ep <= rng[1]):
                    return True
            else:
                if ep == rng:
                    return True

        return False

    @staticmethod
    def _slice_by_rangeset(lst, rangeset):
        slic = []
        for rng in rangeset:
            if isinstance(rng, tuple):
                sl = lst[rng[0]-1:rng[1]]
                for d in sl:
                    if d not in slic:
                        slic.append(d)
            else:
                sl = lst[rng-1:rng]
                if sl and (sl[0] not in slic):
                    slic += sl

        return slic

    @staticmethod
    def _filter_by_playlist(normal_ids, playlist):
        ids = {vi['E']: idx for idx, vi in enumerate(normal_ids)}
        eps = set()

        max_ep = max(ids.keys())
        for rng in playlist:
            if isinstance(rng, tuple):
                rng_1 = max_ep if rng[1] is None else min(rng[1], max_ep)
                for ep in range(rng[0], rng_1 + 1):
                    eps.add(ep)
            else:
                eps.add(rng)

        return [normal_ids[ids[ep]] for ep in sorted(eps) if ep in ids]

    def filter_video_episodes(self, url, cover_info):
        if cover_info['normal_ids'] and self.args['playlist_items'][url]:
            normal_ids = cover_info['normal_ids']
            playlist_items = self.args['playlist_items'][url]

            if len(normal_ids) == 1:
                if not self._in_rangeset(normal_ids[0]['E'], playlist_items):
                    cover_info['normal_ids'] = []
            else:
                cover_info['normal_ids'] = self._filter_by_playlist(normal_ids, playlist_items)

        return cover_info

    def get_cover_config_info(self, url):
        cover_info = self.get_video_cover_info(url)
        if cover_info:
            cover_info = self.filter_video_episodes(url, cover_info)

            cover_info['source_name'] = self.SOURCE_NAME
            cover_info['vc_name'] = self.VC_NAME

        return cover_info

    def update_cover_dwnld_info(self, cover_info):
        vl = cover_info.get('normal_ids', [])
        for vi in vl:
            self.update_video_dwnld_info(vi)

    def set_requester(self, requester):
        self._requester = requester
