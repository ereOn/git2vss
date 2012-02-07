"""
git2vss utility functions.
"""

import vss

from error import Git2VSSMissingOptionError

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

def __get_vss_project_path(git_repo, vss, vss_project_path=None):
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

def pull(git_repo, repository_path=None, vss_project_path=None, ss_path=None):
    """
    Performs a pull on the VSS repository.
    """

    vss_repo = __get_vss_instance(git_repo=git_repo, repository_path=repository_path, ss_path=ss_path)


