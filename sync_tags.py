import requests
import os
import re

REPO_A_OWNER = 'tailscale'
REPO_A_NAME = 'tailscale'
REPO_B_OWNER = 'betdev-cloud'
REPO_B_NAME = 'tailscale'

headers = {
  'Authorization': f'token {os.getenv("GITHUB_TOKEN")}',
  'Accept': 'application/vnd.github.v3+json',
}

response_a = requests.get(f'https://api.github.com/repos/{REPO_A_OWNER}/{REPO_A_NAME}/tags')
tags_a = response_a.json()[:10]

release_tags_a = [tag for tag in tags_a if not re.search(r'-pre', tag['name'])]

response_b = requests.get(f'https://api.github.com/repos/{REPO_B_OWNER}/{REPO_B_NAME}/tags', headers=headers)
tags_b = response_b.json()[:10]

release_tags_a_names = {tag['name'] for tag in release_tags_a}
tags_b_names = {tag['name'] for tag in tags_b}

new_tags = release_tags_a_names - tags_b_names

if new_tags:
  latest_tag = sorted(new_tags)[-1]
  print(f'Latest tag: {latest_tag}')

  response_main = requests.get(f'https://api.github.com/repos/{REPO_B_OWNER}/{REPO_B_NAME}/git/refs/heads/main', headers=headers)
  if response_main.status_code == 200:
    main_sha = response_main.json()['object']['sha']
    create_tag_url = f'https://api.github.com/repos/{REPO_B_OWNER}/{REPO_B_NAME}/git/refs'
    tag_data = {
      'ref': f'refs/tags/{latest_tag}',
      'sha': main_sha
    }
    print(f'Creating tag {latest_tag} with sha {main_sha}')
    response_create_tag = requests.post(create_tag_url, json=tag_data, headers=headers)
    if response_create_tag.status_code == 201:
      print(f'Successfully created tag {latest_tag}')

      workflow_dispatch_url = f'https://api.github.com/repos/{REPO_B_OWNER}/{REPO_B_NAME}/actions/workflows/build.yml/dispatches'
      dispatch_data = {
        "ref": "main",
        "inputs": {
          "version": latest_tag
        }
      }
      response_dispatch = requests.post(workflow_dispatch_url, json=dispatch_data, headers=headers)
      if response_dispatch.status_code == 204:
        print(f'Successfully triggered build for tag {latest_tag}')
      else:
        print(f'Failed to trigger build: {response_dispatch.status_code}')
        print(response_dispatch.json())
    else:
      print(f'Failed to create tag: {response_create_tag.status_code}')
      print(response_create_tag.json())
  else:
    print('Failed to get main branch sha')
else:
  print('No new tags found')
