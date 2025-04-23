# git-restore

restore files from git repos


### Install
```
pip install -r requirements.txt
```

### Usage
```
usage: git-restore.py [-h] (--repo-url REPO_URL | --repo-path REPO_PATH) [--output-dir OUTPUT_DIR] [--list-only]

List or restore deleted files from a Git repo with rich output.

options:
  -h, --help            show this help message and exit
  --repo-url REPO_URL   GitHub repo URL
  --repo-path REPO_PATH
                        Path to a local Git repo
  --output-dir OUTPUT_DIR
                        Directory to save restored files
  --list-only           Only list deleted files, do not restore
```