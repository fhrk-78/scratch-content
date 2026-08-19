import os
from pathlib import Path
import yaml
import requests
import re
import zipfile
from datetime import datetime
import math

VERSION_DETECT_REGEX = r'(v[0-9]+(?:\.[0-9]+)*)'

def download(url: str, filename: Path) -> None:
  content = requests.get(url).content
  with open(filename, mode='wb') as f:
    f.write(content)

def zip(sourceDir: Path, filename: Path) -> None:
  with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for path in sourceDir.iterdir():
      if path.is_file():
        zipf.write(path, arcname=path.name)

def filename_nize(s: str) -> str:
  return re.sub(r'[ \\/:\*\?"<>\|]', '_', s.strip())

if __name__ == '__main__':
  rootdir = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd()))

  # get config
  with open(rootdir/'scripts'/'config.yml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

  projects = requests.get(f'https://api.scratch.mit.edu/users/{config['username']}/projects').json()

  for target in projects:
    # exclude check
    if target['id'] in config['exclude']:
      continue

    # get meta
    project = requests.get(f'https://api.scratch.mit.edu/projects/{str(target['id'])}/').json()
    version = re.findall(VERSION_DETECT_REGEX, project['title'])
    
    if len(version) == 0:
      pjroot = rootdir/'projects'/filename_nize(project['title'])
    else:
      pjroot = rootdir/'projects'/filename_nize(re.sub(VERSION_DETECT_REGEX, '', str(project['title'])))
    pjroot.mkdir(parents=True, exist_ok=True)

    # get lastupdate
    lastupdatetxt = pjroot/'lastupdate.txt'
    lastupdate = None
    if lastupdatetxt.exists():
      with open(lastupdatetxt, 'r', encoding='utf-8') as f:
        lastupdate = int(f.read())

    # write README.md
    download(project['image'], pjroot/'thumbnail.png')
    with open(pjroot/'README.md', 'w', encoding='utf-8') as f:
      f.writelines([
        f'# {project['title']}\n\n',
        '![thumbnail](./thumbnail.png)\n\n',
        '## Interactions\n\n',
        project['instructions'],
        '\n\n## Descriptions\n\n',
        project['description'],
        '\n'
      ])

    modified = datetime.fromisoformat(project['history']['modified']).timestamp()
    if lastupdate == modified:
      print(f'{target['id']} is up to date')
      continue

    # directory setup
    pjUnzipped = pjroot/'unzipped'
    pjUnzipped.mkdir(exist_ok=True)

    # download body
    token = project['project_token']
    projectJSON = requests.get(f'https://projects.scratch.mit.edu/{str(project['id'])}?token={token}')
    with open(pjUnzipped/'project.json', 'wb') as f:
      f.write(projectJSON.content)

    # list assets
    assets: list[str] = []
    for sprite in projectJSON.json()['targets']:
      for costume in sprite['costumes']:
        assets.append(costume['md5ext'])
      for sound in sprite['sounds']:
        assets.append(sound['md5ext'])

    # download all assets
    for asset in assets:
      download(f"https://assets.scratch.mit.edu/internalapi/asset/{asset}/get", pjUnzipped / asset)

    # zip project
    if len(version) == 0:
      zip(pjUnzipped, pjroot/'latest.sb3')
    else:
      pjTags = pjroot/'tags'
      pjTags.mkdir(exist_ok=True)
      zip(pjUnzipped, pjTags / f'{version[0]}.sb3')

    with open(lastupdatetxt, 'w', encoding='utf-8') as f:
      f.write(str(math.floor(modified)))

    print(f'{target['id']} succefy packed')
