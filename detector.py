#!/usr/bin/env python3

import argparse
import json
import os
import string
import sys

import chardet
import whatthepatch
import yaml

import util

whitelist = set()
blacklist = ['test', 'tests', 'spec']

module_path = os.path.dirname(os.path.realpath(__file__))
resources_path = os.path.join(module_path, 'resources')

try:
    with open(os.path.join(resources_path, 'languages.yml'), 'r') as file:
        languages = yaml.load(file)
except FileNotFoundError:
    print('Missing `languages.yml\': https://github.com/github/linguist/blob/master/lib/linguist/languages.yml')
    sys.exit(1)

for key, value in languages.items():
    if 'extensions' in value:
        whitelist.update(value['extensions'])

def whitelisted(name):
    return any(name.lower().endswith(item) for item in whitelist)

def blacklisted(name):
    return any(item in name.lower() for item in blacklist)

def compare(first, second):
    return all(token in second.strip().split() for token in first.strip().split())

def run(config):
    total_patch_additions = 0
    total_patch_deletions = 0

    detected_patch_additions = 0
    detected_patch_deletions = 0

    ratios = {}

    for diff in config.patch:
        new_source_path = os.path.join(config.project, diff.header.path)
        old_source_path = os.path.join(config.project, diff.header.old_path)

        full_path = os.path.abspath(new_source_path)
        if os.path.exists(full_path):
            if config.debug:
                print('Found {0}'.format(full_path))
        else:
            full_path = os.path.abspath(old_source_path)
            if os.path.exists(full_path):
                if config.debug:
                    print('WARNING: Found file at old path: {0}'.format(
                        full_path
                    ))

        if blacklisted(full_path) or not whitelisted(full_path):
            continue

        detected_additions = 0
        detected_deletions = 0

        ratios[diff.header.path] = {}

        additions = []
        deletions = []

        for change in diff.changes:
            # Ignore empty or whitespace lines
            if not change[2] or change[2].isspace():
                continue
            # line was unchanged
            elif change[0] == change[1]:
                continue
            # line was changed, content is the same
            elif change[0] and change[1] and change[0] != change[1]:
                continue
            # line was inserted
            elif not change[0] and change[1]:
                additions.append(change[2])
            # line was removed
            elif change[0] and not change[1]:
                deletions.append(change[2])
            # should never happen
            else:
                print('WARNING: Could not detect change type')
                raise Exception(change)

        if config.debug:
            print('Modified lines: ', end='')
            print(set(additions).intersection(deletions))

        if os.path.exists(full_path):
            file = open(full_path, 'rb')
            detection = chardet.detect(file.read())

            if config.debug:
                print('{0}: encoding is {1} with {2} confidence'.format(
                    full_path, detection['encoding'], detection['confidence']
                ))

            file.close()

            with open(full_path, 'r', encoding=detection['encoding']) as file:
                source = file.readlines()

                for addition in additions:
                    for line in source:
                        if compare(addition, line):
                            detected_additions += 1
                            break

                for deletion in deletions:
                    found = False
                    for line in source:
                        if compare(deletion, line):
                            found = True
                            break

                    if not found:
                        detected_deletions += 1
        else:
            if config.debug:
                print('WARNING: File {0} does not exist'.format(full_path))

        detected_patch_additions += detected_additions
        detected_patch_deletions += detected_deletions

        total_additions = len(additions)
        total_deletions = len(deletions)

        total_patch_additions += total_additions
        total_patch_deletions += total_deletions

        assert detected_additions <= total_additions
        assert detected_deletions <= total_deletions

        ratios[diff.header.path]['additions'] = detected_additions / total_additions if total_additions > 0 else None
        ratios[diff.header.path]['deletions'] = detected_deletions / total_deletions if total_deletions > 0 else None
        ratios[diff.header.path]['status'] = diff.header.status

    # We are confident unless all files of the change set cannot be found
    confident = not all(value['status'] is not 'deleted' for value in ratios.values())

    result = {
        'overall': {
            'additions': detected_patch_additions / total_patch_additions,
            'deletions': detected_patch_deletions / total_patch_deletions,
            'confident': confident
        },
        'breakdown': ratios
    }

    return result


def process_arguments():
    parser = argparse.ArgumentParser(
        description='''
            Test if a given patch has already been applied to a project's
            codebase.
        '''
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Turn on debugging'
    )

    parser.add_argument(
        'patch',
        type=argparse.FileType('r'),
        help='Path to the patch to be tested'
    )

    parser.add_argument(
        'project',
        help='Path to the root of the project source code'
    )

    return parser.parse_args()


def main():
    config = process_arguments()
    config.patch = util.load_patch(config.patch.read())
    print(json.dumps(run(config), indent=4))

if __name__ == '__main__':
    main()
