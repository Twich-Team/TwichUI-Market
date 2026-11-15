"""Verify CI's actual tested commit; PR previews are never release approvals.

Some shared workflows check out the PR head while running the combined workflow
file. Switch only an untouched Actions PR checkout to GitHub's existing preview
commit. This fetches/checks out a commit; it never merges or updates a branch.
"""
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()


def sha(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{40}',value):
        raise ValueError('CI source must be an exact commit SHA')
    return value


def verify(environment=None):
    env=os.environ if environment is None else environment
    if env.get('GITHUB_ACTIONS')!='true' or Path(env.get('GITHUB_WORKSPACE','')).resolve()!=ROOT.resolve():
        raise ValueError('Source preparation is restricted to this GitHub Actions workspace')
    expected=sha(env.get('GITHUB_SHA'))
    event=env.get('GITHUB_EVENT_NAME')
    actual=sha(git('rev-parse','HEAD'))
    preview=event=='pull_request'
    head=sha(env.get('CI_PR_HEAD_SHA')) if preview else None
    base=sha(env.get('CI_PR_BASE_SHA')) if preview else None
    changed=False
    if actual!=expected:
        if not preview or actual!=head:
            raise ValueError('Unexpected initial CI checkout; refusing to change it')
        if git('status','--porcelain'):
            raise ValueError('CI source preparation requires a clean checkout')
        git('fetch','--no-tags','--depth=2','origin',expected)
        git('checkout','--detach',expected)
        changed=True
    actual=sha(git('rev-parse','HEAD'))
    if actual!=expected:raise ValueError('CI tested commit differs from the event commit')
    if preview:
        parents=[line.split()[1] for line in git('cat-file','-p','HEAD').splitlines() if line.startswith('parent ')]
        if parents!=[base,head]:raise ValueError('PR preview parents differ from the event base/head')
    return {'event':event,'tested_commit':actual,'source_kind':'pull_request_preview' if preview else 'commit',
        'pr_base_commit':base,'pr_head_commit':head,'checkout_changed':changed,
        'release_admissible':False if preview else None,
        'notice':'PR preview validation is integration evidence only. Release/deployment require separate exact-commit CI and owner authorization.'}


if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
