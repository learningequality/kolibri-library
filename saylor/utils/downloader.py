import asyncio
import os
import requests
import time

from pyppeteer import launch

from requests_file import FileAdapter
from ricecooker.utils.caching import CacheForeverHeuristic, FileCache, CacheControlAdapter, InvalidatingCacheControlAdapter

DOWNLOAD_SESSION = requests.Session()                          # Session for downloading content from urls
DOWNLOAD_SESSION.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
DOWNLOAD_SESSION.mount('file://', FileAdapter())
cache = FileCache('.webcache')
forever_adapter= CacheControlAdapter(heuristic=CacheForeverHeuristic(), cache=cache)

DOWNLOAD_SESSION.mount('http://', forever_adapter)
DOWNLOAD_SESSION.mount('https://', forever_adapter)


def read(path, loadjs=False, session=None, driver=None):
    """ read: Reads from source and returns contents
        Args:
            path: (str) url or local path to download
            loadjs: (boolean) indicates whether to load js (optional)
            session: (requests.Session) session to use to download (optional)
            driver: (selenium.webdriver) webdriver to use to download (optional)
        Returns: str content from file or page
    """
    session = session or DOWNLOAD_SESSION
    try:
        if loadjs:                                              # Wait until js loads then return contents
            content = asyncio.get_event_loop().run_until_complete(load_page(path))
            return content
        else:                                                   # Read page contents from url
            response = DOWNLOAD_SESSION.get(path, stream=True)
            response.raise_for_status()
            return response.content
    except (requests.exceptions.MissingSchema, requests.exceptions.InvalidSchema):
        with open(path, 'rb') as fobj:                          # If path is a local file path, try to open the file
            return fobj.read()

async def load_page(path):
    browser = await launch({'headless': True})
    page = await browser.newPage()
    await page.goto(path)
    time.sleep(5)
    content = await page.evaluate('document.body.innerHTML', force_expr=True)
    await browser.close()
    return content
