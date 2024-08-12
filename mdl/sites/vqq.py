import json
import re
import os
import subprocess

from urllib.parse import urlencode

from requests import RequestException

from ..commons import pick_highest_definition, sort_definitions, VideoTypeCodes, VideoTypes, DEFAULT_YEAR
from ..videoconfig import VideoConfig
from ..utils import json_path_get, build_cookiejar_from_kvp

mdl_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class QQVideoPlatforms:
    P10901 = '11'
    P10801 = '10801'  # '10601'
    P10201 = '10201'


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

    _ENCRYPTVER_to_APPVER = {
        '8.1': '3.5.57',
        '9.1': '3.5.57',
        '8.5': '1.27.3'
    }

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
            'uhd': 10208,  # fixme
            'fhd': 10209,
            'shd': 10201,
            'hd': 10212,  # 10202
            'sd': 10203
        },
        QQVideoPlatforms.P10801: {
            'uhd': 321005,  # fixme
            'fhd': 321004,
            'shd': 321003,
            'hd': 321002,
            'sd': 321001
        },
        QQVideoPlatforms.P10201: {
            'uhd': 10219,  # fixme
            'fhd': 10218,
            'shd': 10217,
            'hd': 2,
            'sd': 100001
        }
    }

    _VQQ_FMT2DEFN_MAP = {10209: 'fhd', 10201: 'shd', 10212: 'hd', 10203: 'sd',
                         321004: 'fhd', 321003: 'shd', 321002: 'hd', 321001: 'sd',
                         320090: 'hd', 320089: 'sd'}

    def __init__(self, args, confs):
        super().__init__(args, confs)

        self._COVER_PAT_RE = re.compile(r"var\s+COVER_INFO\s*=\s*(.+?);?var\s+COLUMN_INFO"
                                        r"|\"coverInfo\"\s*:\s*(.+?),\s*\"videoInfo\"",
                                        re.MULTILINE | re.DOTALL | re.IGNORECASE)
        self._VIDEO_INFO_RE = re.compile(r"var\s+VIDEO_INFO\s*=\s*(.+?);?</script>"
                                         r"|\"episodeSinglePlay\".+?\"item_params\"\s*:\s*({.+?})\s*,\s*\"\s*sub_items",
                                         re.MULTILINE | re.DOTALL | re.IGNORECASE)
        self._ALL_LOADED_INFO_RE = re.compile(r"window\.__PINIA__\s*=\s*(.+?);?</script>",
                                              re.MULTILINE | re.DOTALL | re.IGNORECASE)
        self._EP_LIST_RE = re.compile(r"(?:\[{\"list\":)?Array\.prototype\.slice\.call\({\"\d+\":(?:{\"list\":\[)?\[(.+?})\]\]?,.*?\"length\":\d+}\).*?(?=,\"listMeta\")",
                                      re.MULTILINE | re.DOTALL | re.IGNORECASE)
        self._VIDEO_COVER_PREFIX = 'https://v.qq.com/x/cover/'
        self._VIDEO_CONFIG_URL = 'https://vd.l.qq.com/proxyhttp'

        # make sure _VIDEO_URL_PATS has a compiled version, which should have been done in @classmethod is_url_valid
        for pat in self._VIDEO_URL_PATS:
            if pat.get('cpat') is None:
                pat['cpat'] = re.compile(pat['pat'], re.IGNORECASE)

        # get user tokens/cookies from configuration file
        self._regular_token = build_cookiejar_from_kvp(self.confs['regular_user_token'])
        self._vip_token = build_cookiejar_from_kvp(self.confs['vip_user_token'])
        self.user_token = self._vip_token if self._vip_token else self._regular_token
        self.has_vip = True if self._vip_token else False
        self.login_token = self._get_logintoken_from_cookies(self.user_token)

        self.encrypt_ver = self.confs['ckey_ver']
        ckey_js = 'vqq_ckey-' + self.encrypt_ver + '.js'
        self.jsfile = os.path.join(mdl_dir, 'js', ckey_js)

        self.app_ver = self._ENCRYPTVER_to_APPVER[self.encrypt_ver]

        probe_mode_default = 'False'
        probe_mode = self.confs.get('probe_mode') or probe_mode_default
        self.probe_mode = True if probe_mode.lower() == 'true' else False

        use_cdn = self.confs.get('use_cdn')
        self.use_cdn = True if use_cdn and use_cdn.lower() == 'true' else False

        cdn_blacklist = self.confs.get('cdn_blacklist')
        self.cdn_blacklist = tuple(cdn_blacklist.split()) if cdn_blacklist else ()

        self.preferred_defn = self.confs['definition']

    # @classmethod
    # def is_url_valid(cls, url):
    #     return super().is_url_valid(url)

    @staticmethod
    def _get_logintoken_from_cookies(cookies):
        login_token = {'openid': '', 'appid': '', 'access_token': '', 'vuserid': '', 'vusession': ''}

        if cookies:
            for cookie_name in login_token:
                login_token.update({cookie_name: cookies.get('vqq_' + cookie_name, '')})

        login_token['main_login'] = 'qq'

        return login_token

    def _get_video_urls_p10801(self, vid, definition, vurl, referrer):
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

            if data and data.get('dltype'):
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

                    ret_defn = definition
                    if ret_defn not in fmt_names:
                        for defn in self._VQQ_FORMAT_IDS_DEFAULT[QQVideoPlatforms.P10801]:
                            if defn in fmt_names:
                                ret_defn = defn
                                break

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
                            ['%s%s?sdtfrom=v1010' % (prefix, vfilename_new) for prefix in chosen_url_prefixes])
                        urls.append(url_mirrors)
                else:  # 'mp4'
                    if drm == 1 and not self.has_vip:
                        return format_name, ext, urls

                    logo = json_path_get(data, ['vl', 'vi', 0, 'logo'])
                    if logo == 0:  # logo == 0 or drm == 1
                        ext = 'ts'

                        playlist_m3u8 = json_path_get(data, ['vl', 'vi', 0, 'ul', 'ui', -1, 'hls', 'pname'])
                        if not playlist_m3u8:
                            # return self._get_video_urls_p10901(vid, definition)
                            return self._get_video_urls_p10201(vid, definition, vurl, referrer)
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
                        # return self._get_video_urls_p10901(vid, definition)
                        return self._get_video_urls_p10201(vid, definition, vurl, referrer)

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

            if data and data.get('dltype'):
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
                ret_defn = definition  # not necessarily equal to requested `definition`
                if ret_defn not in formats:
                    for defn in self._VQQ_FORMAT_IDS_DEFAULT[QQVideoPlatforms.P10901]:
                        if defn in formats:
                            ret_defn = defn
                            break

                format_id = formats.get(ret_defn) or self._VQQ_FORMAT_IDS_DEFAULT[QQVideoPlatforms.P10901][ret_defn]
                vfilename = json_path_get(data, ['vl', 'vi', 0, 'fn'], '')
                vfn = vfilename.split('.')  # e.g. ['egmovie', 'p201', 'mp4'], ['egmovie', 'mp4']
                ext = vfn[-1]  # video extension, e.g. 'mp4'
                # vfmt = vfn[1]  # e.g. 'p201'
                # fmt_prefix = vfmt[0]  # e.g. 'p' in 'p201'
                vfmt_new = vfn[1][0] + str(format_id % 10000) if len(vfn) == 3 else ''

                fvkey = json_path_get(data, ['vl', 'vi', 0, 'fvkey'])
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
                        'charge': 0
                    }
                    r = self._requester.get('https://h5vv.video.qq.com/getkey', params=params, cookies=self.user_token)
                    if r.status_code == 200:
                        try:
                            key_data = json.loads(r.text[len('QZOutputJson='):-1])
                        except json.JSONDecodeError:
                            # logging
                            return format_name, ext, urls

                        if key_data and isinstance(key_data, dict):
                            vkey = key_data.get('key', fvkey)
                            if not vkey:
                                return format_name, ext, urls
                            url_mirrors = '\t'.join(['%s%s?sdtfrom=v1010&vkey=%s' % (url_prefix, cfilename, vkey)
                                                    for url_prefix in chosen_url_prefixes])
                            if url_mirrors:
                                urls.append(url_mirrors)

                # check if the URLs for the file parts have all been successfully obtained
                if len(keyids) == len(urls):
                    format_name = ret_defn

        return format_name, ext, urls

    def _get_video_urls_p10201(self, vid, definition, vurl, referrer):
        urls = []
        ext = None
        format_name = None

        nodejs = self.args['node']
        cmd_nodejs = [nodejs, self.jsfile]
        with subprocess.Popen(cmd_nodejs, bufsize=1, universal_newlines=True, encoding='utf-8',
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE) as node_proc:
            ckey_req = ' '.join([QQVideoPlatforms.P10201, self.app_ver, vid, vurl, referrer])
            node_proc.stdin.write(ckey_req)
            node_proc.stdin.write(r'\n')
            node_proc.stdin.flush()
            ckey_resp = node_proc.stdout.readline().rstrip(r'\r\n')
            ckey, tm, guid, flowid = ckey_resp.split()

            vinfoparam = {
                'otype': 'ojson',
                'isHLS': 1,
                'charge': 0,
                'fhdswitch': 0,
                'show1080p': 1,
                'defnpayver': 7,
                'sdtfrom': 'v1010',
                'host': 'v.qq.com',
                'vid': vid,
                'defn': definition,
                'platform': QQVideoPlatforms.P10201,
                'appVer': self.app_ver,
                'refer': referrer,
                'ehost': vurl,
                'logintoken': json.dumps(self.login_token, separators=(',', ':')),
                'encryptVer': self.encrypt_ver,
                'guid': guid,
                'flowid': flowid,
                'tm': tm,
                'cKey': ckey,
                'dtype': 1,
                #'drm': 40
            }
            params = {
                'buid': 'vinfoad',
                'vinfoparam': urlencode(vinfoparam)
            }

            try:
                r = self._requester.post(self._VIDEO_CONFIG_URL, json=params, cookies=self.user_token)
                r.raise_for_status()
                if r.status_code != 200:
                    raise RequestException("Unexpected status code %i" % r.status_code)

                try:
                    data = json.loads(r.text)
                    if data:
                        data = json.loads(data.get('vinfo'))
                except json.JSONDecodeError as e:
                    self._logger.error("Received ill-formed video config info for '%i': '%r'", vid, e)
                    return format_name, ext, urls

                if data and data.get('dltype'):
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
                    ret_defn = definition  # not necessarily the requested `definition`
                    if ret_defn not in formats:
                        ret_defn = pick_highest_definition(formats)

                    new_format_id = formats.get(ret_defn) or self._VQQ_FORMAT_IDS_DEFAULT[QQVideoPlatforms.P10201][ret_defn]
                    vfilename = json_path_get(data, ['vl', 'vi', 0, 'fn'], '')
                    vfn = vfilename.split('.')  # e.g. ['egmovie', 'p201', 'mp4'], ['egmovie', 'mp4']
                    ext = vfn[-1]  # video extension, e.g. 'mp4'
                    fmt_prefix = vfn[1][0] if len(vfn) == 3 else 'p'  # e.g. 'p' in 'p201'
                    vfmt_new = fmt_prefix + str(new_format_id % 10000)

                    # fvkey = json_path_get(data, ['vl', 'vi', 0, 'fvkey'])
                    fc = json_path_get(data, ['vl', 'vi', 0, 'cl', 'fc'])
                    keyid = json_path_get(data, ['vl', 'vi', 0, 'cl', 'ci', 0, 'keyid']) if fc else json_path_get(data, ['vl', 'vi', 0, 'cl', 'keyid'])
                    orig_format_id = int(keyid.split('.')[1])

                    max_fc = 80  # large enough try limit such that we don't miss any clip
                    for idx in range(1, max_fc + 1):
                        keyid_new = keyid.split('.')
                        keyid_new[0] = vfn[0]
                        if len(keyid_new) == 3:
                            keyid_new[1:] = [vfmt_new, str(idx)]
                            keyid_new = '.'.join(keyid_new)
                        else:
                            if int(keyid_new[1]) != new_format_id:
                                if len(vfn) == 3:
                                    vfn[1] = vfn[1][0] + str(new_format_id)
                                else:
                                    vfn.insert(1, vfmt_new)
                            keyid_new = '.'.join(vfn[:-1])
                        cfilename = keyid_new + '.' + ext

                        ckey_req = ' '.join([QQVideoPlatforms.P10201, self.app_ver, vid, vurl, referrer, r'\n'])
                        node_proc.stdin.write(ckey_req)
                        node_proc.stdin.flush()
                        ckey_resp = node_proc.stdout.readline().rstrip(r'\r\n')
                        ckey, tm, guid, flowid = ckey_resp.split()

                        vkeyparam = {
                            'otype': 'ojson',
                            'vid': vid,
                            'format': new_format_id,
                            'filename': cfilename,
                            'platform': QQVideoPlatforms.P10201,
                            'appVer': self.app_ver,
                            'sdtfrom': 'v1010',
                            'guid': guid,
                            'flowid': flowid,
                            'tm': tm,
                            'refer': referrer,
                            'ehost': vurl,
                            'logintoken': json.dumps(self.login_token, separators=(',', ':')),
                            'encryptVer': self.encrypt_ver,
                            'cKey': ckey
                        }
                        params = {
                            'buid': 'onlyvkey',
                            'vkeyparam': urlencode(vkeyparam)
                        }

                        try:
                            r = self._requester.post(self._VIDEO_CONFIG_URL, json=params, cookies=self.user_token)
                            r.raise_for_status()
                            if r.status_code != 200:
                                raise RequestException("Unexpected status code %i" % r.status_code)

                            try:
                                key_data = json.loads(r.text)
                                if key_data:
                                    key_data = json.loads(key_data.get('vkey'))
                            except json.JSONDecodeError as e:
                                self._logger.error("Received ill-formed video key data for the clip '%s' from video '%i': '%r'", cfilename, vid, e)
                                return format_name, ext, urls

                            if key_data and isinstance(key_data, dict):
                                vkey = key_data.get('key')
                                if not vkey:
                                    break

                                keyid = key_data.get('keyid')
                                keyid_nseg = len(keyid.split('.'))
                                ffilename = key_data.get('filename')
                                if ffilename:
                                    if keyid_nseg == 3:
                                        cfilename = ffilename.split('.')
                                        cfilename.insert(-1, str(idx))
                                        cfilename = '.'.join(cfilename)
                                    else:
                                        cfilename = ffilename

                                url_mirrors = '\t'.join(['%s%s?sdtfrom=v1010&vkey=%s' % (url_prefix, cfilename, vkey)
                                                        for url_prefix in chosen_url_prefixes])
                                if url_mirrors:
                                    urls.append(url_mirrors)

                                if ((orig_format_id == new_format_id or not self.probe_mode) and fc == idx) or (not fc and keyid_nseg != 3):
                                    break
                        except RequestException as e:
                            self._logger.error("Error while requesting the key for the clip '%s' from video '%i': '%r'", cfilename, vid, e)
                            return format_name, ext, urls

                    # hopefully the URLs for the file parts have all been successfully obtained
                    if len(urls) > 0:
                        format_name = ret_defn
            except RequestException as e:
                self._logger.error("Error while requesting the config info of video '%i': '%r'", vid, e)

        return format_name, ext, urls

    def _get_video_urls_p10201_ts(self, vid, definition, vurl, referrer):
        urls = []
        ext = None
        format_name = None

        nodejs = self.args['node']
        cmd_nodejs = [nodejs, self.jsfile]
        with subprocess.Popen(cmd_nodejs, bufsize=1, universal_newlines=True, encoding='utf-8',
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE) as node_proc:
            ckey_req = ' '.join([QQVideoPlatforms.P10201, self.app_ver, vid, vurl, referrer])
            node_proc.stdin.write(ckey_req)
            node_proc.stdin.write(r'\n')
            node_proc.stdin.flush()
            ckey_resp = node_proc.stdout.readline().rstrip(r'\r\n')
            ckey, tm, guid, flowid = ckey_resp.split()

            vinfoparam = {
                'otype': 'ojson',
                'isHLS': 1,
                'charge': 0,
                'fhdswitch': 0,
                'show1080p': 1,
                'defnpayver': 7,
                'sdtfrom': 'v1010',
                'host': 'v.qq.com',
                'vid': vid,
                'defn': definition,
                'platform': QQVideoPlatforms.P10201,
                'appVer': self.app_ver,
                'refer': referrer,
                'ehost': vurl,
                'logintoken': json.dumps(self.login_token, separators=(',', ':')),
                'encryptVer': self.encrypt_ver,
                'guid': guid,
                'flowid': flowid,
                'tm': tm,
                'cKey': ckey,
                'dtype': 3,
                'spau': 1,
                'spaudio': 68,
                'spwm': 1,
                'sphls': 2,
                'sphttps': 1,
                'clip': 4,
                'spsrt': 2,
                'spvvpay': 1,
                'spadseg': 3,
                'spav1': 15,
                'hevclv': 28,
                'spsfrhdr': 100,
                'spvideo': 1044,
                # 'drm': 40,
                # 'spm3u8tag': 67,
                # 'spmasterm3u8': 3
            }
            params = {
                'buid': 'vinfoad',
                'vinfoparam': urlencode(vinfoparam)
            }

            try:
                r = self._requester.post(self._VIDEO_CONFIG_URL, json=params, cookies=self.user_token)
                r.raise_for_status()
                if r.status_code != 200:
                    raise RequestException("Unexpected status code %i" % r.status_code)

                try:
                    data = json.loads(r.text)
                    if data:
                        data = json.loads(data.get('vinfo'))
                except json.JSONDecodeError as e:
                    self._logger.error("Received ill-formed video config info for '%i': '%r'", vid, e)
                    return format_name, ext, urls

                if data and data.get('dltype'):
                    url_prefixes = []
                    for url_dic in json_path_get(data, ['vl', 'vi', 0, 'ul', 'ui'], []):
                        if isinstance(url_dic, dict):
                            url = url_dic.get('url')
                            if url and not url.startswith(self.cdn_blacklist):
                                if not url.endswith('/'):
                                    url = url[:url.rfind('/')+1]
                                url_prefixes.append(url)

                    chosen_url_prefixes = [prefix for prefix in url_prefixes if
                                           prefix[:prefix.find('/', 8)].endswith('.tc.qq.com')]
                    if not chosen_url_prefixes:
                        chosen_url_prefixes = url_prefixes

                    if self.use_cdn:
                        # use all URL prefixes but with default servers coming before CDN mirrors
                        cdn = [prefix for prefix in url_prefixes if prefix not in chosen_url_prefixes]
                        chosen_url_prefixes += cdn

                    drm = json_path_get(data, ['vl', 'vi', 0, 'drm'])
                    preview = data.get('preview')

                    formats_id2nm = {fmt.get('id'): fmt.get('name') for fmt in json_path_get(data, ['fl', 'fi'], [])}
                    formats_nm2id = {fmt_nm: fmt_id for fmt_id, fmt_nm in formats_id2nm.items()}
                    keyid = json_path_get(data, ['vl', 'vi', 0, 'keyid'], '')

                    vfilename = json_path_get(data, ['vl', 'vi', 0, 'fn'], '')
                    vfn = vfilename.rpartition('.')  # e.g. ['egmovie.f323013001', '.', 'ts']
                    ext = vfn[-1]  # video extension, e.g. 'ts' 'mp4'

                    ret_defn = ''  # not necessarily equal to requested `definition`

                    if ext == 'ts':
                        if drm == 1 and not preview and not self.has_vip:
                            return format_name, ext, urls

                        # determine the true definition `ret_defn` from the returned formats
                        key_format_id = keyid.split('.')[-1]
                        try:
                            key_format_id = int(key_format_id)
                            ret_defn = formats_id2nm.get(key_format_id) or ret_defn
                        except ValueError:
                            pass

                        if not ret_defn:
                            for format_defn in sort_definitions(formats_nm2id):
                                format_id = formats_nm2id.get(format_defn)
                                ckey_req = ' '.join([QQVideoPlatforms.P10201, self.app_ver, vid, vurl, referrer, r'\n'])
                                node_proc.stdin.write(ckey_req)
                                node_proc.stdin.flush()
                                ckey_resp = node_proc.stdout.readline().rstrip(r'\r\n')
                                ckey, tm, guid, flowid = ckey_resp.split()

                                vkeyparam = {
                                    'otype': 'ojson',
                                    'vid': vid,
                                    'format': format_id,
                                    'filename': vfilename,
                                    'platform': QQVideoPlatforms.P10201,
                                    'appVer': self.app_ver,
                                    'sdtfrom': 'v1010',
                                    'guid': guid,
                                    'flowid': flowid,
                                    'tm': tm,
                                    'refer': referrer,
                                    'ehost': vurl,
                                    'logintoken': json.dumps(self.login_token, separators=(',', ':')),
                                    'encryptVer': self.encrypt_ver,
                                    'cKey': ckey
                                }
                                params = {
                                    'buid': 'onlyvkey',
                                    'vkeyparam': urlencode(vkeyparam)
                                }

                                try:
                                    r = self._requester.post(self._VIDEO_CONFIG_URL, json=params, cookies=self.user_token)
                                    if r.status_code != 200:
                                        raise RequestException("Unexpected status code %i" % r.status_code)

                                    try:
                                        key_data = json.loads(r.text)
                                        if key_data:
                                            key_data = json.loads(key_data.get('vkey'))
                                    except json.JSONDecodeError as e:
                                        self._logger.error("Received ill-formed video key data for the file '%s' of video '%i': '%r'", vfilename, vid, e)
                                        return format_name, ext, urls

                                    if key_data and isinstance(key_data, dict):
                                        vkey = key_data.get('key')
                                        if not vkey:
                                            return format_name, ext, urls

                                        cfilename = key_data.get('filename', '')
                                        if cfilename and cfilename == vfilename:
                                            ret_defn = format_defn
                                            break
                                except RequestException as e:
                                    self._logger.error("Error while requesting the key for the file '%s' of video '%i': '%r'", vfilename, vid, e)
                                    return format_name, ext, urls

                        fc = json_path_get(data, ['vl', 'vi', 0, 'fc'])  # always >= 1?
                        # start = 0 if fc == 0 else 1  # start counting number of the video clip file indexes
                        start = 1

                        for idx in range(start, fc + 1):
                            vfilename_new = '.'.join([vfn[0], str(idx), 'ts'])
                            url_mirrors = '\t'.join(
                                ['%s%s?sdtfrom=v1010' % (prefix, vfilename_new) for prefix in chosen_url_prefixes])
                            urls.append(url_mirrors)
                    else:  # 'mp4'
                        if drm == 1 and not self.has_vip:
                            return format_name, ext, urls

                        return self._get_video_urls_p10201(vid, definition, vurl, referrer)

                    format_name = ret_defn
            except RequestException as e:
                self._logger.error("Error while requesting the config info of video '%i': '%r'", vid, e)

        return format_name, ext, urls

    def _get_video_urls(self, vid, definition, vurl, referrer):
        if self.no_logo:
            # return self._get_video_urls_p10801(vid, definition, vurl, referrer)
            return self._get_video_urls_p10201_ts(vid, definition, vurl, referrer)
        else:
            # return self._get_video_urls_p10901(vid, definition)
            return self._get_video_urls_p10201(vid, definition, vurl, referrer)

    def _extract_video_cover_info(self, regex, text):
        result = (None, None)

        cover_match = regex.search(text)
        if cover_match:
            info = {}
            cover_group = cover_match.group(1) or cover_match.group(2)
            try:
                cover_info = json.loads(cover_group.replace('undefined', 'null'))
            except json.JSONDecodeError:
                return result
            if cover_info and isinstance(cover_info, dict):
                info['title'] = cover_info.get('title', '') or cover_info.get('title_new', '')
                info['year'] = cover_info.get('year') or (cover_info.get('publish_date') or '').split('-')[0]
                info['cover_id'] = cover_info.get('cover_id', '')

                type_id = int(cover_info.get('type') or VideoTypeCodes.MOVIE)
                info['type'] = self._VQQ_TYPE_CODES.get(type_id, VideoTypes.MOVIE)

                video_id = cover_info.get('vid')
                if video_id is None:
                    video_ids = cover_info.get('video_ids') or []
                    normal_ids = [{'V': vid, 'E': ep} for ep, vid in enumerate(video_ids, start=1)]
                else:
                    normal_ids = [{"V": video_id, "E": 1}]
                info['normal_ids'] = normal_ids

                result = (info, cover_match.end())

        return result

    def _update_video_cover_info(self, cover_info, regex, text):
        match = regex.search(text)
        if match:
            matched = match.group(1)
            matched_norm = re.sub(self._EP_LIST_RE, r'[{"list":[[\1]]}]', matched).replace('undefined', 'null')
            try:
                conf_info = json.loads(matched_norm)
            except json.JSONDecodeError:
                return

            if conf_info:
                year = json_path_get(conf_info, ['introduction', 'introData', 'list', 0, 'item_params', 'year']) \
                       or json_path_get(conf_info, ['introduction', 'introData', 'list', 0, 'item_params', 'show_year'])
                if year and (not cover_info['year'] or cover_info['year'] != year):
                    cover_info['year'] = year

                # set to the probably more specific title
                ep_list = json_path_get(conf_info, ['episodeMain', 'listData', 0, 'list'], [])
                if not ep_list:
                    return
                ep_list = ep_list[0]

                if len(ep_list) >= len(cover_info['normal_ids']):  # ensure the full list of episodes
                    cover_info['normal_ids'] = [{'V': item['vid'],
                                                 'E': ep,
                                                 'title': item.get('playTitle') or item.get('title', '')
                                                 # exclude the types of videos that are unlikely to have meaningful episode names
                                                 if cover_info['type'] not in [VideoTypes.TV, ] else ''}
                                                for ep, item in enumerate(ep_list, start=1)]

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
            "E": 1,
            # "title": ""
        }, {
            "V": "q0024a27g9j",
            "E": 2,
            # "title": ""
        }]
        }"""

        info = None

        try:
            r = self._requester.get(cover_url)
            if r.status_code != 200:
                raise RequestException("Unexpected status code %i" % r.status_code)

            r.encoding = 'utf-8'
            info, pos_end = self._extract_video_cover_info(self._COVER_PAT_RE, r.text)
            if info:
                if not info['normal_ids']:
                    info, _ = self._extract_video_cover_info(self._VIDEO_INFO_RE, r.text[pos_end:])
            else:
                info, _ = self._extract_video_cover_info(self._VIDEO_INFO_RE, r.text)

            if info:
                self._update_video_cover_info(info, self._ALL_LOADED_INFO_RE, r.text)

                info['episode_all'] = len(info['normal_ids']) if info['normal_ids'] else 1
                info['referrer'] = cover_url  # set the Referer to the address of the cover web page
        except RequestException as e:
            self._logger.error("Error while requesting the webpage '%s': '%r'", cover_url, e)

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
            "url": "https://v.qq.com/x/cover/nhtfh14i9y1egge.html",  # original request URL
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

            format_name, ext, urls = self._get_video_urls(vi['V'], self.preferred_defn, cover_info['url'], cover_info['referrer'])
            if format_name:  # may not be same as preferred definition
                fmt = dict(ext=ext, urls=urls)
                vi['defns'].setdefault(format_name, []).append(fmt)
