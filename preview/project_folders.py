"""User-selected file folders never change a project's Codex scan context."""
from pathlib import Path


def folder_key(project):
    return 'codex:'+project['codex_id'] if project.get('codex_id') else project['id']


def file_folder(project, overlay):
    return overlay.get('project_folders', {}).get(folder_key(project), {}).get('path') or project['path']


def decorate_projects(projects, overlay):
    result = []
    for project in projects:
        custom = overlay.get('project_folders', {}).get(folder_key(project))
        path = file_folder(project, overlay)
        result.append({**project, 'file_path': path,
            'file_path_source': 'user' if custom else project.get('source', 'catalog'),
            'file_path_available': Path(path).is_dir()})
    return result
