import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

GITHUB_OWNER = "Mak404-droid"
GITHUB_REPO = "DesktopCompanion"

PROJECT_DIR = Path(__file__).resolve().parent

VERSION_FILE = PROJECT_DIR / "version.json"

BACKUP_DIR = PROJECT_DIR / "backups"

UPDATE_DIR = PROJECT_DIR / "update_temp"

HEALTH_FILE = PROJECT_DIR / ".companion_healthy"

UPDATE_LOCK = PROJECT_DIR / ".update_lock"

APP_FILE = PROJECT_DIR / "app.py"

GITHUB_API = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)


# ============================================================
# FILES THAT ARE ALLOWED TO BE UPDATED
# ============================================================

UPDATEABLE_FILES = {
    "app.py",
    "companion.py",
    "database.py",
    "web_search.py",
    "version.json",
}


# ============================================================
# PROTECTED FILES
# ============================================================

PROTECTED_FILES = {
    ".env",
    ".gitignore",
}


# ============================================================
# VERSION
# ============================================================

def get_current_version():

    try:

        with open(
            VERSION_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        return data.get(
            "version",
            "0.0.0"
        )

    except Exception:

        return "0.0.0"


def version_tuple(version):

    version = str(version).strip()

    if version.startswith("v"):

        version = version[1:]

    parts = version.split(".")

    result = []

    for part in parts[:3]:

        try:
            result.append(
                int(part)
            )

        except ValueError:

            result.append(0)

    while len(result) < 3:

        result.append(0)

    return tuple(result)


def is_newer(
    current,
    latest
):

    return (
        version_tuple(latest)
        >
        version_tuple(current)
    )


# ============================================================
# GITHUB API
# ============================================================

def github_headers():

    return {
        "Accept":
            "application/vnd.github+json",

        "User-Agent":
            "DesktopCompanion-Updater"
    }


def get_latest_release():

    response = requests.get(
        GITHUB_API,
        timeout=15,
        headers=github_headers()
    )

    if response.status_code == 404:

        return None

    response.raise_for_status()

    return response.json()


# ============================================================
# CHECK UPDATE
# ============================================================

def check_for_update():

    current = get_current_version()

    try:

        release = get_latest_release()

        if not release:

            return {
                "update": False,
                "current": current,
                "latest": None,
                "release": None,
                "message":
                    "No GitHub release exists yet."
            }

        tag = release.get(
            "tag_name"
        )

        if not tag:

            return {
                "update": False,
                "current": current,
                "latest": None,
                "release": release,
                "message":
                    "Release has no version tag."
            }

        latest = tag.lstrip("v")

        update_available = is_newer(
            current,
            latest
        )

        return {
            "update":
                update_available,

            "current":
                current,

            "latest":
                latest,

            "release":
                release,

            "message":
                (
                    f"Update available: "
                    f"{current} -> {latest}"
                    if update_available
                    else
                    f"You are up to date "
                    f"({current})."
                )
        }

    except Exception as e:

        return {
            "update": False,
            "current": current,
            "latest": None,
            "release": None,
            "message":
                f"Update check failed: {e}"
        }


# ============================================================
# FIND RELEASE ASSETS
# ============================================================

def find_update_assets(
    release,
    version
):

    assets = release.get(
        "assets",
        []
    )

    zip_asset = None
    checksum_asset = None

    expected_zip = (
        f"DesktopCompanion-v{version}.zip"
    )

    expected_checksum = (
        f"{expected_zip}.sha256"
    )

    for asset in assets:

        name = asset.get(
            "name",
            ""
        )

        if name == expected_zip:

            zip_asset = asset

        elif name == expected_checksum:

            checksum_asset = asset

    return (
        zip_asset,
        checksum_asset
    )


# ============================================================
# DOWNLOAD
# ============================================================

def download_file(
    url,
    destination
):

    response = requests.get(
        url,
        timeout=60,
        headers=github_headers(),
        stream=True
    )

    response.raise_for_status()

    with open(
        destination,
        "wb"
    ) as file:

        for chunk in response.iter_content(
            chunk_size=1024 * 1024
        ):

            if chunk:

                file.write(chunk)


# ============================================================
# SHA-256
# ============================================================

def calculate_sha256(path):

    sha = hashlib.sha256()

    with open(
        path,
        "rb"
    ) as file:

        for chunk in iter(
            lambda:
            file.read(1024 * 1024),
            b""
        ):

            sha.update(chunk)

    return sha.hexdigest()


def verify_sha256(
    file_path,
    checksum_path
):

    expected = (
        checksum_path
        .read_text(
            encoding="utf-8"
        )
        .strip()
        .split()[0]
        .lower()
    )

    actual = (
        calculate_sha256(
            file_path
        )
        .lower()
    )

    return (
        expected == actual
    )


# ============================================================
# BACKUP
# ============================================================

def create_backup():

    BACKUP_DIR.mkdir(
        exist_ok=True
    )

    timestamp = time.strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = (
        BACKUP_DIR /
        timestamp
    )

    backup.mkdir(
        parents=True,
        exist_ok=True
    )

    for filename in UPDATEABLE_FILES:

        source = (
            PROJECT_DIR /
            filename
        )

        if source.exists():

            shutil.copy2(
                source,
                backup / filename
            )

    return backup


# ============================================================
# RESTORE BACKUP
# ============================================================

def restore_backup(
    backup
):

    if not backup.exists():

        return

    for filename in UPDATEABLE_FILES:

        source = (
            backup /
            filename
        )

        destination = (
            PROJECT_DIR /
            filename
        )

        if source.exists():

            shutil.copy2(
                source,
                destination
            )


# ============================================================
# CLEAN TEMPORARY FILES
# ============================================================

def cleanup():

    try:

        if UPDATE_DIR.exists():

            shutil.rmtree(
                UPDATE_DIR,
                ignore_errors=True
            )

    except Exception:

        pass


# ============================================================
# EXTRACT UPDATE
# ============================================================

def extract_update(
    zip_path
):

    if UPDATE_DIR.exists():

        shutil.rmtree(
            UPDATE_DIR,
            ignore_errors=True
        )

    UPDATE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as archive:

        names = archive.namelist()

        for name in names:

            path = Path(name)

            # Prevent ZIP path traversal
            if (
                path.is_absolute()
                or ".." in path.parts
            ):

                raise RuntimeError(
                    "Unsafe path in update package."
                )

            filename = path.name

            if filename not in UPDATEABLE_FILES:

                continue

            destination = (
                UPDATE_DIR /
                filename
            )

            with archive.open(
                name
            ) as source:

                with open(
                    destination,
                    "wb"
                ) as target:

                    shutil.copyfileobj(
                        source,
                        target
                    )


# ============================================================
# VALIDATE UPDATE
# ============================================================

def validate_update():

    required = {
        "app.py",
        "database.py",
        "web_search.py",
        "version.json",
    }

    for filename in required:

        path = (
            UPDATE_DIR /
            filename
        )

        if not path.exists():

            raise RuntimeError(
                f"Update is missing: "
                f"{filename}"
            )

    with open(
        UPDATE_DIR /
        "version.json",
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if not data.get(
        "version"
    ):

        raise RuntimeError(
            "Update has an invalid version."
        )


# ============================================================
# INSTALL
# ============================================================

def install_update():

    for filename in UPDATEABLE_FILES:

        source = (
            UPDATE_DIR /
            filename
        )

        destination = (
            PROJECT_DIR /
            filename
        )

        if source.exists():

            shutil.copy2(
                source,
                destination
            )


# ============================================================
# HEALTH CHECK
# ============================================================

def start_companion():

    if HEALTH_FILE.exists():

        HEALTH_FILE.unlink()

    process = subprocess.Popen(
        [
            sys.executable,
            str(APP_FILE)
        ],
        cwd=str(PROJECT_DIR)
    )

    return process


def wait_for_health(
    process,
    timeout=15
):

    start = time.time()

    while (
        time.time() - start
        < timeout
    ):

        if HEALTH_FILE.exists():

            return True

        if (
            process.poll()
            is not None
        ):

            return False

        time.sleep(0.5)

    return False


# ============================================================
# UPDATE PROCESS
# ============================================================

def perform_update(
    release,
    latest_version
):

    if UPDATE_LOCK.exists():

        print(
            "Another update is already running."
        )

        return False

    UPDATE_LOCK.write_text(
        "update",
        encoding="utf-8"
    )

    backup = None
    process = None

    try:

        print(
            f"Preparing update "
            f"to {latest_version}..."
        )

        zip_asset, checksum_asset = (
            find_update_assets(
                release,
                latest_version
            )
        )

        if not zip_asset:

            raise RuntimeError(
                "Update ZIP was not found "
                "in the GitHub release."
            )

        if not checksum_asset:

            raise RuntimeError(
                "SHA-256 checksum file "
                "was not found."
            )

        UPDATE_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        zip_path = (
            UPDATE_DIR /
            f"DesktopCompanion-v"
            f"{latest_version}.zip"
        )

        checksum_path = (
            UPDATE_DIR /
            f"DesktopCompanion-v"
            f"{latest_version}.zip.sha256"
        )

        print(
            "Downloading update..."
        )

        download_file(
            zip_asset["browser_download_url"],
            zip_path
        )

        print(
            "Downloading checksum..."
        )

        download_file(
            checksum_asset[
                "browser_download_url"
            ],
            checksum_path
        )

        print(
            "Verifying SHA-256..."
        )

        if not verify_sha256(
            zip_path,
            checksum_path
        ):

            raise RuntimeError(
                "SHA-256 verification failed."
            )

        print(
            "SHA-256 verified."
        )

        print(
            "Checking update package..."
        )

        extract_update(
            zip_path
        )

        validate_update()

        print(
            "Update package is valid."
        )

        print(
            "Creating backup..."
        )

        backup = create_backup()

        print(
            "Installing update..."
        )

        install_update()

        print(
            "Starting updated companion..."
        )

        process = start_companion()

        print(
            "Running health check..."
        )

        if not wait_for_health(
            process
        ):

            raise RuntimeError(
                "Updated companion failed "
                "the health check."
            )

        print(
            "======================================"
        )

        print(
            "UPDATE SUCCESSFUL"
        )

        print(
            f"Version: {latest_version}"
        )

        print(
            "======================================"
        )

        cleanup()

        try:

            UPDATE_LOCK.unlink()

        except Exception:

            pass

        return True

    except Exception as e:

        print(
            "======================================"
        )

        print(
            "UPDATE FAILED"
        )

        print(
            str(e)
        )

        print(
            "Restoring previous version..."
        )

        if process:

            try:

                process.terminate()

            except Exception:

                pass

        if backup:

            restore_backup(
                backup
            )

            print(
                "Rollback completed."
            )

        cleanup()

        try:

            UPDATE_LOCK.unlink()

        except Exception:

            pass

        return False


# ============================================================
# AUTOMATIC CHECK
# ============================================================

def auto_update():

    result = check_for_update()

    if not result.get(
        "update"
    ):

        return False

    print(
        result["message"]
    )

    return perform_update(
        result["release"],
        result["latest"]
    )


# ============================================================
# COMMAND LINE
# ============================================================

if __name__ == "__main__":

    print(
        "======================================"
    )

    print(
        "Desktop Companion Auto Updater"
    )

    print(
        "======================================"
    )

    result = check_for_update()

    print(
        f"Current version: "
        f"{result['current']}"
    )

    if result.get(
        "latest"
    ):

        print(
            f"Latest version: "
            f"{result['latest']}"
        )

    print(
        result["message"]
    )

    if result.get(
        "update"
    ):

        answer = input(
            "\nInstall this update now? "
            "[y/N]: "
        ).strip().lower()

        if answer == "y":

            success = perform_update(
                result["release"],
                result["latest"]
            )

            if success:

                print(
                    "Update finished."
                )

            else:

                print(
                    "Update was rolled back."
                )

        else:

            print(
                "Update cancelled."
            )