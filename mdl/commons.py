from enum import Enum

VIDEO_DEFINITIONS = {'fhd': '1080P', 'shd': '720P', 'hd': '480P', 'sd': '270P'}  # from highest to lowest

#VIDEO_EXTENSIONS = ('mp4', 'flv', 'mpg', 'ts')  # stream segment MIME extensions

# User-Agent strings for various platforms


class VideoTypeCodes(Enum):
    """ Enumeration of video types
    """
    MOVIE = "MOV"
    TV = "TV"

