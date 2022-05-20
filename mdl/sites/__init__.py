

from .vqq import QQVideoVC
from .m1905 import M1905VC

_ALL_SITES_VIDEOCONFIG_CLASSES = {'QQVideo': {'class': QQVideoVC, 'instance': None, 'nodejs': True},
                                  'm1905': {'class': M1905VC, 'instance': None, 'nodejs': False}
                                  }


def get_all_sites_vcs():
    return _ALL_SITES_VIDEOCONFIG_CLASSES
