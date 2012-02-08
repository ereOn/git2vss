"""
git2vss utility functions.
"""

import vss
import tempfile
import shutil
import os
import stat

from error import Git2VSSMissingOptionError, Git2VSSInvalidGitStatusError
from git import GitCommandError

def __git_python_unescape(value):
    """
    Fixes a bug in GitPython which doesn't unescape values.

    Return value unescaped.

    """

    value = value.replace('\\\\', '\\')
    value = value.replace('\\"', '"')

    return value

def __get_vss_instance(git_repo, repository_path=None, ss_path=None):
    """
    Get the VSS instance according to the specified parameters.
    """

    config = git_repo.config_reader()

    if repository_path is None:
        if config.has_option('git2vss', 'repository-path'):
            repository_path = config.get_value('git2vss', 'repository-path')
            # TODO: Remove the line below when the bug in GitPython is fixed.
            repository_path = __git_python_unescape(repository_path)
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
            # TODO: Remove the line below when the bug in GitPython is fixed.
            vss_project_path = __git_python_unescape(vss_project_path)
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

def __scan_directory(path):
    """
    Generate a list of all files and directories under the specified path. VSS specials files are ignored.
    """

    r_dirs = []
    r_files = []

    for root, dirs, files in os.walk(path):
        for dname in dirs:
            r_dirs.append(os.path.relpath(os.path.join(root, dname), path))
        for fname in files:
            if not fname.endswith('.scc'):
                r_files.append(os.path.relpath(os.path.join(root, fname), path))

    return r_dirs, r_files

def __diff(old, new):
    """Compare two lists and return a tuple in the form (only_in_old, in_both, only_in_new)."""

    o = set(old)
    n = set(new)
    only_in_old = list(o - n)
    only_in_new = list(n - o)
    in_both = list(set.intersection(o, n))

    return (only_in_old, in_both, only_in_new)

def push(git_repo, ref=None, repository_path=None, vss_project_path=None, ss_path=None):
    """
    Performs a push on the VSS repository.
    """

    if git_repo.is_dirty():
        raise Git2VSSInvalidGitStatusError('Working directory is dirty. Refusing to push.', git_repo)

    vss_repo = __get_vss_instance(git_repo=git_repo, repository_path=repository_path, ss_path=ss_path)
    vss_project_path = __get_vss_project_path(git_repo, vss_project_path)

    vss_temp_dir = tempfile.mkdtemp()

    try:
        git_temp_dir = tempfile.mkdtemp()

        try:
            current_head = str(git_repo.head.commit)

            if ref:
                git_repo.git.checkout(ref)

            try:
                git_repo.git.checkout_index('-f', '-a', '--prefix=' + git_temp_dir + '/')
            finally:
                if ref:
                    git_repo.git.checkout(current_head)

            vss_repo.checkout(vss_project_path, recursive=True, get_folder=vss_temp_dir, output='error')

            try:
                # We compare the folders
                vss_dirs, vss_files = __scan_directory(vss_temp_dir)
                git_dirs, git_files = __scan_directory(git_temp_dir)

                deleted_dirs, current_dirs, new_dirs = __diff(vss_dirs, git_dirs)
                deleted_files, current_files, new_files = __diff(vss_files, git_files)

                # First commit the updated files
                for fname in current_files:
                    shutil.copyfile(os.path.join(git_temp_dir, fname), os.path.join(vss_temp_dir, fname))

                # We checkin the files back
                vss_repo.checkin(vss_project_path, recursive=True, get_folder=vss_temp_dir, output='error', comment_no_text=True)

            except Exception, ex:

                # Something went wrong: we undo the checkout and propagate the exception
                vss_repo.undo_checkout(vss_project_path, recursive=True, get_folder=vss_temp_dir, output='error')
                raise ex

            # We remove the deleted folders and files

            for fname in deleted_files:
                vss_dir = os.path.join(vss_project_path, fname).replace(os.sep, '/')
                vss_repo.delete(vss_dir)

            for dname in reversed(sorted(deleted_dirs, key=len)):
                vss_repo.set_current_project(vss_project_path.replace(os.sep, '/'))
                vss_dir = os.path.join(vss_project_path, dname).replace(os.sep, '/')
                vss_repo.delete(vss_dir)

            # We then add the new folders and files
            for dname in sorted(new_dirs, key=len):
                vss_dir = os.path.join(vss_project_path, dname).replace(os.sep, '/')
                vss_repo.create(vss_dir, comment_no_text=True)

            for fname in new_files:
                vss_dir = os.path.join(vss_project_path, os.path.dirname(fname)).replace(os.sep, '/')
                vss_repo.set_current_project(vss_dir)
                vss_repo.add(os.path.join(git_temp_dir, fname), comment_no_text=True)

        finally:
            __rmtree(git_temp_dir)
    finally:
        __rmtree(vss_temp_dir)

    if 'VSS-HEAD' in git_repo.tags:
        git_repo.delete_tag('VSS-HEAD')

    print 'Push to VSS done. VSS-HEAD is now at %s.' % (git_repo.create_tag('VSS-HEAD').commit.hexsha)

