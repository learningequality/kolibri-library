  
import json
import logging
import os
import re
import youtube_dl

from pressurecooker.youtube import YouTubeResource
from le_utils.constants.languages import getlang_by_name, getlang

LOGGER = logging.getLogger("AimHiUtils")
LOGGER.setLevel(logging.DEBUG)

YOUTUBE_CACHE_DIR = os.path.join('chefdata', 'youtubecache')
YOUTUBE_ID_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?(?P<youtube_id>[A-Za-z0-9\-=_]{11})'
)
YOUTUBE_PLAYLIST_URL_FORMAT = "https://www.youtube.com/playlist?list={0}"

VIDEO_DESCRIPTION_JSON_PATH = os.path.join('chefdata', 'youtubecache', 'video_description.json')
AIMHI_THUMBNAIL_PATH = os.path.join("files", "AimHi_logo.png")

PLAYLIST_MAP = [
  "PLr5n3ojAJWjQE8vTaPZRq-3FzFfvOkYDu",   #Maths
  "PLr5n3ojAJWjSNVp6jrlwXPz5MyFArv6oO",   #Biology
  "PLr5n3ojAJWjRGQ1DnnIqDrIXKuuNydGid",   #Physics
  "PLr5n3ojAJWjTrFw5u6JYnoo--R5L9PQrh",   #Inspired Guest Full Recordings
  "PLr5n3ojAJWjStwX7rM5UFPKz6pJAt_vyp",   #Learning Adventure HiLights
  "PLr5n3ojAJWjQf_UjAPl_q5j9KIrTZm21u",   #Inspired Guest HiLights
  "PLr5n3ojAJWjSVh9mgusLb6npGNnFif_Sw",   #Inspiring Guests
  "PLr5n3ojAJWjRiuPrUAAveWrrqnNPPNzYK",   #Philosophy
  "PLr5n3ojAJWjSVnG_EK1xF3rW1Lo0N2qwA",   #HiLights
  "PLr5n3ojAJWjQEiRIuHlRoN7rBDKG6GbvH",   #Science
  "PLr5n3ojAJWjTkqDW49ew1u7vsbVzM5Uub",   #Geography
  "PLr5n3ojAJWjRSuu4s5Vu1CEN0rkgXZ-VA",   #English
  "PLr5n3ojAJWjRDmRmIVAsD4MSEt7wMSOGr",   #What is Cancer?
  "PLr5n3ojAJWjRgakYChgf-iHEwyiEVwtVr",   #Politics
]