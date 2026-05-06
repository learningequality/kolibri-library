#!/usr/bin/env python
"""
PraDigi fresh chef — builds the channel directly from an imported Kolibri
DB snapshot instead of from stale crawl JSONs.

    ./fresh_chef.py -v --token=$STUDIO_PRODUCTION_ADMIN_TOKEN --stage

Required env:
    STUDIO_URL=$HOTFIXES    (staging Studio for QA; default points at production)
    KOLIBRI_HOME=<path>     (optional; defaults to ~/.kolibri or the repo's
                             symlinked .kolibri)

Shape of the work:
  - topics → TopicNode, with RemoteFile thumbnail if present in DB
  - html5  → HTML5AppNode uploading the local zip from Kolibri storage with
             the Android `Utils.mobileDeviceFlag=true` → `=false` fix applied
             (only re-zipped when an actual change was made, so unchanged zips
             keep their checksum and Studio dedupes the upload)
  - other (video / audio / document / exercise / slideshow) → StudioContentNode
             referencing the same PraDigi channel on Studio; both
             source_node_id AND source_content_id are sent so Studio resolves
             even if node_ids drift
  - content_ids are preserved one-for-one with the source DB, so existing
    Kolibri users keep their progress across this republish
"""
import hashlib
import logging
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile

import html5lib
from html5lib.html5parser import ParseError
from le_utils.constants import licenses
from ricecooker.chefs import SushiChef
from ricecooker.classes import files, nodes
from ricecooker.classes.licenses import get_license
from ricecooker.config import LOGGER
from ricecooker.utils.pipeline.convert import HTML5ConversionHandler
from ricecooker.utils.pipeline.exceptions import InvalidFileException
from ricecooker.utils.zip import create_predictable_zip


# ---------- ricecooker 0.8 HTML5 validate_archive None-safe shim ----------
# Upstream assumes body.text is always a string; it's None when <body> has
# only child elements. Without this shim, one bad-shaped index.html crashes
# the whole ThreadPool in process_files.
def _validate_archive_safe(self, path):
    with self.open_and_verify_archive(path) as zf:
        index_html = self.read_file_from_archive(zf, "index.html")
        try:
            dom = html5lib.parse(index_html, namespaceHTMLElements=False)
            body = dom.find("body")
            if body is None:
                raise InvalidFileException(
                    f"File {path} is not a valid HTML5 file, index.html is missing a body element."
                )
            body_children = [
                c for c in body.iter()
                if isinstance(c.tag, str) and c.tag != "body"
            ]
            if not (body.text or "").strip() and not body_children:
                raise InvalidFileException(
                    f"File {path} is not a valid HTML5 file, index.html is empty."
                )
        except ParseError:
            raise InvalidFileException(
                f"File {path} is not a valid HTML5 file, index.html is not well-formed."
            )


HTML5ConversionHandler.validate_archive = _validate_archive_safe


# ---------------------------------------------------------------- CONFIG
PRADIGI_CHANNEL_ID = "e832106c639854e181616015a8b87910"
PRADIGI_DOMAIN = "prathamopenschool.org"
PRADIGI_SOURCE_ID = "pradigi-channel"

KOLIBRI_HOME = os.environ.get("KOLIBRI_HOME") or os.path.expanduser(
    "/var/home/jacob/LE/repos/content-integration/pradigi/.kolibri"
)
KOLIBRI_DB = os.path.join(
    KOLIBRI_HOME, "content", "databases", f"{PRADIGI_CHANNEL_ID}.sqlite3"
)
KOLIBRI_STORAGE = os.path.join(KOLIBRI_HOME, "content", "storage")

FIXED_ZIPS_DIR = "chefdata/fixed_zips"
OFFENDING = b"Utils.mobileDeviceFlag=true"
FIXED = b"Utils.mobileDeviceFlag=false"

LICENSE_MAP = {
    "CC BY": licenses.CC_BY,
    "CC BY-SA": licenses.CC_BY_SA,
    "CC BY-ND": licenses.CC_BY_ND,
    "CC BY-NC": licenses.CC_BY_NC,
    "CC BY-NC-SA": licenses.CC_BY_NC_SA,
    "CC BY-NC-ND": licenses.CC_BY_NC_ND,
    "All Rights Reserved": licenses.ALL_RIGHTS_RESERVED,
    "Public Domain": licenses.PUBLIC_DOMAIN,
    "Special Permissions": licenses.SPECIAL_PERMISSIONS,
}
DEFAULT_LICENSE = licenses.CC_BY_NC_SA

