"""CI must test the combined source without relabelling it as release evidence."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ci_checkout',ROOT/'scripts/verify-ci-checkout.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
BASE='a'*40;HEAD='b'*40;PREVIEW='c'*40


class CICheckout(unittest.TestCase):
    def env(self,event='pull_request'):
        return {'GITHUB_ACTIONS':'true','GITHUB_WORKSPACE':str(ROOT),'GITHUB_SHA':PREVIEW,
            'GITHUB_EVENT_NAME':event,'CI_PR_BASE_SHA':BASE,'CI_PR_HEAD_SHA':HEAD}

    def test_head_only_checkout_is_changed_to_the_exact_existing_preview(self):
        replies=[HEAD,'','','',PREVIEW,f'tree {"d"*40}\nparent {BASE}\nparent {HEAD}\n']
        with patch.object(module,'git',side_effect=replies) as git:
            result=module.verify(self.env())
        self.assertEqual(git.call_args_list[2].args,('fetch','--no-tags','--depth=2','origin',PREVIEW))
        self.assertEqual(git.call_args_list[3].args,('checkout','--detach',PREVIEW))
        self.assertEqual(result['tested_commit'],PREVIEW)
        self.assertTrue(result['checkout_changed']);self.assertFalse(result['release_admissible'])

    def test_existing_correct_preview_needs_no_checkout(self):
        with patch.object(module,'git',side_effect=[PREVIEW,PREVIEW,f'parent {BASE}\nparent {HEAD}']) as git:
            result=module.verify(self.env())
        self.assertFalse(result['checkout_changed']);self.assertEqual(git.call_count,3)

    def test_dirty_checkout_wrong_head_or_wrong_parents_fail_closed(self):
        for replies in [[HEAD,' M file'],['e'*40],[PREVIEW,PREVIEW,f'parent {HEAD}\nparent {BASE}']]:
            with patch.object(module,'git',side_effect=replies):
                with self.assertRaises(ValueError):module.verify(self.env())

    def test_non_pr_runs_never_switch_sources(self):
        with patch.object(module,'git',side_effect=[HEAD]):
            with self.assertRaises(ValueError):module.verify(self.env('push'))
        with patch.object(module,'git',side_effect=[PREVIEW,PREVIEW]):
            result=module.verify(self.env('push'))
        self.assertEqual(result['source_kind'],'commit');self.assertIsNone(result['release_admissible'])

    def test_non_actions_workspace_and_untrusted_sha_are_rejected_before_git(self):
        for change in [{'GITHUB_ACTIONS':'false'},{'GITHUB_WORKSPACE':'/tmp'},{'GITHUB_SHA':'refs/heads/main'}]:
            with patch.object(module,'git') as git:
                with self.assertRaises(ValueError):module.verify({**self.env(),**change})
                git.assert_not_called()


if __name__=='__main__':unittest.main()
