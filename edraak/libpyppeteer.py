import asyncio
import json
import os
from pyppeteer import launch
from tempfile import NamedTemporaryFile

from ricecooker.utils.downloader import read


def visit_page(url, loadjs=False, networktab=False):
    """
    Makes chromium visit the page at `url` and return the page content.
    If `networktab==True` the result will also contain the info from the network tab
    that resulted from the GET request, which can be used to find dependent resources.
    """
    if not loadjs:
        return {'content': read(url)}
    
    result = {}  # dictionay {'content': str(<HTML>), 'resources':{networktabdict} }
    
    if networktab:
        networktab_file = NamedTemporaryFile(suffix='.json', delete=False)
        networktab_file.close()
        # print('using {} as networktab_file'.format(networktab_file.name))


    async def main():
        """
        This is the asyncio coroutine that will do the actual work.
        It is called with via `run_until_complete` below.
        """
        browser = await launch(headless=True)
        page = await browser.newPage()

        if networktab:
            await page.tracing.start(screenshots=True, path=networktab_file.name)

        await page.goto(url, waitUntil='networkidle0')  # timeout=3000??  networkIdleTimeout: 5000, ?
        # docs https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.page.Page.goto
        content = await page.content() # evaluate('''() => document.innerHTML''')

        if networktab:
            trace = await page.tracing.stop()

        await browser.close()
        return content

    # Run the async code...
    result['url'] = url  # TODO: redirects???
    result['content'] = asyncio.get_event_loop().run_until_complete(main())

    if networktab:
        with open(networktab_file.name,'r') as jsonf:
            result['networktab'] = json.load(jsonf)    
            os.remove(networktab_file.name)

    return result




def get_resource_requests_from_networktab(networktab):
    """
    Parse `networktab` to extract only `ResourceSendRequest` information.
    """
    events = networktab['traceEvents']
    network_events = []
    for event in events:
        if event['name'] == 'ResourceSendRequest':
            network_events.append(event)
    resource_requests = []
    for ne in network_events:
        ne_data = ne['args']['data']
        ne_dict = dict(
            method=ne_data['requestMethod'],
            url=ne_data['url']
        )
        resource_requests.append(ne_dict)
    return resource_requests
