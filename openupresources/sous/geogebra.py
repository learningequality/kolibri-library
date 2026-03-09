import requests
import base64
import zipfile
import io
import re
import shutil

# html = standalone html

html_template = """<html>
<head>
    <meta name=viewport content="width=device-width,initial-scale=1">
</head>
<body>
    <script src="GeoGebra/deployggb.js"></script>
    <div id="ggb-element"></div> 
<script>  
    var ggbApp = new GGBApplet({%s, "width": 800, "height": 600, "showToolBar": false, "showAlgebraInput": false, "showMenuBar": false, "allowStyleBar": false, "enableShiftDragZoom": false }, true);
    window.addEventListener("load", function() { 
        ggbApp.setHTML5Codebase('GeoGebra/HTML5/5.0/web3d/');
        ggbApp.inject('ggb-element');
    });
</script>
</body>
</html>"""

def fill_html_template(b64):
    return html_template % '"ggbBase64": "{}"'.format(b64)

def get_html_from_id(identifier):
    return fill_html_template(get_b64_from_id(identifier).decode('utf-8'))

def get_xml_from_id(identifier):
    ggb_base64 = get_b64_from_id(identifier)
    zip_bytes = base64.decodestring(ggb_base64)
    zip_io = io.BytesIO(zip_bytes)
    zip_object = zipfile.ZipFile(zip_io)
    geogebra = zip_object.open("geogebra.xml")
    geogebra_xml = geogebra.read()
    return geogebra_xml

def get_b64_from_id(identifier):
    data = '{"request":{"-api":"1.0.0","login":{"-type":"cookie","-getuserinfo":"false"},"task":{"-type":"fetch","fields":{"field":[{"-name":"id"},{"-name":"geogebra_format"},{"-name":"width"},{"-name":"height"},{"-name":"toolbar"},{"-name":"menubar"},{"-name":"inputbar"},{"-name":"reseticon"},{"-name":"labeldrags"},{"-name":"shiftdragzoom"},{"-name":"rightclick"},{"-name":"ggbbase64"},{"-name":"preview_url"}]},"filters":{"field":[{"-name":"id","#text":"'+identifier+'"}]},"order":{"-by":"id","-type":"asc"},"limit":{"-num":"1"}}}}'
    r = requests.post(url="https://www.geogebra.org/api/json.php", data=data)
    return r.json()['responses']['response'][1]['item']['ggbBase64'].encode('utf-8')

def replace_ggb(base64_zip, new_zip_file):
    # for now, just doing one.
    shutil.copy("/home/dragon/chef/openup/sushi-chef-openupresources/sous/cache_dir/geo.zip", new_zip_file)
    zip_object = zipfile.ZipFile(new_zip_file, "a")
    html = zip_object.open("mNkCD4V9s-7122-Corresponding-Parts.html").read().decode('utf-8')
    pattern = '"ggbBase64":"([^"]+)"'
    new_html = re.sub(pattern, '"ggbBase64":"{}"'.format(base64_zip), html)
    zip_object.writestr("index.html", new_html)
    zip_object.close()
    return new_zip_file
    
def new_zip(identifier):
    b64 = get_b64_from_id(identifier)
    print (replace_ggb(b64, "new_geo.zip"))
    
if __name__  == "__main__": 
    html = get_html_from_id("beVbuPFP")
    with open("bundle/b64.html", "w") as f:
        f.write(html)