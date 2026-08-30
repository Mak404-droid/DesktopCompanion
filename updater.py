import hashlib
import json
import shutil
import subprocess
import sys
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
# ONLY THESE FILES CAN BE UPDATED
# ============================================================

UPDATEABLE_FILES = {
    "app.py",
    "companion.py",
    "database.py",
    "web_search.py",
    "version.json",
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

        return str(
            data.get("version", "0.0.0")
        )

    except Exception:

        return "0.0.0"


def version_tuple(version):

    version = str(version).strip()

    if version.startswith("v"):

        version = version[1:]

    parts = version.split(".")

    numbers = []

    for part in parts[:3]:

        try:

            numbers.append(
                int(part)
            )

        except ValueError:

            numbers.append(0)

    while len(numbers) < 3:

        numbers.append(0)

    return tuple(numbers)


def is_newer(current, latest):

    return (
        version_tuple(latest)
        >
        version_tuple(current)
    )


# ============================================================
# GITHUB
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
# UPDATE CHECK
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
                    "GitHub release has no tag."
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

    except Exception as error:

        return {
            "update": False,
            "current": current,
            "latest": None,
            "release": None,
            "message":
                f"Update check failed: {error}"
        }


# ============================================================
# FIND RELEASE FILES
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

    return expected == actual


# ============================================================
# BACKUP
# ============================================================

def create_backup():

    BACKUP_DIR.mkdir(
        parents=True,
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
# RESTORE
# ============================================================

def restore_backup(backup):

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
# CLEANUP
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

def extract_update(zip_path):

    # IMPORTANT:
    # The ZIP stays directly inside UPDATE_DIR.
    # Extracted files go into UPDATE_DIR/files.
    # This prevents the ZIP from being deleted
    # before extraction.

    extract_dir = (
        UPDATE_DIR /
        "files"
    )

    if extract_dir.exists():

        shutil.rmtree(
            extract_dir,
            ignore_errors=True
        )

    extract_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as archive:

        for name in archive.namelist():

            path = Path(name)

            # ZIP path traversal protection
            if (
                path.is_absolute()
                or ".." in path.parts
            ):

                raise RuntimeError(
                    "Unsafe path in update package."
                )

            filename = path.name

            # Only extract approved files
            if filename not in UPDATEABLE_FILES:

                continue

            destination = (
                extract_dir /
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

    extract_dir = (
        UPDATE_DIR /
        "files"
    )

    required = {
        "app.py",
        "database.py",
        "web_search.py",
        "version.json",
    }

    for filename in required:

        path = (
            extract_dir /
            filename
        )

        if not path.exists():

            raise RuntimeError(
                f"Update is missing: {filename}"
            )

    with open(
        extract_dir /
        "version.json",
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    new_version = data.get(
        "version"
    )

    if not new_version:

        raise RuntimeError(
            "Update has an invalid version."
        )


# ============================================================
# INSTALL
# ============================================================

def install_update():

    extract_dir = (
        UPDATE_DIR /
        "files"
    )

    for filename in UPDATEABLE_FILES:

        source = (
            extract_dir /
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

        try:

            HEALTH_FILE.unlink()

        except Exception:

            pass

    return subprocess.Popen(
        [
            sys.executable,
            str(APP_FILE)
        ],
        cwd=str(PROJECT_DIR)
    )


def wait_for_health(
    process,
    timeout=20
):

    start_time = time.time()

    while (
        time.time() - start_time
        < timeout
    ):

        if HEALTH_FILE.exists():

            return True

        if process.poll() is not None:

            return False

        time.sleep(0.5)

    return False


# ============================================================
# PERFORM UPDATE
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
            f"Preparing update to "
            f"{latest_version}..."
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

        # Start clean temporary directory
        if UPDATE_DIR.exists():

            shutil.rmtree(
                UPDATE_DIR,
                ignore_errors=True
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

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        print(
            "Downloading update..."
        )

        download_file(
            zip_asset[
                "browser_download_url"
            ],
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

        # ----------------------------------------------------
        # VERIFY
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # EXTRACT
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # BACKUP
        # ----------------------------------------------------

        print(
            "Creating backup..."
        )

        backup = create_backup()

        # ----------------------------------------------------
        # INSTALL
        # ----------------------------------------------------

        print(
            "Installing update..."
        )

        install_update()

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        print(
            "Starting updated companion..."
        )

        process = start_companion()

        # ----------------------------------------------------
        # HEALTH CHECK
        # ----------------------------------------------------

        print(
            "Running health check..."
        )

        healthy = wait_for_health(
            process
        )

        if not healthy:

            raise RuntimeError(
                "Updated companion failed "
                "the health check."
            )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

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

    except Exception as error:

        print(
            "======================================"
        )

        print(
            "UPDATE FAILED"
        )

        print(
            str(error)
        )

        # Stop failed version
        if process:

            try:

                process.terminate()

                process.wait(
                    timeout=5
                )

            except Exception:

                pass

        # ----------------------------------------------------
        # ROLLBACK
        # ----------------------------------------------------

        if backup:

            print(
                "Restoring previous version..."
            )

            restore_backup(
                backup
            )

            print(
                "Rollback completed."
            )

            # Restart old version
            try:

                start_companion()

            except Exception:

                pass

        else:

            print(
                "No backup was created."
            )

        cleanup()

        try:

            UPDATE_LOCK.unlink()

        except Exception:

            pass

        return False


# ============================================================
# MAIN
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

    if result.get("latest"):

        print(
            f"Latest version: "
            f"{result['latest']}"
        )

    print(
        result["message"]
    )

    if result.get("update"):

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