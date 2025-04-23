import argparse
import os
import shutil
from urllib.parse import urlparse
from git import Repo, GitCommandError
from rich.progress import Progress
from rich.console import Console
from rich.table import Table

console = Console()

def extract_repo_name(repo_input):
    if repo_input.endswith('.git'):
        return os.path.splitext(os.path.basename(urlparse(repo_input).path))[0]
    return os.path.basename(os.path.abspath(repo_input))

def clone_repo(repo_url, dest_dir):
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    return Repo.clone_from(repo_url, dest_dir)

def format_size(bytes_size):
    if bytes_size >= 1024 ** 3:
        return f"{bytes_size / (1024 ** 3):.2f} GB"
    elif bytes_size >= 1024 ** 2:
        return f"{bytes_size / (1024 ** 2):.2f} MB"
    elif bytes_size >= 1024:
        return f"{bytes_size / 1024:.2f} KB"
    else:
        return f"{bytes_size} B"

def get_excluded_extensions():
    try:
        with open("excluded_file_extensions.txt", "r") as f:
            return set(line.strip().lower() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def list_deleted_files_visual(repo_dir, min_size=None, max_size=None, exclude_ext=False, scan_percent=None):
    excluded_exts = get_excluded_extensions() if exclude_ext else set()
    repo = Repo(repo_dir)
    commits = list(repo.iter_commits('--all'))
    if scan_percent:
        commits = sorted(commits, key=lambda c: c.committed_datetime)
        cutoff = max(1, int(len(commits) * (scan_percent / 100)))
        commits = commits[:cutoff]

    table = Table(title="Deleted Files", show_lines=True)
    table.add_column("Commit", style="bold cyan", width=10)
    table.add_column("File Path", style="yellow")
    table.add_column("Size", justify="right")

    with Progress() as progress:
        task = progress.add_task("[cyan]Scanning commits...", total=len(commits))

        for commit in commits:
            progress.update(task, advance=1)
            parents = commit.parents
            if not parents:
                continue
            parent = parents[0]
            try:
                diff = parent.diff(commit, paths=None, create_patch=False)
                for d in diff:
                    if d.change_type == 'D':
                        path = d.a_path
                        if exclude_ext and os.path.splitext(path)[1].lower() in excluded_exts:
                            continue
                        try:
                            blob = parent.tree / path
                            size_bytes = blob.size
                            if (min_size and size_bytes < min_size) or (max_size and size_bytes > max_size):
                                continue
                            size_str = format_size(size_bytes)
                        except Exception:
                            size_str = "?"
                        table.add_row(commit.hexsha[:7], path, size_str)
            except GitCommandError:
                continue

    console.print(table)

def restore_deleted_files_visual(repo_dir, output_dir, min_size=None, max_size=None, exclude_ext=False, scan_percent=None):
    excluded_exts = get_excluded_extensions() if exclude_ext else set()
    os.makedirs(output_dir, exist_ok=True)
    repo = Repo(repo_dir)
    commits = list(repo.iter_commits('--all'))
    if scan_percent:
        commits = sorted(commits, key=lambda c: c.committed_datetime)
        cutoff = max(1, int(len(commits) * (scan_percent / 100)))
        commits = commits[:cutoff]

    with Progress() as progress:
        task = progress.add_task("[cyan]Restoring files...", total=len(commits))

        for commit in commits:
            progress.update(task, advance=1)
            parents = commit.parents
            if not parents:
                continue
            parent = parents[0]
            try:
                diff = parent.diff(commit, paths=None, create_patch=False)
                for d in diff:
                    if d.change_type == 'D':
                        file_path = d.a_path
                        if exclude_ext and os.path.splitext(file_path)[1].lower() in excluded_exts:
                            continue
                        safe_name = file_path.replace('/', '_')
                        full_path = os.path.join(output_dir, f"{commit.hexsha}___{safe_name}")
                        try:
                            blob = parent.tree / file_path
                            size_bytes = blob.size
                            if (min_size and size_bytes < min_size) or (max_size and size_bytes > max_size):
                                continue
                            with open(full_path, 'wb') as f:
                                f.write(blob.data_stream.read())
                            console.print(f"[green][+][/green] {file_path} -> {full_path}")
                        except (KeyError, GitCommandError):
                            console.print(f"[red][!][/red] Failed to restore: {file_path}")
            except GitCommandError:
                continue

def main():
    parser = argparse.ArgumentParser(description='List or restore deleted files from a Git repo with rich output.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--repo-url', help='GitHub repo URL')
    group.add_argument('--repo-path', help='Path to a local Git repo')
    parser.add_argument('--output-dir', help='Directory to save restored files')
    parser.add_argument('--list-only', action='store_true', help='Only list deleted files, do not restore')
    parser.add_argument('--minsize', type=int, help='Minimum file size in bytes')
    parser.add_argument('--maxsize', type=int, help='Maximum file size in bytes')
    parser.add_argument('--exclude-extensions', action='store_true', help='Exclude extensions listed in excluded_file_extensions.txt')
    parser.add_argument('--scan-oldest-commits', type=int, choices=range(1, 101), metavar='[1-100]', help='Only scan oldest X%% of commits')

    args = parser.parse_args()

    if args.repo_url:
        repo_name = extract_repo_name(args.repo_url)
        repo_path = repo_name
        console.print(f"[bold green][i][/bold green] Cloning [yellow]{args.repo_url}[/yellow] into [blue]{repo_path}[/blue]...")
        clone_repo(args.repo_url, repo_path)
    else:
        repo_path = args.repo_path
        repo_name = extract_repo_name(repo_path)
        console.print(f"[bold green][i][/bold green] Using local repo at [blue]{repo_path}[/blue]...")

    if args.list_only:
        console.print(f"[bold green][i][/bold green] Listing deleted files with size info...")
        list_deleted_files_visual(repo_path, args.minsize, args.maxsize, args.exclude_extensions, args.scan_oldest_commits)
    else:
        output_dir = args.output_dir or os.path.join("restored_repos", f"{repo_name}_restored")
        console.print(f"[bold green][i][/bold green] Restoring to [blue]{output_dir}[/blue]...")
        restore_deleted_files_visual(repo_path, output_dir, args.minsize, args.maxsize, args.exclude_extensions, args.scan_oldest_commits)

    if args.repo_url:
        shutil.rmtree(repo_path, ignore_errors=True)
        console.print(f"[bold green][i][/bold green] Removed cloned repo [blue]{repo_path}[/blue]")

    console.print("[bold green][✓] Done.[/bold green]")

if __name__ == '__main__':
    main()
