import re
import logging


class VideoConfig(object):
    # [{'pat': r'^https?://v\.qq\.com/x/cover/(\w+)\.html', 'eg': 'https://v.qq.com/x/cover/nhtfh14i9y1egge.html'}]
    _VIDEO_URL_PATS = []
    _requester = None  # Web content downloader, e.g. requests
    VC_NAME = 'vc'

    def __init__(self, requester, args, confs):
        self._requester = requester
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

    def get_video_config_info(self, url):
        pass

    def set_requester(self, requester):
        self._requester = requester
