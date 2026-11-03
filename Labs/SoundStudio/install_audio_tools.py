"""Install the official pinned Rubber Band CLI in this studio's private runtime."""
from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]/'Saved'/'SoundStudio'/'tools'
URL='https://breakfastquay.com/files/releases/rubberband-4.0.0-gpl-executable-windows.zip'
SHA256='f2d47fc64dbb42f6cc62edf7933ac4fa89d8f0ef8b9cf97b6afc263a7fe05644'
EXECUTABLE=ROOT/'rubberband-4.0.0'/'rubberband-4.0.0-gpl-executable-windows'/'rubberband-r3.exe'


def install():
    ROOT.mkdir(parents=True,exist_ok=True)
    if not EXECUTABLE.is_file():
        archive=ROOT/'rubberband-4.0.0.zip'
        if not archive.is_file():
            with urllib.request.urlopen(URL,timeout=45) as response:
                archive.write_bytes(response.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:
            raise RuntimeError('Rubber Band download checksum differs from the pinned release.')
        target=(ROOT/'rubberband-4.0.0').resolve()
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                if not (target/item.filename).resolve().is_relative_to(target):
                    raise RuntimeError('Unexpected path in audio-tools archive.')
            bundle.extractall(target)
    config_path=HERE/'runtime.json'
    config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    config['rubberband']=str(EXECUTABLE)
    config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    print(EXECUTABLE)


if __name__=='__main__':install()
