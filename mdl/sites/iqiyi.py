import random
import string
import re
import hashlib
import time
from urllib.parse import urlencode, quote
import json

from requests import RequestException

from mdl.videoconfig import VideoConfig
from mdl.commons import VideoTypes
from mdl.utils import json_path_get


class IQiyiVC(VideoConfig):
    _VIDEO_URL_PATS = [
        {'pat': r'^https?://www\.iqiyi\.com/.+\.html',
         'eg': 'https://www.iqiyi.com/v_19rrad5u8o.html'}  # 'video_page'
    ]
    SOURCE_NAME = "IQiyi"
    VC_NAME = "IQiyi"

    _IQIYI_DEFN_MAP_I2S = {800: 'uhd', 600: 'fhd', 500: 'shd', 300: 'hd', 200: 'sd'}
    _IQIYI_DEFN_MAP_S2I = {'dolby': 800, 'sfr_hdr': 800, 'hdr10': 800, 'uhd': 800, 'fhd': 600, 'shd': 500, 'hd': 300, 'sd': 200}

    def __init__(self, args, confs):
        super().__init__(args, confs)

        self._TVID_PAT_RE = re.compile(r"\"tvid\":\s*(?P<tvid>\d+)", re.MULTILINE | re.DOTALL | re.IGNORECASE)

        self._PLAYER_INIT_URL = 'https://mesh.if.iqiyi.com/player/lw/lwplay/accelerator.js?apiVer=3'
        self._VIDEO_COVER_PREFIX = 'https://mesh.if.iqiyi.com/tvg/v2/lw/base_info'
        self._VIDEO_CONFIG_URL = 'https://cache.video.iqiyi.com/dash'

        self._appver = '13.062.22175'
        #self.preferred_defn = self.confs['definition']

    @staticmethod
    def _calc_vf(url):
        def Ov(e):
            """appending the string 'ulc2h7tka0mdrf2lkb1n6m6mulc2htbn'"""
            r = e
            for t in range(0, 4):
                for i in range(0, 2):
                    for n in range(0, 4):
                        a = (70 * t + 677 * i + 21 * n + 87 * t * i * n + 59) % 30
                        a += 48 if a < 9 else 88
                        r += chr(a)
            return r

        path_n_query = re.sub(r"^(https?://)?cache\.video\.iqiyi\.com", "", url, flags=re.IGNORECASE)

        return hashlib.md5(Ov(path_n_query).encode('utf-8')).hexdigest()

    @staticmethod
    def _authkey(tm, tvid):
        giveaway = hashlib.md5("".encode('utf-8')).hexdigest()  # "d41d8cd98f00b204e9800998ecf8427e"
        return hashlib.md5((giveaway + str(tm) + str(tvid)).encode('utf-8')).hexdigest()

    @staticmethod
    def _calc_sign(params, secret_key="howcuteitis"):
        query = ""
        ks = sorted(params.keys())
        for k in ks:
            q = k + "=" + str(params[k])
            query += q + "&"
        query = query[:-1]

        return hashlib.md5((query + "&secret_key=" + secret_key).encode("utf-8")).hexdigest().upper()

    @classmethod
    def generate_device_id(cls):
        random.seed()
        random_str = "".join(random.choices(string.printable, k=128))
        device_id = hashlib.md5(random_str.encode('utf-8')).hexdigest()

        return device_id

    def get_video_cover_info(self, url):
        info = None

        req_url = self._PLAYER_INIT_URL
        try:
            r = self._requester.get(req_url, headers={'referer': url})
            if r.status_code != 200:
                raise RequestException("Unexpected status code %i" % r.status_code)
            r.encoding = 'utf-8'

            tvid_match = self._TVID_PAT_RE.search(r.text)
            if not tvid_match:
                return info
            tvid = int(tvid_match.group('tvid'))

            params = {
                'entity_id': tvid,
                'device_id': self.confs['device_id'],
                'auth_cookie': '',
                'pcv': self._appver,
                'app_version': self._appver,
                'ext': '',
                'app_mode': 'standard',
                'scale': 125,
                'timestamp': int(time.time() * 1000),
                'src': 'pca_tvg',
                'os': '',
                'conduit_id': ''
            }
            sign = self._calc_sign(params)
            params['sign'] = sign

            req_url = self._VIDEO_COVER_PREFIX
            r = self._requester.get(req_url, params=params)
            if r.status_code != 200:
                raise RequestException("Unexpected status code %i" % r.status_code)
            r.encoding = 'utf-8'

            try:
                data = json.loads(r.text).get('data')
            except json.JSONDecodeError as e:
                self._logger.error("Received ill-formed video config info for tvId '%i': '%r'", tvid, e)
                return info
            if not data:
                return info

            info = {
                'url': url,
                'referrer': url,
                'title': data['base_data']['title'],
                'year': data['base_data']['current_video_year'],
                'cover_id': data['base_data']['qipu_id'],
                'type': VideoTypes.MOVIE if data['base_data']['album_source_type'] == '-1' else VideoTypes.TV,
                # 'normal_ids': [],
                # 'episode_all': len(info['normal_ids'])
            }

            # fallback
            vi = {'V': tvid, 'E': 1, 'defns': {}, 'url': url, 'referrer': url}
            info['normal_ids'] = [vi]
            info['episode_all'] = 1

            data = json_path_get(data, ['template', 'tabs', 0, 'blocks', 2, 'data', 'data'])
            if not data:
                return info

            if isinstance(data, dict):
                info['normal_ids'] = [{'V': vi['qipu_id'], 'E': ep, 'defns': {}, 'title': vi.get('subtitle') or vi.get('title'),
                                       'url': vi.get('page_url') or ''} for ep, vi in enumerate(data['videos'], start=1)]
            else:  # is a `list` of `dict`
                videos = [vd['videos'] for vd in data if vd['videos'] and not isinstance(vd['videos'], str)]
                if not videos:
                    return info
                videos = videos[0]

                ep = 1
                normal_ids = []
                # vis = []
                if isinstance(videos, dict):
                    vis = [vi for part, vi_lst in sorted(videos['feature_paged'].items(), key=lambda x: int(x[0].split('-')[0])) for vi in vi_lst]
                else:  # is a `list` of `dict`
                    vis = [vi for vd in sorted(videos, key=lambda x: int(x['title'].split('-')[0])) for vi in vd['data']]
                for vi in vis:
                    if 0 < vi['album_order'] != ep:
                        ep = vi['album_order']
                    normal_ids.append({'V': vi['qipu_id'], 'E': ep, 'defns': {}, 'title': vi.get('subtitle') or vi.get('title'),
                                       'url': vi.get('page_url') or ''})
                    ep += 1
                info['normal_ids'] = normal_ids

            info['episode_all'] = len(info['normal_ids'])

            if not self.args['playlist_items'][url]:
                info['normal_ids'] = [dic for dic in info['normal_ids'] if dic['V'] == tvid]

            return info
        except RequestException as e:
            self._logger.error("Error while requesting the webpage '%s': '%r'", req_url, e)

    def update_video_dwnld_info(self, vi):
        tm = int(time.time() * 1000)
        params = {
            'tvid': vi['V'],
            'bid': self._IQIYI_DEFN_MAP_S2I[self.preferred_defn],
            'vid': '',
            'src': '01010031010000000000',
            'vt': 0,
            'rs': 1,
            'uid': '',
            'ori': 'pcw',
            'ps': 1,
            'k_uid': self.confs['device_id'],
            'pt': 0,
            'd': 0,
            's': '',
            'lid': 0,
            'cf': 0,
            'ct': 0,
            'authKey': self._authkey(tm, vi['V']),
            'k_tag': 1,
            'dfp': '',
            'locale': 'zh_cn',
            'pck': '',
            'k_err_retries': 0,
            'up': '',
            'qd_v': 'a1',
            'tm': tm,
            'k_ft1': '706436220846084',
            'k_ft4': '1162321298202628',
            'k_ft5': '150994945',
            'k_ft7': '4',
            'fr_300': '120_120_120_120_120_120',
            'fr_500': '120_120_120_120_120_120',
            'fr_600': '120_120_120_120_120_120',
            'fr_800': '120_120_120_120_120_120',
            'fr_1020': '120_120_120_120_120_120',
            'bop': quote('{"version":"10.0","dfp":"","b_ft1":28}'),
            'sr': 1,
            'ost': 0,
            'ut': 0
        }
        params['vf'] = self._calc_vf('/dash?' + urlencode(params))

        req_url = self._VIDEO_CONFIG_URL + '?' + urlencode(params)
        try:
            r = self._requester.get(req_url)
            if r.status_code != 200:
                raise RequestException("Unexpected status code %i, request URL: '%s'" % (r.status_code, req_url))
            r.encoding = 'utf-8'

            try:
                data = json.loads(r.text).get('data')
            except json.JSONDecodeError as e:
                self._logger.error("Received ill-formed video config info for tvId '%i': '%r'", vi['V'], e)
                return
            if not data:
                return

            vd = [vd for vd in sorted(data['program']['video'], key=lambda x: x['bid'], reverse=True) if vd.get('m3u8') and vd['ff'] != 'dash']
            if not vd:
                return
            vd = vd[0]

            ts_urls = [ts for ts in vd['m3u8'].split('\n') if ts and not ts.startswith('#')]
            std_defn = self._IQIYI_DEFN_MAP_I2S[vd['bid']]
            vi["defns"].setdefault(std_defn, []).append(dict(ext=vd['ff'], urls=ts_urls))

        except RequestException as e:
            self._logger.error("Error while requesting the webpage '%s': '%r'", req_url, e)