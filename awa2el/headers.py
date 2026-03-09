le_rawheaders_detail = """
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
Accept-Encoding: gzip, deflate, br
Accept-Language: en-GB,en-US;q=0.9,en;q=0.8
Cache-Control: no-cache
Connection: keep-alive
Cookie: has_js=1; SSESSb5d96a45fb92cee9b9c59b85294fc5f6=Mk1k2BmgLd6jNmfyvrSQJnpP73FAATRqsAX9v3QPsXU; SESSb5d96a45fb92cee9b9c59b85294fc5f6=oMKsYHiW0cDQ0DTxwdqTNZCfheEVvqkMiUnPOMFbfnQ
DNT: 1
Host: www.nashmi.net
Pragma: no-cache
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/71.0.3578.98 Chrome/71.0.3578.98 Safari/537.36
""".strip()

headers = dict([[h.partition(': ')[0], h.partition(': ')[2]] for h in le_rawheaders_detail.split('\n')])