def pull(git_repo, repository_path=None, vss_project_path=None, ss_path=None):
    """
    Performs a pull on the VSS repository.
    """

    if git_repo.is_dirty():
        raise Git2VSSInvalidGitStatusError('Working directory is dirty. Refusing to pull.', git_repo)

    if 'vss-merge' in git_repo.branches:
        raise Git2VSSInvalidGitStatusError('The vss-merge branch still exists. Refusing to pull.', git_repo)

    git_repo_head = str(git_repo.head.ref)

    if 'VSS-HEAD' in git_repo.tags:
        git_repo.git.checkout('-b', 'vss-merge', 'VSS-HEAD')
    else:
        git_repo.git.checkout('-b', 'vss-merge', 'HEAD')

    vss_repo = __get_vss_instance(git_repo=git_repo, repository_path=repository_path, ss_path=ss_path)
    vss_project_path = __get_vss_project_path(git_repo, vss_project_path)

    vss_temp_dir = tempfile.mkdtemp()

    try:
        vss_repo.get(vss_project_path, recursive=True, get_folder=vss_temp_dir, output='error', ignore='all')

        git_temp_dir = tempfile.mkdtemp()

        try:
            git_repo.git.checkout_index('-f', '-a', '--prefix=' + git_temp_dir + '/')

            # We compare the folders
            vss_dirs, vss_files = __scan_directory(vss_temp_dir)
            git_dirs, git_files = __scan_directory(git_temp_dir)

        finally:
            __rmtree(git_temp_dir)

        deleted_dirs, current_dirs, new_dirs = __diff(git_dirs, vss_dirs)
        deleted_files, current_files, new_files = __diff(git_files, vss_files)

        # Add the updated files to the index
        for fname in current_files + new_files:
            dst_file = os.path.join(git_repo.working_dir, fname)
            shutil.copyfile(os.path.join(vss_temp_dir, fname), dst_file)
            os.chmod(dst_file, stat.S_IWRITE)
            git_repo.git.add(fname)

        # Remove the deleted files from the index
        for fname in deleted_files:
            dst_file = os.path.join(git_repo.working_dir, fname)
            os.chmod(dst_file, stat.S_IWRITE)
            os.remove(dst_file)
            git_repo.git.rm(fname)

    finally:
        __rmtree(vss_temp_dir)

    try:
        git_repo.git.commit('-m', 'VSS pull from %s:%s' % (vss_repo.repository_path, vss_project_path))
        print 'Commited changes from upstream.'

    except GitCommandError:
        print 'No changes from upstream: nothing to commit.'

    finally:
        git_repo.git.checkout(git_repo_head)

        try:
            git_repo.git.merge('vss-merge')
            git_repo.git.branch('-d', 'vss-merge')

        except GitCommandError:
            print 'Automatic merge failed. Please fix it and delete "vss-merge" you are done.'

    if 'VSS-HEAD' in git_repo.tags:
        git_repo.delete_tag('VSS-HEAD')

    print 'Pull from VSS done. VSS-HEAD is now at %s.' % (git_repo.create_tag('VSS-HEAD').commit.hexsha)

