from enum import Enum

VIDEO_DEFINITIONS = ('fhd', 'shd', 'hd', 'sd')  # from highest to lowest

#VIDEO_EXTENSIONS = ('mp4', 'flv', 'mpg', 'ts')  # stream segment MIME extensions

# User-Agent strings for various platforms


class VideoTypeCodes(Enum):
    """ Enumeration of video types
    """
    MOVIE = "MOV"
    TV = "TV"

