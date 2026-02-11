
VIDEO_DEFINITIONS = ('suhd', 'uhd', 'dolby', 'hdr10', 'fhd', 'shd', 'hd', 'sd')  # from highest to lowest

DEFAULT_YEAR = '1900'

#VIDEO_EXTENSIONS = ('mp4', 'flv', 'mpg', 'ts')  # stream segment MIME extensions

# User-Agent strings for various platforms


class VideoURLType:
    COVER = 'Playlist'  # e.g. 'https://v.qq.com/x/cover/nhtfh14i9y1egge.html' ''https://v.qq.com/detail/n/nhtfh14i9y1egge.html''
    PAGE = 'EPISODE'    # e.g. 'https://v.qq.com/x/cover/nhtfh14i9y1egge/d00249ld45q.html' 'https://v.qq.com/x/page/d00249ld45q.html'


class VideoTypes:
    MOVIE = "MOV"
    TV = "TV"
    CARTOON = "Cartoon"
    SPORTS = "Sports"
    ENTMT = "Ent"
    GAME = "Game"
    DOCU = "Docu"
    VARIETY = "Variety"
    MUSIC = "Music"
    NEWS = "News"
    FINANCE = "Finance"
    FASHION = "Fashion"
    TRAVEL = "Travel"
    EDUCATION = "Edu"
    TECH = "Tech"
    AUTO = "Auto"
    HOUSE = "House"
    LIFE = "Life"
    FUN = "Fun"
    BABY = "Baby"
    CHILD = "Child"
    ART = "Art"


class VideoTypeCodes:
    """ Enumeration of video types
    """
    MOVIE = 1
    TV = 2
    CARTOON = 3
    SPORTS = 4
    ENTMT = 5
    GAME = 6
    DOCU = 9
    VARIETY = 10
    MUSIC = 22
    NEWS = 23
    FINANCE = 24
    FASHION = 25
    TRAVEL = 26
    EDUCATION = 27
    TECH = 28
    AUTO = 29
    HOUSE = 30
    LIFE = 31
    FUN = 43
    BABY = 60
    CHILD = 106
    ART = 111


def pick_highest_definition(defns):
    """"
    Pick the definition format of the highest quality from given `defns`

    :param defns: List of definition formats to pick the definition from
    :type defns: Iterable[str]
    :return: The definition format
    :rtype: str
    """
    for definition in VIDEO_DEFINITIONS:
        if definition in defns:
            return definition


def sort_definitions(defns, reverse=True):
    """
    Sort the given set of definition formats

    :param defns: List of definition formats to sort
    :type defns: Iterable[str]
    :param reverse: The order in which the definitions are sorted. If set to `True`, then the definitions are arranged
        from the highest quality to the lowest
    :type reverse: bool
    :return: The sorted definitions
    :rtype: list
    """
    sorted_defns = []
    full_defns = VIDEO_DEFINITIONS if reverse else VIDEO_DEFINITIONS[::-1]
    for defn in full_defns:
        if defn in defns:
            sorted_defns.append(defn)

    return sorted_defns
