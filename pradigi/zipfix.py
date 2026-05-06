import os
import shutil
import tempfile
import zipfile
import ntpath
import logging
from ricecooker.utils.zip import create_predictable_zip

logging.basicConfig(level=logging.INFO, filename="zipfix.log")

LIKELY_OFFENDING = "Utils.mobileDeviceFlag"
OFFENDING_CODE = "Utils.mobileDeviceFlag=true"
FIXED_CODE = "Utils.mobileDeviceFlag=false"

def apply_fix_better(filepath, dryrun=False):
    """
    Traverse files and replace offending code with fixed code, handling Unicode issues.

    Args:
        filepath (str): Path to the directory or file.
        dryrun (bool): If True, do not modify files.
    """
    for root, dirs, files in os.walk(filepath):
        for file in files:
            if file.endswith((".js", ".html")):
                file_path = os.path.join(root, file)
                content = None

                # Attempt to read the file with utf-8 encoding
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                # Handle UnicodeDecodeError by trying an alternate encoding
                except UnicodeDecodeError:
                    logging.warning("UTF-8 decoding failed for %s. Trying unicode_escape.", file_path)
                    try:
                        with open(file_path, "r", encoding="unicode_escape") as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        logging.error("Cannot decode %s with either UTF-8 or unicode_escape. Skipping.", file_path)
                        continue

                # If content was successfully read, perform the fix
                if content:
                    #logging.info("First chars of {}: {}".format(file_path, content[0:100]))

                    # Fix bytestring corruption: files that start with b' and end with '
                    if content.startswith("b'") and len(content) > 2:
                        logging.info("Fixing bytestring corruption in %s", file_path)
                        # Strip b' prefix
                        content = content[2:]
                        # Strip trailing ' if present
                        if content.endswith("'"):
                            content = content[:-1]
                        # Decode escape sequences like \r\n, \t, etc.
                        try:
                            content = content.encode('utf-8').decode('unicode_escape')
                        except UnicodeDecodeError:
                            logging.error("Failed to decode escape sequences in %s", file_path)

                    if FIXED_CODE in content:
                        logging.info("Previously fixed: %s", file_path)

                    if OFFENDING_CODE in content:
                        logging.info("Fixing mobile device flag in %s", file_path)
                        content = content.replace(OFFENDING_CODE, FIXED_CODE)

                    if not dryrun:
                        with open(file_path, "w", encoding="utf-8") as f:
                            logging.info("Writing back... {}".format(file_path))
                            f.write(content)
        # No need for manual recursion - os.walk already handles subdirectories

def fix_zips(path, dryrun=False):
    """
    Process a zip file, extract, fix offending code, and repackage.

    Args:
        path (str): Path to the zip file.
        dryrun (bool): If True, do not modify files.
    """
    zip_filename = ntpath.basename(path)
    extract_path = tempfile.mkdtemp()


    try:
        # Extract zip file contents
        with zipfile.ZipFile(path) as zf:
            zf.extractall(extract_path)
        logging.info("Extracted %s to %s", path, extract_path)

        # Apply fixes to the extracted files
        apply_fix_better(extract_path, dryrun)

    except zipfile.BadZipFile:
        logging.error("%s is not a valid zip file. Skipping.", zip_filename)

    finally:
        # Ensure cleanup of the temporary directory
        tmp_predictable_zip_path = create_predictable_zip(extract_path)
        shutil.copyfile(tmp_predictable_zip_path, path)
        shutil.rmtree(extract_path)
        os.remove(tmp_predictable_zip_path)
        logging.info("Cleaned up temporary directory %s", extract_path)

# Main loop to process all zip files in the target directory
for root, dirs, files in os.walk('./chefdata/zipfiles/'):
    for name in files:
        if name.endswith('.zip'):
            path = os.path.join(root, name)
            logging.info("Processing zip file: %s", path)
            fix_zips(path, dryrun=False)  # Set dryrun=True for testin
