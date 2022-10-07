#!/usr/bin/python3

import os
from git import Repo
import argparse
import json
from jira import JIRA
import re


def build_branch_name_from_jira_issue(issue_key: str, issue_title: str) -> str:
    close_brace_index = issue_title.find(']')
    normalized_issue_title = re.sub('[ ~^?*:[\\]]+', ' ', issue_title.strip())
    if close_brace_index == -1:
        return f"{issue_key.upper()}-{normalized_issue_title.replace(' ', '-').lower()}"
    return f"{issue_key.upper()}-{normalized_issue_title[close_brace_index + 1:].strip().replace(' ', '-').lower()}"


def find_project_folder_by_name(root_folder: str, project_name: str) -> list:
    result = list()
    normalized_project_name = project_name.lower()
    for folder in os.listdir(root_folder):
        # if folder contains the project name, return it
        if normalized_project_name in folder.lower():
            result.append(os.path.join(root_folder, folder))
    return result


parser = argparse.ArgumentParser(
    prog='Nova Branch Tool',
    description='Help tool to work with branches on Nova project')
parser.add_argument('-i', '--issue', required=False)
parser.add_argument('-p', '--project', required=True)
args = parser.parse_args()

# Read configuration
with open('config.json') as f:
    config = json.load(f)

# Find project folder
project_folders = find_project_folder_by_name(config['repositoryRoot'], args.project)
if len(project_folders) == 0:
    print(f"Project repository folder for {args.project} not found in {config['repositoryRoot']}")
    exit(1)
elif len(project_folders) > 1:
    print(f"Multiple project repository folders for {args.project} found in {config['repositoryRoot']}")
    exit(1)
project_folder = project_folders[0]
print(f"Project folder found: {project_folder}")
repo = Repo(project_folder)
if repo.bare:
    print(f"Project folder {project_folder} is not a git repository")
    exit(1)

# Connect to Jira
j = JIRA(config['jira']['host'], basic_auth=(config['jira']['username'], config['jira']['password']))
issue = args.issue
if issue is None:
    # Try to guess issue
    print("No issue key provided, trying to find the right issue ...")
    # Get JIRA issues assigned to user and in progress
    issues = j.search_issues(f"project = '{config['jira']['project']}' AND assignee = '{config['jira']['username']}' AND status IN ('To Do', 'In Progress') ORDER BY updated DESC, created DESC", maxResults=10)
    if len(issues) == 0:
        print("No issues found")
        exit(1)
    elif len(issues) > 1:
        print("Multiple issues found, please specify one:")
        user_input = dict()
        for i in range(len(issues)):
            print(f"{i + 1:>2}. {issues[i].key} - {issues[i].fields.summary}")
            user_input[str(i + 1)] = issues[i].key
        user_choice = input("Please select an issue (press number or 'q' for exit): ")
        if user_choice == 'q':
            exit(0)
        elif user_choice in user_input:
            issue = user_input[user_choice]
        else:
            print("Invalid choice")
            exit(1)

new_branch_name = build_branch_name_from_jira_issue(issue, j.issue(issue).fields.summary)

# Get the active branch
active_branch = repo.active_branch

if active_branch.name == 'master':
    print('You are on master branch')
else:
    print('Checking out master branch...')
    active_branch = repo.heads.master.checkout()
    print('You are on master branch')

print('Pulling master branch...')
repo.remotes.origin.pull()

print('Creating new branch...')
repo.create_head(new_branch_name)
print('New branch [{}] for jira task [{}] created'.format(new_branch_name, issue))
repo.heads[new_branch_name].checkout()