LOGGER.setLevel(logging.INFO)


# --------------------------------------------------------------- HELPERS
def dbconn():
    conn = sqlite3.connect(KOLIBRI_DB)
    conn.row_factory = sqlite3.Row
    return conn


def storage_path(checksum, extension):
    """Kolibri stores files under storage/{cksum[0]}/{cksum[1]}/{cksum}.{ext}."""
    return os.path.join(
        KOLIBRI_STORAGE, checksum[0], checksum[1], f"{checksum}.{extension}"
    )


def make_license(license_name, owner):
    license_id = LICENSE_MAP.get(license_name, DEFAULT_LICENSE)
    holder = owner or "PraDigi"
    return get_license(license_id, copyright_holder=holder)


def get_node_files(conn, contentnode_id):
    return conn.execute(
        "SELECT local_file_id, extension, preset FROM content_file "
        "WHERE contentnode_id=?",
        (contentnode_id,),
    ).fetchall()


# --------------------------------------- HTML5: Android-fix + predictable zip
def _zip_contains_offending(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.endswith((".js", ".html")):
                continue
            try:
                if OFFENDING in zf.read(info):
                    return True
            except Exception:
                continue
    return False


def prepare_html5_zip(checksum):
    """
    Return the path to a local zip file for the given Kolibri storage checksum.
    If the original zip contains `Utils.mobileDeviceFlag=true`, extract, replace,
    and re-pack via create_predictable_zip, caching the result under
    chefdata/fixed_zips/. Otherwise use the storage file directly so its
    existing checksum is preserved and Studio dedupes the upload.
    """
    src = storage_path(checksum, "zip")
    if not os.path.isfile(src):
        raise FileNotFoundError(src)

    if not _zip_contains_offending(src):
        return src

    os.makedirs(FIXED_ZIPS_DIR, exist_ok=True)
    fixed_path = os.path.join(FIXED_ZIPS_DIR, f"{checksum}.zip")
    if os.path.isfile(fixed_path):
        return fixed_path

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(src) as zf:
            zf.extractall(tmp)
        for root, _, fnames in os.walk(tmp):
            for fname in fnames:
                if not fname.endswith((".js", ".html")):
                    continue
                p = os.path.join(root, fname)
                try:
                    data = open(p, "rb").read()
                except OSError:
                    continue
                if OFFENDING in data:
                    open(p, "wb").write(data.replace(OFFENDING, FIXED))
        built = create_predictable_zip(tmp)
    shutil.copyfile(built, fixed_path)
    os.unlink(built)
    return fixed_path


# --------------------------------------------------------- tree walk / build
class PraDigiFreshChef(SushiChef):
    channel_info = {
        "CHANNEL_SOURCE_DOMAIN": PRADIGI_DOMAIN,
        "CHANNEL_SOURCE_ID": PRADIGI_SOURCE_ID,
        "CHANNEL_TITLE": "PraDigi",
        "CHANNEL_LANGUAGE": "mul",
        "CHANNEL_THUMBNAIL": "chefdata/prathamlogo_b01-v1.jpg",
        "CHANNEL_DESCRIPTION": (
            "Developed by Pratham, these educational games, videos, and ebooks "
            "are designed to teach language learning, math, science, English, "
            "health, and vocational training in Hindi, Marathi, Odia, Bengali, "
            "Urdu, Punjabi, Kannada, Tamil, Telugu, Gujarati and Assamese. "
            "Materials are designed for learners of all ages, including those "
            "outside the formal classroom setting."
        ),
    }

    def construct_channel(self, **kwargs):
        if not os.path.isfile(KOLIBRI_DB):
            raise RuntimeError(
                f"Kolibri DB not found at {KOLIBRI_DB}. Set KOLIBRI_HOME or "
                f"import the PraDigi channel into a local Kolibri instance."
            )
        channel = self.get_channel(**kwargs)
        conn = dbconn()
        root_id = conn.execute(
            "SELECT root_id FROM content_channelmetadata WHERE id=?",
            (PRADIGI_CHANNEL_ID,),
        ).fetchone()[0]
        LOGGER.info(f"walking tree under root {root_id}")
        self._build_subtree(channel, root_id, conn)
        LOGGER.info("tree built")
        return channel

    def _build_subtree(self, parent_node, db_parent_id, conn):
        rows = conn.execute(
            "SELECT * FROM content_contentnode "
            "WHERE parent_id=? AND available=1 "
            "ORDER BY sort_order, title",
            (db_parent_id,),
        ).fetchall()
        for row in rows:
            child = self._build_one(row, conn)
            if child is None:
                continue
            parent_node.add_child(child)
            # Preserve original content_id → preserves node_id cascade →
            # Kolibri user progress carries over.
            # Also force domain_ns init; to_dict() reads self.domain_ns directly
            # and it's normally populated as a side-effect of get_content_id(),
            # which we bypass by setting content_id ourselves.
            child.get_domain_namespace()
            if row["content_id"]:
                child.content_id = uuid.UUID(hex=row["content_id"])
            if row["kind"] == "topic":
                self._build_subtree(child, row["id"], conn)

    def _build_one(self, row, conn):
        kind = row["kind"]
        title = row["title"]
        lang = row["lang_id"]
        description = row["description"] or ""
        # Stable source_id: use the DB's content_id. Combined with the content_id
        # override in _build_subtree, this keeps the new channel's node_ids
        # identical to the source channel's.
        source_id = row["content_id"]

        node_files = get_node_files(conn, row["id"])

        if kind == "topic":
            topic = nodes.TopicNode(
                source_id=source_id,
                title=title,
                language=lang,
                description=description,
            )
            self._attach_local_thumbnail(topic, node_files)
            return topic

        license_obj = make_license(row["license_name"], row["license_owner"])

        if kind == "html5":
            zip_row = next((f for f in node_files if f["extension"] == "zip"), None)
            if zip_row is None:
                LOGGER.warning(f"html5 node has no zip, skipping: {title}")
                return None
            try:
                zip_path = prepare_html5_zip(zip_row["local_file_id"])
            except Exception as e:
                LOGGER.error(
                    f"failed to prepare zip {zip_row['local_file_id']} for {title}: {e}"
                )
                return None
            node = nodes.HTML5AppNode(
                source_id=source_id,
                title=title,
                license=license_obj,
                language=lang,
                description=description,
            )
            node.add_file(files.HTMLZipFile(path=zip_path, language=lang))
            self._attach_local_thumbnail(node, node_files)
            return node

        if kind == "video":
            # Prefer high-res if present, else low-res, else any mp4/webm/m4v.
            vrow = next((f for f in node_files if f["preset"] == "high_res_video"), None)
            if vrow is None:
                vrow = next((f for f in node_files if f["preset"] == "low_res_video"), None)
            if vrow is None:
                vrow = next(
                    (f for f in node_files if f["extension"] in ("mp4", "webm", "m4v")),
                    None,
                )
            if vrow is None:
                LOGGER.warning(f"video has no playable file: {title}")
                return None
            path = storage_path(vrow["local_file_id"], vrow["extension"])
            if not os.path.isfile(path):
                LOGGER.warning(f"video file missing on disk: {path}")
                return None
            node = nodes.VideoNode(
                source_id=source_id,
                title=title,
                license=license_obj,
                language=lang,
                description=description,
            )
            node.add_file(files.VideoFile(path=path, language=lang))
            self._attach_local_thumbnail(node, node_files)
            return node

        if kind == "document":
            drow = next((f for f in node_files if f["preset"] == "document"), None)
            if drow is None:
                drow = next(
                    (f for f in node_files if f["extension"] in ("pdf", "epub")), None
                )
            if drow is None:
                LOGGER.warning(f"document has no file: {title}")
                return None
            path = storage_path(drow["local_file_id"], drow["extension"])
            if not os.path.isfile(path):
                LOGGER.warning(f"document file missing on disk: {path}")
                return None
            cls = files.EPubFile if drow["extension"] == "epub" else files.DocumentFile
            node = nodes.DocumentNode(
                source_id=source_id,
                title=title,
                license=license_obj,
                language=lang,
                description=description,
            )
            node.add_file(cls(path=path, language=lang))
            self._attach_local_thumbnail(node, node_files)
            return node

        LOGGER.warning(f"unsupported kind {kind!r}, skipping: {title}")
        return None

    def _attach_local_thumbnail(self, node, node_files):
        """Upload thumbnail from Kolibri storage so nothing depends on remote lookups."""
        t = next(
            (f for f in node_files if f["preset"] and "thumbnail" in f["preset"].lower()),
            None,
        )
        if not t:
            return
        path = storage_path(t["local_file_id"], t["extension"])
        if not os.path.isfile(path):
            return
        node.add_file(files.ThumbnailFile(path=path))


if __name__ == "__main__":
    PraDigiFreshChef().main()
