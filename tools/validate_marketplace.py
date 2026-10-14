#!/usr/bin/env python3
import hashlib
import json
import re
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def download(url: str, destination: Path) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"asset URL must use HTTPS: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "SideWeave-Marketplace-Validator/1"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
        output.write(response.read())


def write_public_key(key_text: str, destination: Path, publisher: str, key_id: str) -> None:
    normalized = key_text.strip()
    if "untrusted comment:" not in normalized:
        normalized = f"untrusted comment: {publisher}/{key_id}\n{normalized}"
    destination.write_text(normalized + "\n", encoding="utf-8")


def validate() -> None:
    catalog = read_json(ROOT / "marketplace.json")
    directory = read_json(ROOT / "publishers.json")
    if type(catalog.get("schema_version")) is not int or catalog["schema_version"] != 1:
        raise ValueError("unknown marketplace schema_version")
    if type(directory.get("schema_version")) is not int or directory["schema_version"] != 1:
        raise ValueError("unknown marketplace or publisher schema_version")

    publishers = {}
    for publisher in directory.get("publishers", []):
        publisher_id = publisher.get("id", "")
        if not ID_RE.fullmatch(publisher_id) or not publisher.get("name"):
            raise ValueError(f"invalid publisher: {publisher_id}")
        keys = {}
        for key in publisher.get("keys", []):
            if key.get("algorithm") != "minisign" or key.get("status") not in {"active", "retired", "revoked"}:
                raise ValueError(f"invalid key record: {publisher_id}/{key.get('id')}")
            if not key.get("id") or not key.get("public_key") or key["id"] in keys:
                raise ValueError(f"invalid or duplicate key: {publisher_id}/{key.get('id')}")
            keys[key["id"]] = key
        publishers[publisher_id] = {"name": publisher["name"], "keys": keys}

    ids = set()
    for kind, items in (("plugin", catalog.get("plugins", [])), ("skin", catalog.get("skins", []))):
        for item in items:
            item_id = item.get("id", "")
            if not ID_RE.fullmatch(item_id) or not item.get("name"):
                raise ValueError(f"invalid {kind} item: {item_id}")
            identity = (kind, item_id)
            if identity in ids:
                raise ValueError(f"duplicate {kind} ID: {item_id}")
            ids.add(identity)
            package_type = item.get("type")
            allowed = {"skin"} if kind == "skin" else {"web", "native"}
            if package_type not in allowed:
                raise ValueError(f"unsupported package type for {item_id}: {package_type}")
            publisher = publishers.get(item.get("publisher"))
            if not publisher:
                raise ValueError(f"unknown publisher for {item_id}: {item.get('publisher')}")
            versions = item.get("versions", [])
            by_version = {}
            for version in versions:
                number = version.get("version", "")
                if not number or number in by_version:
                    raise ValueError(f"empty or duplicate version for {item_id}: {number}")
                by_version[number] = version
            latest = item.get("latest")
            if latest not in by_version:
                raise ValueError(f"latest does not point into versions for {item_id}")
            capabilities = set(item.get("capabilities", []))
            for version in versions:
                number = version["version"]
                key_id = version.get("key_id")
                key = publisher["keys"].get(key_id)
                if not key:
                    raise ValueError(f"unknown publisher key for {item_id}@{number}: {key_id}")
                if key["status"] == "revoked":
                    raise ValueError(f"revoked key cannot publish a catalog version: {item_id}@{number}")
                if number == latest and key["status"] != "active":
                    raise ValueError(f"latest version requires an active key: {item_id}")
                release = version.get("release", {})
                urls = [release.get("url"), release.get("signature_url"), release.get("checksum_url")]
                if not release.get("tag") or not release.get("asset") or not all(url and url.startswith("https://") for url in urls):
                    raise ValueError(f"invalid exact asset URLs for {item_id}@{number}")
                with tempfile.TemporaryDirectory(prefix="sideweave-market-") as temporary:
                    work = Path(temporary)
                    archive = work / "package.zip"
                    signature = work / "package.minisig"
                    checksum = work / "package.sha256"
                    public_key = work / "publisher.pub"
                    download(urls[0], archive)
                    download(urls[1], signature)
                    download(urls[2], checksum)
                    expected_hash = checksum.read_text(encoding="utf-8").split()[0].lower()
                    actual_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
                    if expected_hash != actual_hash:
                        raise ValueError(f"SHA256 mismatch for {item_id}@{number}")
                    write_public_key(key["public_key"], public_key, item["publisher"], key_id)
                    subprocess.run(["minisign", "-Vm", str(archive), "-x", str(signature), "-p", str(public_key)], check=True)
                    with zipfile.ZipFile(archive) as package:
                        manifest = json.loads(package.read("manifest.json"))
                    expected = {
                        "id": item_id,
                        "version": number,
                        "type": package_type,
                        "publisher": item["publisher"],
                        "key_id": key_id,
                    }
                    for field, value in expected.items():
                        if manifest.get(field) != value:
                            raise ValueError(f"manifest {field} mismatch for {item_id}@{number}")
                    if set(manifest.get("capabilities", manifest.get("permissions", []))) != capabilities:
                        raise ValueError(f"manifest capabilities mismatch for {item_id}@{number}")
                    if package_type == "native" and manifest.get("requires_trust") is not True:
                        raise ValueError(f"native manifest must set requires_trust for {item_id}")

    print("Marketplace catalog and all referenced packages are valid.")


if __name__ == "__main__":
    validate()
