There are a number of issues with the code at the moment:

`recompress_zip.py` works on the existing .zip.final.zip files, because downloading the videos takes a long time.

We manually deleted a number of videos from zip files to try to bring the zip files below 250 megabytes
A number of zip files are still too large -- perhaps the actual limit is 200 megabytes?

We should consider moving the videos outside the zip.
