#!/usr/bin/env python3

import argparse
import json
import os
import pkg_resources
import re
import sys

import git
import tqdm
import whatthepatch

import detector
import resolver


class Color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'


def error(message, fatal=False):
    print(
        '{0}{1}ERROR:{3} {2}'.format(Color.BOLD, Color.RED, message, Color.END)
    )

    if fatal:
        sys.exit(1)


def dump_results(version_results):
    for version, results in version_results.items():
        print(
            '{0}{1}\n{2}{3}'.format(
                Color.BOLD, version, '=' * len(version), Color.END
            )
        )

        for file, ratio in results.items():
            print('{0}: {1}'.format(file, str(ratio)))


def run(config):
    full_path = os.path.abspath(config.project)

    git_path = os.path.join(full_path, '.git')
    svn_path = os.path.join(full_path, '.svn')
    cvs_path = os.path.join(full_path, '.cvs')

    if os.path.exists(git_path):
        return run_git(config)
    elif os.path.exists(svn_path):
        return run_svn(config)
    elif os.path.exists(cvs_path):
        return run_cvs(config)
    else:
        return run_dir(config)


def run_git(config):
    sha1_regex = re.compile('([a-f0-9]{40})')

    full_path = os.path.abspath(config.project)

    try:
        repo = git.Repo(full_path)
    except git.exc.InvalidGitRepositoryError:
        error('project path is not a valid git repository', True)

    try:
        active_branch = repo.active_branch
    except TypeError:
        if len(repo.branches) == 1:
            active_branch = repo.branches[0]
            repo.git.checkout(active_branch)
        else:
            error('Repository is in a detatched HEAD state ' +
                  'and could not determine default branch.', True)

    if config.start_version:
        start_version = pkg_resources.parse_version(config.start_version)
    else:
        start_version = pkg_resources.SetuptoolsLegacyVersion('0.0.0')

    if config.versions:
        versions = config.versions.strip().split(',')
    else:
        versions = []
        for tag in repo.tags:
            if start_version <= pkg_resources.parse_version(tag.name):
                versions.append(tag.name)

    if not config.debug:
        versions = tqdm.tqdm(versions)

    version_results = {}
    patch_text = config.patch.read()
    patch = [diff for diff in whatthepatch.parse_patch(patch_text)]

    match = sha1_regex.match(patch_text.split()[1])

    if match:
        sha = match.group(1)
    else:
        raise Exception('No commit hash found in patch')

    if config.debug:
        print('Starting from commit sha {}'.format(sha))

    try:
        for version in versions:
            if version in repo.branches:
                repo.git.branch('-D', version)

            if config.debug:
                print('Checking out {0}'.format(version))

            if version not in repo.tags:
                raise ValueError('No such version "{}"'.format(version))
            repo.git.reset('--hard')
            repo.git.clean('-df')
            repo.git.checkout(version)

            diffs = []
            for diff in patch:
                path = resolver.resolve_path(
                    repo, sha, version, diff.header.new_path, config.debug
                )

                header = diff.header._replace(new_path=path)

                adjusted_diff = diff._replace(header=header)
                diffs.append(adjusted_diff)

            config.patch = diffs
            version_results[version] = detector.run(config)
            repo.git.checkout(active_branch)

            if config.debug:
                print('Removing {0}'.format(version))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        error(str(e))
        version_results = None
    finally:
        print('\r', end='')
        repo.git.reset('--hard')
        repo.git.clean('-df')
        repo.git.checkout(active_branch)

    return version_results


def run_svn(config):
    pass


def run_cvs(config):
    pass


def run_dir(config):
    runner_config = config
    for version in os.listdir(config.project):
        full_path = os.path.join(config.project, version)


def process_arguments():
    parser = argparse.ArgumentParser(
        description='''
            Checkout each version of a codebase and run a patch check
            against it.
        '''
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Turn on debugging'
    )

    parser.add_argument(
        '--results',
        type=argparse.FileType('w+'),
        default=sys.stdout,
        help='Path to store the results'
    )

    parser.add_argument(
        '--start-version',
        metavar='VERSION',
        help='Version at which to start; ignored if using --versions'
    )

    parser.add_argument(
        '--versions',
        help='Comma separated list of versions against which to execute'
    )

    parser.add_argument(
        'patch',
        type=argparse.FileType('r'),
        help='Path to the patch to be tested'
    )

    parser.add_argument(
        'project',
        help='Path to the root of the project repository'
    )

    return parser.parse_args()


def main():
    config = process_arguments()

    print('''
            {0}Project:{3} {2}
            {0}  Patch:{3} {1}
        '''.format(
            Color.BOLD,
            os.path.basename(config.patch.name),
            os.path.basename(os.path.abspath(config.project)),
            Color.END
        )
    )

    version_results = run(config)

    if version_results:
        json.dump(version_results, config.results, sort_keys=True, indent=4)

if __name__ == '__main__':
    main()
