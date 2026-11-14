"""Check the public release files against the build manifest."""

import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen


def download(url):
    for attempt in range(5):
        try:
            with urlopen(url, timeout=30) as response:
                return response.read()
        except HTTPError as error:
            if attempt == 4 or error.code not in (404, 429, 500, 502, 503, 504):
                raise
            time.sleep(5)


def main():
    wheel_url, manifest_path = sys.argv[1:]
    base, wheel = wheel_url.rsplit("/", 1)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if wheel not in manifest:
        raise ValueError("The release wheel is missing from the build manifest")
    for name, expected in manifest.items():
        digest = hashlib.sha256(download(f"{base}/{name}")).hexdigest()
        if digest != expected:
            raise ValueError(f"Public release checksum mismatch for {name}")
        print(f"{name} {digest}")
    if json.loads(download(f"{base}/SHA256.json")) != manifest:
        raise ValueError("Public release manifest differs from the build manifest")


if __name__ == "__main__":
    main()
