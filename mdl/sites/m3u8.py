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
        defn = "hd"

        ts_urls = self._get_ts_playlist(vi['url'])
        if ts_urls:
            vi['defns'].setdefault(defn, []).append(dict(ext="ts", urls=ts_urls))

    @staticmethod
    def _purge_media_playlist(m3u8_text):
        segs = m3u8_text.splitlines()
        nsegs = len(segs)
        purged = []
        i = 0
        inbetween = False

        # skip the header
        while i < nsegs and (not segs[i] or segs[i].startswith("#")):
            i += 1

        # filter out the DISCONTINUITY
        for j in range(i, nsegs):
            if not segs[j]:
                continue
            if segs[j].startswith("#EXT-X-DISCONTINUITY"):
                inbetween = not inbetween
                continue
            if inbetween or segs[j].startswith("#"):
                continue

            purged.append(segs[j])

        return purged

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
                            mpeg_urls = [urljoin(playlist, ts) for ts in self._purge_media_playlist(r.text) if
                                         ts and not ts.startswith('#') and (ts.endswith('.ts') or '.ts?' in ts)]
                            return mpeg_urls
                else:
                    raise RequestException("Unexpected status code %i" % r.status_code)
        except RequestException as e:
            self._logger.error("Failed to fetch '%s': '%r'", playlist, e)
