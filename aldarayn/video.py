import youtube_dl
from ricecooker.classes.nodes import VideoNode
from ricecooker.classes.files import WebVideoFile, SubtitleFile
youtube = youtube_dl.YoutubeDL({"noplaylist": True, "quiet": True})

# keys: ['id', 'uploader', 'uploader_id', 'uploader_url', 'channel_id', 'channel_url', 'upload_date', 'license', 'creator', 'title', 'alt_title', 'thumbnail', 'description', 'categories', 'tags', 'subtitles', 'automatic_captions', 'duration', 'age_limit', 'annotations', 'chapters', 'webpage_url', 'view_count', 'like_count', 'dislike_count', 'average_rating', 'formats', 'is_live', 'start_time', 'end_time', 'series', 'season_number', 'episode_number', 'track', 'artist', 'extractor', 'webpage_url_basename', 'extractor_key', 'playlist', 'playlist_index', 'thumbnails', 'display_id', 'requested_subtitles', 'requested_formats', 'format', 'format_id', 'width', 'height', 'resolution', 'fps', 'vcodec', 'vbr', 'stretched_ratio', 'acodec', 'abr', 'ext']



def acquire_video_node(url, license, **options):
    info = youtube.extract_info(url, download=False)
    subtitles=info.get("subtitles")
    assert not info.get("subtitles"), "Implement Subtitles for {}".format(info['id'])
    videofile = WebVideoFile(web_url = url,
                             high_resolution = False,
                             download_settings={"noplaylist": True, "quiet": True})
    video_data = {
                    "source_id": info['id'],
                    "title": info['title'],
                    "author": info.get('author'),
                    "license": license, # mandatory -- could derive, maybe...
                    "description": info.get('description'),
                    "derive_thumbnail":False,
                    "thumbnail":info.get("thumbnail"),
                    "files":[videofile],
                }
    video_data.update(**options)  # replace if we're given data
    videonode = VideoNode(**video_data)
    return videonode

if __name__ == "__main__":
    acquire_video_info("https://www.youtube.com/watch?v=oHg5SJYRHA0", license = "CC BY")
