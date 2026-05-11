from .iqiyi import IQiyiVC
from .vqq import QQVideoVC
from .m1905 import M1905VC
from .m3u8 import M3u8VC

_ALL_SITES_VIDEOCONFIG_CLASSES = {'QQVideo': {'class': QQVideoVC, 'instance': None},
                                  'M1905': {'class': M1905VC, 'instance': None},
                                  'IQiyi': {'class': IQiyiVC, 'instance': None},
                                  'M3u8': {'class': M3u8VC, 'instance': None}
                                  }


def get_all_sites_vcs():
    return _ALL_SITES_VIDEOCONFIG_CLASSES
