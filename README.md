This project allows you to find all the open source contributions made by a set of github users.

## How to run this project

### Requirements

* make sure to install [pixi](https://pixi.prefix.dev/latest/installation/)

### Run the scripts

There are two steps required to see what contributions a team has been up to.

#### 1. populate a team.txt file.

This can be done manually by writing out a list of all the github user names you want to check. For example:

```
$ echo "soapy1" > team.txt
```

Or, to get all the OpenTeams engineering team run the pixi task:

```
$ pixi run find-my-team
```

#### 2. collect prs.

Use the output from the previous step to collect important information about all the PRs those users have made in the past 30 days. Run the pixi task

```
$ pixi run collect-prs
```

This will output a summary of PRs by all the users, including information on how many security and cve related contributions they have made. This will also output the raw data to a file `prs.json`.

This uses [zero-shot classification](https://huggingface.co/docs/inference-providers/tasks/zero-shot-classification) to determine if a pr is a security or cve related fix based on the pr title and description.
