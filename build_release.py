import hashlib
import json
import shutil
import zipfile

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent

OUTPUT_DIR = PROJECT_DIR / "release"

FILES_TO_INCLUDE = [
    "app.py",
    "companion.py",
    "database.py",
    "web_search.py",
    "version.json",
]


def get_version():

    with open(
        PROJECT_DIR / "version.json",
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)["version"]


def sha256_file(path):

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


def main():

    version = get_version()

    if OUTPUT_DIR.exists():

        shutil.rmtree(
            OUTPUT_DIR
        )

    OUTPUT_DIR.mkdir(
        parents=True
    )

    zip_name = (
        f"DesktopCompanion-v{version}.zip"
    )

    zip_path = (
        OUTPUT_DIR /
        zip_name
    )

    print(
        "======================================"
    )

    print(
        "Desktop Companion Release Builder"
    )

    print(
        "======================================"
    )

    print(
        f"Building version {version}..."
    )

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED
    ) as archive:

        for filename in FILES_TO_INCLUDE:

            path = (
                PROJECT_DIR /
                filename
            )

            if not path.exists():

                raise FileNotFoundError(
                    f"Missing file: {filename}"
                )

            archive.write(
                path,
                arcname=filename
            )

            print(
                f"Included: {filename}"
            )

    checksum = sha256_file(
        zip_path
    )

    checksum_path = (
        OUTPUT_DIR /
        f"{zip_name}.sha256"
    )

    checksum_path.write_text(
        checksum,
        encoding="utf-8"
    )

    print()
    print(
        f"Package: {zip_path}"
    )

    print(
        f"SHA-256: {checksum}"
    )

    print()
    print(
        "Release package created successfully."
    )


if __name__ == "__main__":

    main()