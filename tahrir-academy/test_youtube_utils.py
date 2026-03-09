
import youtube_dl
from youtube_utils.cache import Db
from youtube_utils.youtube import Client, CachingClient


with Db('.cache', 'tahrirchannels') as cache:
    yt = Client(youtube_dl.YoutubeDL(dict(verbose=True, no_warnings=True, writesubtitles=True, allsubtitles=True)))
    youtube = CachingClient(yt, cache)
    print(youtube.get_video_data('mOpCL3ggpCQ'))
