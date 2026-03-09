# sushi-chef-ms-digital-literacy-english
Import script for the English content from Microsoft Digital Literacy courses https://www.microsoft.com/en-us/digital-literacy into the Kolibri platform

This courses can be downloaded either in Scorm format or in a zip format containing video files and their subtitles. For this script to work, both formats are downloaded: Scorm contains exercises, video files, descriptions and titles for the videos. However it does not contain subtitles. To get video subtitles the zipped video files are downloaded too, thus video files are downloaded twice.
The resulting size of the directory where all the videos are downloaded is 9Gbytes, plus 3 Gbytes in the directory where videos are processed to reduce its size, resulting in a final size of less than 300 Mb for the channel.

This script uses LibreOffice to convert MS Office files to pdf. For this reason, in a Linux system, these Debian packages must be instaled:
libreoffice
default-jre
