#!/usr/bin/env python3
"""Give a signed AAB conventional JAR metadata order (NEW-001).

AGP writes META-INF/MANIFEST.MF after META-INF/*.SF and the signature block. JarFile
still verifies such an archive, but JarInputStream (and other streaming readers) sees no
manifest and treats every entry as unsigned. That parser differential lets two standard
verifiers disagree about the same artifact.

JAR v1 signatures cover entry contents through the manifest, not ZIP order, so moving
the manifest and signature files to the front keeps the signature valid. This tool:
  * never changes an entry name, byte, timestamp, compression method or attribute;
  * fails closed on duplicate names, a missing manifest or missing signature files;
  * leaves an already conventional archive untouched;
  * does not verify signatures: the release script still runs jarsigner afterwards.

Usage: normalize-aab-signature-order.py [--check] AAB
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import zipfile
from pathlib import Path

MANIFEST = "META-INF/MANIFEST.MF"
SIGNATURE_SUFFIXES = (".SF", ".RSA", ".DSA", ".EC")


class OrderError(RuntimeError):
    pass


def is_signature_file(name: str) -> bool:
    upper = name.upper()
    if not upper.startswith("META-INF/") or "/" in upper[len("META-INF/"):]:
        return False
    return upper.endswith(SIGNATURE_SUFFIXES) or upper[len("META-INF/"):].startswith("SIG-")


def entries(path: Path) -> list[zipfile.ZipInfo]:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
    names = [info.filename for info in infos]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise OrderError(f"duplicate ZIP entry names are ambiguous: {duplicates[:5]}")
    if MANIFEST not in names:
        raise OrderError("signed archive has no META-INF/MANIFEST.MF")
    if not any(is_signature_file(name) for name in names):
        raise OrderError("archive has no JAR signature files")
    return infos


def check(path: Path) -> None:
    """Enforce the order JarInputStream needs to see the manifest and signatures."""
    names = [info.filename for info in entries(path)]
    position = 1 if names[0] == "META-INF/" else 0
    if names[position] != MANIFEST:
        raise OrderError(
            f"META-INF/MANIFEST.MF is entry {names.index(MANIFEST) + 1} of {len(names)}; "
            "streaming JAR readers will not see it")
    first_content = next((i for i, name in enumerate(names) if not name.startswith("META-INF/")), len(names))
    late = [name for name in names[first_content:] if is_signature_file(name)]
    if late:
        raise OrderError(f"signature files follow signed content: {late}")


def normalize(path: Path) -> bool:
    try:
        check(path)
        return False
    except OrderError:
        infos = entries(path)  # re-raises structural problems that ordering cannot fix
    directory = [i for i in infos if i.filename == "META-INF/"]
    manifest = [i for i in infos if i.filename == MANIFEST]
    signatures = [i for i in infos if is_signature_file(i.filename)]
    chosen = {id(i) for i in directory + manifest + signatures}
    ordered = directory + manifest + signatures + [i for i in infos if id(i) not in chosen]

    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temporary_path = Path(temporary)
    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary_path, "w") as target:
            for info in ordered:
                clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                clone.compress_type = info.compress_type
                clone.external_attr = info.external_attr
                clone.create_system = info.create_system
                clone.comment = info.comment
                target.writestr(clone, source.read(info.filename))
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary_path) as target:
            before = [i.filename for i in source.infolist()]
            after = [i.filename for i in target.infolist()]
            if sorted(before) != sorted(after):
                raise OrderError("normalized archive changed the entry set")
            for name in before:
                if source.read(name) != target.read(name):
                    raise OrderError(f"normalized archive changed entry bytes: {name}")
                old, new = source.getinfo(name), target.getinfo(name)
                if (old.compress_type, old.date_time, old.external_attr) != (new.compress_type, new.date_time, new.external_attr):
                    raise OrderError(f"normalized archive changed entry metadata: {name}")
        check(temporary_path)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify order without writing")
    parser.add_argument("aab", type=Path)
    args = parser.parse_args()
    try:
        if not args.aab.is_file():
            raise OrderError(f"archive is missing: {args.aab}")
        if args.check:
            check(args.aab)
            print(f"AAB JAR metadata order OK: {args.aab}")
        else:
            changed = normalize(args.aab)
            print(("normalized" if changed else "already conventional") + f" AAB JAR metadata order: {args.aab}")
    except (OrderError, zipfile.BadZipFile) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
