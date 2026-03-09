#!/usr/bin/env python
import pickle

import youtube_dl

url = 'https://vimeo.com/firdauskharas'
ydl_options = {
    #'outtmpl': '%(title)s-%(id)s.%(ext)s',
    'writethumbnail': False,
    'no_warnings': True,
    'continuedl': False,
    'restrictfilenames':True,
    'quiet': False,
    'format': "bestvideo[height<={maxheight}][ext=mp4]+bestaudio[ext=m4a]/best[height<={maxheight}][ext=mp4]".format(maxheight='720'),
}


with youtube_dl.YoutubeDL(ydl_options) as ydl:
    try:
        ydl.add_default_info_extractors()
        info = ydl.extract_info(url, download=False)
    except (youtube_dl.utils.DownloadError,youtube_dl.utils.ContentTooShortError,youtube_dl.utils.ExtractorError) as e:
        print('error_occured')

with open('chocmoose_info.pickle', 'wb') as handle:
    pickle.dump(info, handle, protocol=pickle.HIGHEST_PROTOCOL)

# with open('chocmoose_info.pickle', 'rb') as handle:
#     info = pickle.load(handle)

