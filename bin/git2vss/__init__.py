"""
git2vss utility functions.
"""

import vss
import tempfile
import shutil
import os
import stat

from error import Git2VSSMissingOptionError, Git2VSSInvalidGitStatusError

def __get_vss_instance(git_repo, repository_path=None, ss_path=None):
    """
    Get the VSS instance according to the specified parameters.
    """

    config = git_repo.config_reader()

    if repository_path is None:
        if config.has_option('git2vss', 'repository-path'):
            repository_path = config.get_value('git2vss', 'repository-path')
        else:
            raise Git2VSSMissingOptionError('git2vss.repository-path', git_repo)

    return vss.VSS(repository_path=repository_path, ss_path=ss_path)

def __get_vss_project_path(git_repo, vss_project_path=None):
    """
    Get the VSS project path according to the specified parameters.
    """

    config = git_repo.config_reader()

    if vss_project_path is None:
        if config.has_option('git2vss', 'vss-project-path'):
            vss_project_path = config.get_value('git2vss', 'vss-project-path')
        else:
            raise Git2VSSMissingOptionError('git2vss.vss-project-path', git_repo)

    return vss_project_path

def __rmtree(path):
    """
    Recursively delete a given path, even if it has read-only attributes.
    """

    def force_delete(func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    shutil.rmtree(path, onerror=force_delete)

def __copytree(src, dst):
    """
    Recursively copy a tree from src to dst.
    """

    for root, dirs, files in os.walk(src):
        root = os.path.relpath(root, src)

        for dname in dirs:
            dst_dir = os.path.join(dst, root, dname)
            if os.path.isdir(dst_dir):
                pass
            else:
                if os.path.isfile(dst_dir):
                    os.remove(dst_dir)

                os.mkdir(dst_dir)

        for fname in files:
            if not os.path.splitext(fname)[1] in ('.scc'):
                src_file = os.path.join(src, root, fname)
                dst_file = os.path.join(dst, root, fname)

                if os.path.isfile(dst_file):
                    os.chmod(dst_file, stat.S_IWRITE)

                shutil.copy(src_file, dst_file)
                os.chmod(dst_file, stat.S_IWRITE)

def push(git_repo, ref=None, repository_path=None, vss_project_path=None, ss_path=None):
    """
    Performs a push on the VSS repository.
    """

    if git_repo.is_dirty():
        raise Git2VSSInvalidGitStatusError('Working directory is dirty. Refusing to push.', git_repo)

    vss_repo = __get_vss_instance(git_repo=git_repo, repository_path=repository_path, ss_path=ss_path)
    vss_project_path = __get_vss_project_path(git_repo, vss_project_path)

    temp_dir = tempfile.mkdtemp()

    try:
        vss_repo.checkout(vss_project_path, recursive=True, get_folder=temp_dir, output='error')

        # Lets export the git repository
        temp_git_repo_archive = tempfile.TemporaryFile()
        git_repo.archive(temp_git_repo_archive)

        # We compare the folders

        # We first commit the updated files

        try:
            # We checkin the files back
            vss_repo.checkin(vss_project_path, recursive=True, get_folder=temp_dir, output='error', comment_no_text=True)
        except Exception, ex:
            # Something went wrong: we undo the checkout and propagate the exception
            vss_repo.undo_checkout(vss_project_path, recursive=True, get_folder=temp_dir, output='error')
            raise ex

        # We then add the new files

        # We finally remove the deleted files
    finally:
        __rmtree(temp_dir)

def pull(git_repo, repository_path=None, vss_project_path=None, ss_path=None):
    """
    Performs a pull on the VSS repository.
    """

    if git_repo.is_dirty():
        raise Git2VSSInvalidGitStatusError('Working directory is dirty. Refusing to pull.', git_repo)

    vss_repo = __get_vss_instance(git_repo=git_repo, repository_path=repository_path, ss_path=ss_path)
    vss_project_path = __get_vss_project_path(git_repo, vss_project_path)

    temp_dir = tempfile.mkdtemp()

    try:
        vss_repo.get(vss_project_path, recursive=True, get_folder=temp_dir, output='error', ignore='all')
        __copytree(temp_dir, git_repo.working_dir)
    finally:
        __rmtree(temp_dir)
