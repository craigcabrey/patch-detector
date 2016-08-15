#!/usr/bin/env python3

import os

import git


def resolve_path(repo, first, second, path, debug=False):
    if first == second:
        return (path, 'unchanged')

    first = repo.commit(first)
    second  = repo.commit(second)

    def exists_in_tree(tree, path):
        blob_path = True
        for path_element in path.split(os.path.sep):
            try:
                tree = tree[path_element]
            except KeyError:
                blob_path = False
                break

        if blob_path:
            blob_path = tree.path

        return blob_path

    if exists_in_tree(second.tree, path):
        return (path, 'unchanged')
    else:
        result = 'missing'

    # Ensure that the given path existed in the starting object
    blob_path = exists_in_tree(first.tree, path)

    if not blob_path:
        raise Exception('Path does not exist in start object')

    results = repo.git.log(
        '--all',
        '--follow',
        '--format=%H',
        '--diff-filter=A',
        '--',
        path,
    ).splitlines()

    assert results

    creation_commit = None
    for result in results:
        commit = repo.commit(result)
        if repo.is_ancestor(commit, first):
            creation_commit = commit

    assert creation_commit

    # If the starting point is an ancestor of the ending point, then we need to
    # find what happened to the path for each commit going forward.
    if repo.is_ancestor(first, second):
        rev_list = '{start}...{end}'.format(
            start=first.hexsha, end=second.hexsha
        )

        prev = first

        commits = repo.git.rev_list(rev_list, ancestry_path=True, reverse=True)
        commits = [repo.commit(commit) for commit in commits.splitlines()]

        for commit in commits:
            count = 0

            for diff in prev.diff(commit):
                if diff.a_path == blob_path:
                    count += 1

                    if debug:
                        print(': a : {1} :: b : {2}'.format(
                            commit.hexsha, diff.a_path, diff.b_path
			))

                    if blob_path != diff.b_path:
                        result = 'updated'
                        blob_path = diff.b_path

                    if diff.deleted_file:
                        result = 'deleted'
                        break

            if result == 'deleted':
                break

            if count > 1:
                raise Exception('found more than 1 matching diff')

            for diff in commit.diff(prev):
                if diff.renamed and diff.b_path == path:
                    print('found potential rename: ' + diff.b_path)

            prev = commit
    # If the ending point is an ancestor of the starting point, then we need to
    # find what happened to the path for each commit going backwards.
    elif repo.is_ancestor(second, first):
        # We already know that the creation commit is an ancestor of the
        # starting point, but we don't know if the creation commit is an
        # ancestor of the ending point. In this case, since we know we are in
        # a state whereby the ending point is prior to the starting point, if
        # the creation commit is also an ancestor of the ending point, then we
        # can search for changes to the path.
        if repo.is_ancestor(creation_commit, second):
            result = 'unchanged'
        # Otherwise, the file never existed at this point.
        else:
            result = 'missing'
    # If a relationship between the starting and ending objects can't be
    # determined, then there is nothing we can do and likely an issue that
    # needs manual investigation.
    else:
        result = 'unknown'

    return (blob_path, result)

if __name__ == '__main__':
    import sys

    print(resolve_path(
        git.Repo(sys.argv[1]),
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        True
    ))
