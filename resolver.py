#!/usr/bin/env python3

import os

import git

def resolve_path(repo, start, end, path, debug=False):
    if repo.is_ancestor(start, end):
        rev_list = '{start}..{end}'.format(
            start=start, end=end
        )

        prev = repo.commit(start)
        prev_path = True

        tree = prev.tree
        for path_element in path.split(os.path.sep):
            try:
                tree = tree[path_element]
            except KeyError:
                prev_path = False
                break

        if not prev_path:
            raise Exception('Path does not exist in start object')

        prev_path = tree.path

        if debug:
            print('Start: ' + prev_path)

        commits = repo.git.rev_list(rev_list, ancestry_path=True, reverse=True)
        commits = commits.splitlines()

        commits = [repo.commit(commit) for commit in commits]

        for commit in commits:
            diffs = prev.diff(commit)

            if debug:
                print(commit.hexsha, end='')

            count = 0
            for diff in diffs:
                if diff.a_path == prev_path:
                    count += 1

                    if debug:
                        print(': a : {1} :: b : {2}'.format(
                            commit.hexsha, diff.a_path, diff.b_path
                        ), end='')

                    prev_path = diff.b_path

                    if diff.deleted_file:
                        prev_path = 'deleted'

            if count > 1:
                raise Exception('found more than 1 matching diff')

            if debug:
                print()

            prev = commit

        if debug:
            print('Finish: ' + prev_path)

        return prev_path
    elif repo.is_ancestor(end, start):
        return path
    else:
        raise Exception('Start and end objects are not in a related path')

if __name__ == '__main__':
    import sys

    resolve_path(
        git.Repo(sys.argv[1]),
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        True
    )
