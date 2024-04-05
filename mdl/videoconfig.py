import re
import logging
import codecs
import os
from pathlib import Path

import certifi


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

    @classmethod
    def make_ca_bundle(cls, args, confs):
        """Combine the site-configured intermediate certificates with the CA bundle from `certifi`"""
        here = os.path.abspath(os.path.dirname(__file__))
        vc_ca_path = Path(os.path.join(here, 'certs'))
        vc_ca_bundle = os.path.join(vc_ca_path, ''.join([cls.VC_NAME, '_', 'cacert.pem']))

        if not confs[cls.VC_NAME]['ca_cert']:
            if os.path.isfile(vc_ca_bundle):
                os.remove(vc_ca_bundle)
            return

        vc_ca_path.mkdir(parents=True, exist_ok=True)
        with codecs.open(vc_ca_bundle, 'w', 'utf-8') as vc_fd:
            vc_fd.write('\n')
            vc_fd.write(confs[cls.VC_NAME]['ca_cert'])
            vc_fd.write('\n')
            with codecs.open(certifi.where(), 'r', 'utf-8') as certifi_fd:
                vc_fd.write(certifi_fd.read())

        return vc_ca_bundle

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
