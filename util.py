import collections

import whatthepatch


def load_patch(patch_text):
    patch = [diff for diff in whatthepatch.parse_patch(patch_text)]

    status_header = collections.namedtuple(
        'header',
        whatthepatch.patch.header._fields + ('path', 'status')
    )

    patch = [
        diff._replace(header=status_header(
            index_path=diff.header.index_path,
            old_path=diff.header.old_path,
            old_version=diff.header.old_version,
            new_path=diff.header.new_path,
            new_version=diff.header.new_version,
            path=diff.header.new_path,
            status='unchanged'
        ))
    for diff in patch]

    return patch
