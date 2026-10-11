"""Copy reviewed NEW plist files into this user's LaunchAgents. Does not load jobs."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import platform
import sys

from configure_launchd import API_LABEL, CADDY_LABEL


def install(source, destination):
    source, destination = Path(source).expanduser(), Path(destination).expanduser()
    names = [p.name for p in source.glob("*.plist")]
    if API_LABEL+".plist" not in names or not set(names) <= {API_LABEL+".plist",CADDY_LABEL+".plist"}:
        raise ValueError("invalid_generated_directory")
    contents = {}
    for name in names:
        p = source/name
        if p.is_symlink() or p.stat().st_uid != os.getuid() or p.stat().st_mode & 0o077:
            raise ValueError("private_owned_source_required")
        contents[name] = p.read_bytes()
        if plistlib.loads(contents[name])["Label"]+".plist" != name:
            raise ValueError("label_mismatch")
        if (destination/name).exists() or (destination/name).is_symlink():
            raise FileExistsError("installed_file_exists")
    if destination.is_symlink():
        raise ValueError("symlink_destination")
    destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    created = []
    try:
        for name, raw in contents.items():
            p = destination/name
            with p.open("xb") as stream:
                created.append(p)
                os.fchmod(stream.fileno(),0o600)
                stream.write(raw)
    except OSError:
        for p in created: p.unlink()
        raise
    return {"status":"installed_not_loaded","files":[str(p) for p in created]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from",dest="source",type=Path,required=True)
    args=parser.parse_args()
    try:
        if platform.system() != "Darwin":raise ValueError()
        result=install(args.source,Path.home()/"Library/LaunchAgents")
    except (OSError,ValueError,KeyError):
        parser.error("Mac and reviewed private generated files required; existing installed plists are never overwritten")
    print(json.dumps(result))
    return 0


if __name__=="__main__":sys.exit(main())
