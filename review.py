#!/usr/bin/env python3
import argparse
import subprocess
import json
import os

from worker import run_jobs
from llm import review, reproduce, code_tree
from pair import get_code_tree

def get_last_commit_hashes(n, repo_path):
    """
    Get the last n commit hashes from the specified repository.
    """
    try:
        output = subprocess.check_output(
            ["git", "-C", repo_path, "rev-list", f"-n{n}", "HEAD"],
            stderr=subprocess.STDOUT
        )
        commit_hashes = output.decode("utf-8").strip().splitlines()
        return commit_hashes
    except subprocess.CalledProcessError as e:
        print("Error retrieving commit hashes:", e.output.decode("utf-8"))
        return []

def get_commit_patch(commit_hash, repo_path):

    """
    Get the patch text for a commit using git format-patch.
    """
    try:
        output = subprocess.check_output(
            ["git", "-C", repo_path, "format-patch", "-1", commit_hash, "--stdout"],
            stderr=subprocess.STDOUT
        )
        patch_text = output.decode("utf-8")
        return patch_text
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving patch for commit {commit_hash}:", e.output.decode("utf-8"))
        return ""

def build_prompt(patch_texts):
    """
    Build a prompt asking an LLM to perform a code review for the given patch texts.
    The review should be returned as JSON with keys for analysis, suggestions, and issues.
    """
    prompt = (
        "Please perform a code review for the following git patches. "
        "Return your review as JSON with keys that include your analysis, suggestions, and any issues found.\n\n"
    )
    for patch in patch_texts:
        prompt += "```\n" + patch + "\n```\n\n"
    return prompt

def review_commit(args):
    commit, patch = args
    if len(patch) > 25000:
        print(f"Skipping analysis for patch {commit} because it's too large")
        return
    analysis = review(patch)
    print(commit, analysis)

    if len(analysis):
        repro = reproduce(patch, analysis)
        print("<repro>", commit, repro)
    else:
        repro = None

    print("Writing analysis for ", commit)
    with open(f'out/{commit}.json', 'w') as f:
        json.dump({
            "commit": commit,
            "analysis": analysis,
            "repro": repro
        }, f, indent=4)

def review_commits(n, repo_path="."):
    commit_hashes = get_last_commit_hashes(n, repo_path)
    if not commit_hashes:
        print("No commits found or error accessing repository.")
        return
    
    patches = [(commit, get_commit_patch(commit, repo_path)) for commit in commit_hashes]

    run_jobs(review_commit, patches, max_workers=25, payload_arg_key_fn=lambda x: x[0])

def reproduce_commit(commit_hash, repo_path="."):
    patch = get_commit_patch(commit_hash, repo_path)

    if not patch:
        print(f"Failed to fetch patch for commit {commit_hash}")
        return
    
    # probably fine to re-run this
    issues = review(patch)

    print(issues)

    repro = reproduce(patch, issues)
    print(repro)

def analyze_tree(count, repo_path):
    trees = get_code_tree(count, repo_path)

    by_key = { tree['functionName']: tree for tree in trees }
    analysis = run_jobs(code_tree, [(key, val) for key, val in by_key.items()], max_workers=25, payload_arg_key_fn=lambda x: x[0])

    for key, analysis in analysis.items():
        if len(analysis):
            with open(f'out/{key}.json', 'w') as f:
                json.dump({
                    "tree": by_key[key],
                    "analysis": analysis,
                }, f, indent=4)

def main():
    parser = argparse.ArgumentParser(
        description="Looking for issues in a codebase"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--review", type=int, help="Review the last N commits")
    group.add_argument("--reproduce", type=str, help="Reproduce (fetch diff patch) for the specified commit hash")
    group.add_argument("--tree", type=int, help="Analyze random code trees in the repo")
    parser.add_argument("--repo", type=str, default=".", help="Path to the git repository (default: current directory)")
    args = parser.parse_args()

    if args.review is not None:
        review_commits(args.review, args.repo)
    elif args.reproduce is not None:
        reproduce_commit(args.reproduce, args.repo)
    elif args.tree is not None:
        analyze_tree(args.tree, args.repo)

if __name__ == "__main__":
    main()
