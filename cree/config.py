import os

DOWNLOAD_DIRECTORY = os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "downloads"])
# Create download directory if it doesn't already exist
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

# Update with the directory with the pdfs you'd like to scrape
FOLDER = 'D:\\Kolibri CREE\\CREE'
