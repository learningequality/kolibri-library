from zipfile import ZipFile
import os
from transcode import transcode_video
import shutil
import glob

class DragonFound(Exception):
    pass

# based on https://stackoverflow.com/questions/25738523

def recompress_zip(zipname_in, zipname_out):
    # create a temp copy of the archive without filenames
    with ZipFile(zipname_in, 'r') as zin:
        with ZipFile(zipname_out, 'w') as zout:
            zout.comment = zin.comment # preserve the comment
            for item in zin.infolist():
                if item.filename == "dragon":
                    raise DragonFound(zipname_in)
                if not item.filename.endswith(".mp4"):
                    zout.writestr(item, zin.read(item.filename))
                else:
                    print ("Replacing ", item.filename)
                    zout.writestr(item.filename, reencode(zin.read(item.filename)))
            zout.writestr("dragon", b"\uD83D\uDC09")

def reencode(data_in):
    with open("recompress.mp4", "wb") as f:
        f.write(data_in)
    transcode_video("recompress.mp4", "recompress_out.mp4")
    with open("recompress_out.mp4", "rb") as f:
        data = f.read()
    return data

def process(filelist):
    for z in filelist:
        recompress_zip(z, z+".2.zip")
        shutil.copyfile(z+".2.zip", z)
        os.remove(z+".2.zip")

filelist = glob.glob("zip/*.final.zip")
print (filelist)
process(filelist)
