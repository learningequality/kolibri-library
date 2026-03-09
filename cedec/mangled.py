r = {"Âº": "º",
 "Ã¡": "á",
 "Ã±": "ñ",
 "Ã³": "ó",
 "Ãº": "ú"}

def replace(s):
    for _in, out in r.items():
        s = s.replace(_in, out)
    return s
