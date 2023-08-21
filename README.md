# duplicate-runbooks-repo
The blank instance of Plextrac contains the default runbooks repository PlexTrac Curated. This repo contains 1163 procedures from the MITRE Attack 9.0 and 11.3 frameworks. This repo is un-editable and you cannot copy or move procedures to different repositories.

This script will create a second repo mirroring the default where you can add, remove, or edit the procedures.

The procedure information has been added to an accompanying JSON file. This file will probably get flagged by antivirus software and quarantined. Without this file, the script takes an extra ~10 minutes to run to get the information from the default repo in Plextrac before it can make the duplicate repo.

# Requirements
- [Python 3+](https://www.python.org/downloads/)
- [pip](https://pip.pypa.io/en/stable/installation/)
- [pipenv](https://pipenv.pypa.io/en/latest/install/)

# Installing
After installing Python, pip, and pipenv, run the following commands to setup the Python virtual environment.
```bash
git clone this_repo
cd path/to/cloned/repo
pipenv install
```

# Setup
After setting up the Python environment the script will run in, you will need to setup a few things to configure the script before running.

## Credentials
In the `config.yaml` file you should add the full URL to your instance of Plextrac.

The config also can store your username and password. Plextrac authentication lasts for 15 mins before requiring you to re-authenticate. The script is set up to do this automatically through the authentication handler. If these 3 values are set in the config, and MFA is not enabled for the user, the script will take those values and authenticate automatically, both initially and every 15 mins. If any value is not saved in the config, you will be prompted when the script is run and during re-authentication.

# Usage
After setting everything up you can run the script with the following command. You should run the command from the folder where you cloned the repo.
```bash
pipenv run python main.py
```
You can also add values to the `config.yaml` file to simplify providing the script with custom parameters needed to run.

## Required Information
The following values can either be added to the `config.yaml` file or entered when prompted for when the script is run.
- PlexTrac Top Level Domain e.g. https://yourapp.plextrac.com
- Username
- Password

## Script Execution Flow
- Authenticates to your instance of Plextrac
- Loads procedure information from JSON file or gets procedures from the default repo in the instance if the file is missing
- Prompts user to enter info to create new runbook repository
- Creates new repo and imports all procedures

Note: This will only import procedures into a new repository, not an existing one.
