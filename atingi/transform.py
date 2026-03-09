import io
import os
import pickle
import shutil
import zipfile

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource
from googleapiclient.http import MediaIoBaseDownload
from PIL import Image
from ricecooker.config import LOGGER

# Creds storage
CLIENT_SECRET_FILE = "credentials/credentials.json"
CLIENT_TOKEN_PICKLE = "credentials/token.pickle"


SCORM_FILES_DRIVE_ID = "1FyXSZXLbXReX-YKjFyIHc8Br_WkzzsnJ"


SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


CSS_ADDITION = """
/*  Added for kolibri usage */
.lesson--open {
    padding-left: 0px !important;
}

.previous-lesson, .page__menu, .lesson-nav--next, .lesson-nav--previous  {
    display: none  !important;
}

[data-block-id="ckmkf68hm004f2669qq58b8c4"] {
    display: none;
}

nav[aria-label="Navigation menu"] {
  display: none;
}

.page-wrap {
    margin-left: 0px !important;
}
button.continue-btn.brand--background:not([data-ba]) {
     display: none  !important;
}

/*  Added for kolibri usage */
"""

JS_ADDITION = """
/*  Added for kolibri usage */
    document.addEventListener('DOMContentLoaded', function() {
        window.location.hash = '#/lessons/TO_REPLACE_BY_LESSON_ID';
    });


    document.addEventListener('animationend', function(event) {
      if (event.animationName === 'fadeIn') {
        var allInnerElements = event.target.getElementsByTagName('*');

        for (var i = 0; i < allInnerElements.length; i++) {
              var element = allInnerElements[i];

          if (element.textContent.trim().includes("Go to Chapter") ||
              element.textContent.trim().includes("Continue with") )  {
            element.closest('div.noOutline').style.display = 'none';
            break;
          }
        }
      }
    });


/*  Added for kolibri usage */

"""


def get_credentials() -> Credentials:
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth 2.0 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """

    creds = None
    if os.path.exists(CLIENT_TOKEN_PICKLE):
        with open(CLIENT_TOKEN_PICKLE, "rb") as token:
            creds = pickle.load(token)
    else:
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRET_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(CLIENT_TOKEN_PICKLE, "wb") as token:
                pickle.dump(creds, token)
    return creds


def download_file(service: Resource, file_id: str, file_name: str) -> None:
    """Downloads a file from the Drive.

    Args:
        service: The drive service object.
        file_id: The ID of the file to download.
        file_name: The name of the file to download.

    Raises:
        Errors: An error if the file is not found or cannot be downloaded.
    """
    if os.path.exists(file_name):
        print(f"File already exists: {file_name}")
        return

    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(file_name, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"Downloading: {int(status.progress() * 100)}%")
    except Exception as e:
        print(f"Error downloading file {file_name}: {e}")


def download_files(
    gdrive_folder_id: str, mimeType: str, output_folder: str
) -> None:  # noqa: E501
    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)
    # List files in the folder
    results = (
        service.files()
        .list(q=f"'{gdrive_folder_id}' in parents", pageSize=1000)
        .execute()
    )
    items = results.get("files", [])

    for item in items:
        # Skip folders
        if item["mimeType"] == "application/vnd.google-apps.folder":
            continue
        if item["mimeType"] == mimeType:
            download_file(
                service, item["id"], f"{output_folder}{item['name']}"
            )  # noqa: E501


def download_gdrive_files() -> None:

    download_files(SCORM_FILES_DRIVE_ID, "application/zip", "chefdata/")


def unzip_scorm_files() -> None:
    for f in os.listdir("chefdata"):
        file_path = os.path.join("chefdata", f)
        course_path = os.path.splitext(file_path)[0]
        course_dirname = os.path.basename(course_path)
        if os.path.isfile(file_path) and f.endswith(".zip"):
            if os.path.exists(file_path) and not os.path.exists(course_path):
                LOGGER.info(f"Unzipping files for lesson: {course_dirname}")
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(course_path)
            else:
                LOGGER.info(f"{course_dirname} already unzipped")


def resize_images(directory: str, max_height: int = 640) -> None:
    for filename in os.listdir(directory):
        if filename.endswith(".png") or filename.endswith(".jpg"):
            filepath = os.path.join(directory, filename)
            with Image.open(filepath) as im:
                width, height = im.size
                if height > max_height:
                    new_width = int((max_height / height) * width)
                    resized = im.resize((new_width, max_height), Image.LANCZOS)
                    resized.save(filepath, format=resized.format)


def prepare_lesson_html5_directory(lesson_data: dict, lesson_dir: str) -> None:
    shutil.copytree(
        os.path.join(
            "chefdata/LearningEquality_atingi_Modules",
            lesson_data["file"],
            "scormcontent",
        ),
        lesson_dir,
        dirs_exist_ok=True,
    )

    assets_dir = os.path.join(lesson_dir, "assets")
    for asset in lesson_data["remove_assets"]:
        asset_path = os.path.join(assets_dir, asset)
        if os.path.exists(asset_path):
            if os.path.isfile(asset_path):
                os.remove(asset_path)
            else:
                shutil.rmtree(asset_path)

    # reduce size of image files
    resize_images(assets_dir)

    index = os.path.join(lesson_dir, "index.html")
    with open(index, "r") as f:
        html_content = f.read()

    page = BeautifulSoup(html_content, "html.parser")
    head = page.find("head")
    if head is None:
        head = page.new_tag("head")
        page.insert(0, head)

    # css to hide menu elements for the course
    existing_style = page.find("style", string=CSS_ADDITION)
    if not existing_style:
        new_style = page.new_tag("style")
        new_style.string = CSS_ADDITION
        head.append(new_style)

    # js to redirect to the lesson route
    new_js_code = JS_ADDITION.replace(
        "TO_REPLACE_BY_LESSON_ID", lesson_data["route"]
    )  # noqa: E501
    existing_script = page.find("script", string=new_js_code)
    if not existing_script:
        new_script = page.new_tag("script")
        new_script.string = new_js_code
        new_script["type"] = "text/javascript"
        head.append(new_script)

    # Write modified content to file
    with open(index, "w") as f:
        f.write(str(page))


def copy_digital_enquirer_kit_files(
    lesson_data: dict, lesson_dir: str
) -> None:  # noqa: E501
    file_path = os.path.join(
        "chefdata/LearningEquality_atingi_Modules", lesson_data["file"]
    )
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        zip_ref.extractall(lesson_dir)
    shutil.move(
        os.path.join(lesson_dir, "story.html"),
        os.path.join(lesson_dir, "index.html"),  # noqa: E501
    )
