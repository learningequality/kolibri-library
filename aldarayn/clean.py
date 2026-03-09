def clean(text):
    cleaner = lxml.html.clean.Cleaner(
        scripts=True, # Removes any <script> tags.
        javascript=True, # Removes any Javascript, like an onclick attribute. Also removes stylesheets.
        comments=True, # Removes any comments.
        style=True, # Removes any style tags.
        inline_style=True, # Removes any style attributes. Defaults to the value of the style option.
        links=True, # Removes any <link> tags
        meta=True, # Removes any <meta> tags
        page_structure=True, # Structural parts of a page: <head>, <html>, <title>.
        processing_instructions=True, # Removes any processing instructions.
        embedded=False, # Removes any embedded objects (flash, iframes)
        frames=False, # Removes any frame-related tags
        forms=True, # Removes any form tags
        annoying_tags=True, # Tags that aren't wrong, but are annoying. <blink> and <marquee>
        #remove_tags=[], # A list of tags to remove. Only the tags will be removed, their content will get pulled up into the parent tag.
        #kill_tags=[], # A list of tags to kill. Killing also removes the tag's content, i.e. the whole subtree, not just the tag itself.
        # allow_tags: [], # A list of tags to include (default include all).
        remove_unknown_tags=True, # Remove any tags that aren't standard parts of HTML.
        safe_attrs_only=True, # If true, only include 'safe' attributes (specifically the list from the feedparser HTML sanitisation web site).
        #safe_attrs=[], # A set of attribute names to override the default list of attributes considered 'safe' (when safe_attrs_only=True).
        add_nofollow=False, # If true, then any <a> tags will have rel="nofollow" added to them.
        #host_whitelist=[], # A list or set of hosts that you can use for embedded content (for content like <object>, <link rel="stylesheet">, etc). You can also implement/override the method allow_embedded_url(el, url) or allow_element(el) to implement more complex rules for what can be embedded. Anything that passes this test will be shown, regardless of the value of (for instance) embedded. Note that this parameter might not work as intended if you do not make the links absolute before doing the cleaning. Note that you may also need to set whitelist_tags.
        # whitelist_tags=[], # A set of tags that can be included with host_whitelist. The default is iframe and embed; you may wish to include other tags like script, or you may want to implement allow_embedded_url for more control. Set to None to include all tags.
    )
    return cleaner.clean_html(text)

