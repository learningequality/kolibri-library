import sys

from profuturo.chef import ProFuturoChef


if __name__ == '__main__':
    """
    Run this script on the command line using:
        python chef.py -v --reset --token=YOURTOKENHERE
    """

    lang_id = "en"
    for lang in ['en', 'es', 'fr', 'pt']:
        if lang in sys.argv:
            lang_id = lang
            sys.argv.remove(lang)
            break

    chef = ProFuturoChef(lang_id)
    chef.main()
