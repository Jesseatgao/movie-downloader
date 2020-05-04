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
        proxies = dict(http=confs[self.VC_NAME]['proxy'],
                       https=confs[self.VC_NAME]['proxy'])
        self._requester.proxies = proxies

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
