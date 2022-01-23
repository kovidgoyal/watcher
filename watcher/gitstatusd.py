#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import atexit
import os
import subprocess
import threading

# gitstatud the exe comes from https://github.com/romkatv/gitstatus
exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gitstatusd')


class GSD:

    def __init__(self):
        self.process = subprocess.Popen(
            [exe, '--num-threads=' + str(2 * len(os.sched_getaffinity(0)))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        atexit.register(self.terminate)
        self.request_id = 0
        self.lock = threading.Lock()

    def terminate(self):
        if self.process.returncode is None:
            self.process.terminate()
            if self.process.wait(0.1) is None:
                self.process.kill()
                self.process.wait()
    __del__ = terminate

    def __call__(self, path):
        with self.lock:
            self.request_id += 1
            rq = f'{self.request_id}\x1f{path}\x1e'
            self.process.stdin.write(rq.encode('utf-8'))
            self.process.stdin.flush()
            resp = b''
            while b'\x1e' not in resp:
                resp += os.read(self.process.stdout.fileno(), 8192)
            fields = resp.rstrip(b'\x1e').decode('utf-8', 'replace').split('\x1f')
            if fields[0] != str(self.request_id):
                raise ValueError(f'Got invalid response id: {fields[0]}')
            if fields[1] == '0':
                raise NotADirectoryError(f'{path} is not a git repository')
            return {
                'workdir': fields[2],
                'HEAD': fields[3],
                'branch_name': fields[4],
                'upstream_branch_name': fields[5],
                'remote_branch_name': fields[6],
                'remote_url': fields[7],
                'repo_state': fields[8],
                'num_files_in_index': int(fields[9] or 0),
                'num_staged_changes': int(fields[10] or 0),
                'num_unstaged_changes': int(fields[11] or 0),
                'num_conflicted_changes': int(fields[12] or 0),
                'num_untracked_files': int(fields[13] or 0),
                'num_commits_ahead_of_upstream': int(fields[14] or 0),
                'num_commits_behind_upstream': int(fields[15] or 0),
                'num_stashes': int(fields[16] or 0),
                'last_tag_pointing_to_HEAD': fields[17],
                'num_unstaged_deleted_files': int(fields[18] or 0),
                'num_staged_new_files': int(fields[19] or 0),
                'num_staged_deleted_files': int(fields[20] or 0),
                'push_remote_name': fields[21],
                'push_remote_url': fields[22],
                'num_commits_ahead_of_push': int(fields[23] or 0),
                'num_commits_behind_of_push': int(fields[24] or 0),
                'num_files_with_skip_worktree_set': int(fields[25] or 0),
                'num_files_with_assume_unchanged_set': int(fields[26] or 0),
                'encoding_of_head': fields[27] or 'utf-8',
                'head_first_para': fields[28],
            }


def test():
    g = GSD()
    data = g(os.getcwd())
    from pprint import pprint
    pprint(data)


if __name__ == '__main__':
    test()
