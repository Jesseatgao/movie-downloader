import re
import logging


class VideoConfig(object):
    # [{'pat': r'^https?://v\.qq\.com/x/cover/(\w+)\.html', 'eg': 'https://v.qq.com/x/cover/nhtfh14i9y1egge.html'}]
    _VIDEO_URL_PATS = []
    _requester = None  # Web content downloader, e.g. requests
    VC_NAME = 'vc'

    def __init__(self, requester, args, confs):
        self._requester = requester
        self.args = args
        self.confs = confs
        logger_name = '.'.join(['MDL', self.VC_NAME])  # 'MDL.vc'
        self._logger = logging.getLogger(logger_name)

        # set proxy
        proxy = confs[self.VC_NAME]['proxy']
        if proxy:
            proxies = dict(http=proxy, https=proxy)
            self._requester.proxies = proxies

        # set default user agent
        user_agent = confs[self.VC_NAME]['user_agent']
        if user_agent:
            self._requester.headers.update({'User-Agent': user_agent})

    @classmethod
    def is_url_valid(cls, url):
        for pat in cls._VIDEO_URL_PATS:
            if pat.get('cpat') is None:
                pat['cpat'] = re.compile(pat['pat'], re.IGNORECASE)
            match = pat['cpat'].match(url)
            if match:
                return True

        return False

    def get_cover_info(self, url):
        pass

    def update_video_dwnld_info(self, cover_info):
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

    def filter_video_episodes(self, url, cover_info):
        if cover_info['normal_ids'] and self.confs['playlist_items'][url]:
            normal_ids = cover_info['normal_ids']
            playlist_items = self.confs['playlist_items'][url]

            if len(normal_ids) == 1:
                if not self._in_rangeset(normal_ids[0]['E'], playlist_items):
                    cover_info['normal_ids'] = []
            else:
                cover_info['normal_ids'] = self._slice_by_rangeset(normal_ids, playlist_items)

        return cover_info

    def get_video_config_info(self, url):
        cover_info = self.get_cover_info(url)
        if cover_info:
            cover_info['url'] = url  # original request URL

            cover_info = self.filter_video_episodes(url, cover_info)

        return cover_info

    def set_requester(self, requester):
        self._requester = requester
