import re
from urllib.parse import urljoin

from requests import RequestException

from mdl.utils import normalize_filename
from mdl.videoconfig import VideoConfig
from mdl.commons import VideoTypes, DEFAULT_YEAR


class M3u8VC(VideoConfig):
    _VIDEO_URL_PATS = [
        {'pat': r'^https?://.+/.+\.m3u8',
         'eg': 'https://cdn.example-tv.com/20251206/2100k/hls/ts.m3u8'}
    ]
    SOURCE_NAME = "M3u8"
    VC_NAME = "M3u8"

    _ENCRYPTION_METHODS = set(["NONE", "AES-128"])

    def __init__(self, args, confs):
        super().__init__(args, confs)

    def get_video_cover_info(self, url):
        vtitle = normalize_filename(url)
        ctitle = "mdl-downloads"  # shared by all m3u8 downloads
        vid = "mdlvid1900"
        cid = "mdlcid1900"

        cover_info = {
            'url': url,
            'referrer': url,
            'title': ctitle,
            'year': DEFAULT_YEAR,
            'cover_id': cid,
            'type': VideoTypes.MOVIE,
            'normal_ids': [{'V': vid, 'E': 1, 'title': vtitle, 'defns': {}, 'url': url, 'referrer': url}],
            'episode_all': 1
        }

        return cover_info

    def update_video_dwnld_info(self, vi):
        """
        {
            "url": "",
            "referrer": "",
            "title": "",
            "year": "",
            "type": VideoTypes.MOVIE,
            "cover_id": "",
            "episode_all": 1,
            "normal_ids": [{
                "V": "",
                "E": 1,
                "title": "",
                "url": "",
                "referrer": "",
                "defns": {
                    "hd": [{
                        "ext": "ts",
                        "urls": ["https://t.com/hdv1.1.ts", "https://t.com/hdv1.2.ts"],
                        "seckeys": [{"algo": "AES-128", "key": b"16-octet key bin", "iv": b"128-bit unsigned"},
                                    {"algo": "NONE", "key": None, "iv": None}
                                   ]
                    }],
                    "sd": [{
                        "ext": "ts",
                        "urls": ["https://t.com/sdv1.1.ts", "https://t.com/sdv1.2.ts"]
                    }]
                }
            }]
        }
        """
        defn = "hd"

        ts_urls, seckeys = self._get_ts_playlist(vi['url'])
        if ts_urls:
            fmt = dict(ext="ts", urls=ts_urls)
            if seckeys:
                fmt['seckeys'] = seckeys
                if not all([seckey['algo'] in self._ENCRYPTION_METHODS for seckey in seckeys]):
                    self._logger.error("Unsupported encryption method found for '%s'", vi['url'])
                    return
            vi['defns'].setdefault(defn, []).append(fmt)

    def _get_seckey(self, ext_x_key, playlist_url):
        _, _, cipher = ext_x_key.partition(":")
        attribs = cipher.split(",")
        kdict = {k: v for k, _, v in [attrib.partition("=") for attrib in attribs]}

        seckey = {'algo': "NONE", 'key': None, 'iv': None}

        algo = kdict.get('METHOD', 'NONE')
        if algo == "NONE":
            return seckey
        seckey['algo'] = algo.upper()

        iv = kdict.get('IV')
        if iv:
            iv = bytes.fromhex(iv[2:])
            seckey['iv'] = iv

        uri = kdict.get('URI')
        if uri:
            uri = urljoin(playlist_url, uri[1:-1])
            try:
                r = self._requester.get(uri)
                if r.status_code == 200:
                    seckey['key'] = r.content
                else:
                    raise RequestException("Unexpected status code %i" % r.status_code)
            except RequestException as e:
                self._logger.error("Failed to fetch '%s': '%r'", uri, e)

        return seckey

    def _purge_media_playlist(self, m3u8_text, playlist_url):
        segs = m3u8_text.splitlines()
        nsegs = len(segs)
        purged = []
        i = 0
        inbetween = False

        media_sequence = 0
        seckeys, seckey = [], None

        # skip the header
        while i < nsegs and (not segs[i] or segs[i].startswith("#")):
            if segs[i] and segs[i].startswith("#EXT-X-MEDIA-SEQUENCE"):
                media_sequence = int(segs[i].split(":")[1])
            if segs[i] and segs[i].startswith("#EXT-X-KEY"):
                seckey = self._get_seckey(segs[i], playlist_url)
                seckeys = []

            i += 1

        # filter out the DISCONTINUITY
        for j in range(i, nsegs):
            if not segs[j]:
                continue
            if segs[j].startswith("#EXT-X-DISCONTINUITY"):
                inbetween = not inbetween
                continue
            if inbetween:
                continue
            if segs[j].startswith("#"):
                if segs[j].startswith("#EXT-X-KEY"):
                    if seckey is None:
                        seckey = {'algo': "NONE", 'key': None, 'iv': None}
                        seckeys = [seckey] * len(purged)
                    seckey = self._get_seckey(segs[j], playlist_url)

                continue

            if seckey:
                seckeys.append(seckey.copy())
            purged.append(urljoin(playlist_url, segs[j]))

        return purged, seckeys, media_sequence

    def _pick_highest_bandwidth_m3u8(self, playlist_variants, playlist_url):
        bandwidth, m3u, sessionkey = 0, "", None
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
                if stream and stream.startswith("#EXT-X-SESSION-KEY:"):
                    sessionkey = self._get_seckey(stream, playlist_url)
                i += 1

        return bandwidth, m3u, sessionkey

    def _get_ts_playlist(self, m3u8_url):
        sessionkey = None
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
                            _, m3u, sessionkey = self._pick_highest_bandwidth_m3u8(r.text, playlist)
                            playlist = urljoin(playlist, m3u)
                            break
                        elif line.startswith("#EXTINF:"):  # in media playlist
                            mpeg_urls, seckeys, media_sequence = self._purge_media_playlist(r.text, playlist)
                            if not seckeys and sessionkey:
                                seckeys = [sessionkey.copy() for _ in range(len(mpeg_urls))]
                            if seckeys:
                                for i, seckey in enumerate(seckeys):
                                    if seckey['algo'] != "NONE" and seckey['iv'] is None:
                                        seckey['iv'] = (media_sequence + i).to_bytes(16, 'big')

                            return mpeg_urls, seckeys
                else:
                    raise RequestException("Unexpected status code %i" % r.status_code)
        except RequestException as e:
            self._logger.error("Failed to fetch '%s': '%r'", playlist, e)

        return [], []
