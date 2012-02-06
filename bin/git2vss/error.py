"""
git2vss specific error classes.
"""

class Git2VSSError(Exception):
    """
    A git2vss base error class.
    """

    def __init__(self, msg, git_repo):
        """
        Create an error with the specified message.
        """

        super(Git2VSSError, self).__init__(msg)

        self.git_repo = git_repo

class Git2VSSMissingOptionError(Git2VSSError):
    """
    A git2vss missing option error class.
    """

    def __init__(self, option, git_repo):
        """
        Create a missing option error for the specified option.
        """

        super(Git2VSSMissingOptionError, self).__init__('Required option %s was not found' % repr(option), git_repo)

        self.option = option

