import yaml
from copy import deepcopy
import json

import settings
import utils.log_handler as logger
log = logger.log
from utils.auth_handler import Auth
import utils.input_utils as input
from utils.log_handler import IterationMetrics
import api


def load_repos_from_instance() -> list:
    log.info(f'Loading Runbook Repositories from instance')
    # EXAMPLE schema of returned repositories
    # {
    #     "data": {
    #         "runbookRepositoryListV2": {
    #             "data": [
    #                 {
    #                     "id": "clacwm17b000029mqcwg1etc9",
    #                     "name": "PlexTrac Curated",
    #                     "shortName": "PlexTrac",
    #                     "description": "Community produced procedures on MITRE/CTI",
    #                     "type": "curated",
    #                     "procedures": [
    #                         {
    #                             "id": "clacwm2r1011l29mq73kdg8ja",
    #                             "__typename": "RunbookProcedureV2"
    #                         },
    #                         {
    #                             "id": "clacwm2qi011c29mqctyf2mrm",
    #                             "__typename": "RunbookProcedureV2"
    #                         }
    #                     ],
    #                     "isEditable": false,
    #                     "updatedAt": "2022-11-11T19:40:51.431Z",
    #                     "userCount": 0,
    #                     "__typename": "RunbookRepositoryV2"
    #                 }
    #             ],
    repos = []
    try:
        payload_vars = {
            "args": {
                "pagination": {
                    "limit": 999,
                    "offset": 0
                }
            }
        }
        payload = {"operationName":"RunbookRepositoryListV2","variables":payload_vars,"query":"query RunbookRepositoryListV2($args: ListArgs!) {\n   runbookRepositoryListV2(args: $args) {\n     data {\n       ...RunbookRepositoryListDataV2\n       __typename\n     }\n     meta {\n       ...ListMetaData\n       __typename\n     }\n     __typename\n   }\n }\n \n fragment RunbookRepositoryListDataV2 on RunbookRepositoryV2 {\n   id\n   name\n   shortName\n   description\n   type\n   procedures {\n     id\n     __typename\n   }\n   isEditable\n   updatedAt\n   userCount\n   __typename\n }\n \n fragment ListMetaData on ListMeta {\n   pagination {\n     limit\n     offset\n     total\n     __typename\n   }\n   sort {\n     by\n     order\n     __typename\n   }\n   filters {\n     by\n     value\n     __typename\n   }\n   __typename\n }"}
        response = api._runbooks._runbooks_v2._runbooksdb.repositories.runbookrepositorylistv2(auth.base_url, auth.get_auth_headers(), payload)
        if response.has_json_response:
            repos = response.json.get("data", {}).get("runbookRepositoryListV2", {}).get("data", [])
            repos = list(filter(lambda x:len(x["procedures"])>0, repos))
            log.success(f'Loaded {len(repos)} repository(s) from instance')
    except Exception as e:
        log.exception(e)
        exit()
    log.debug(f'got repos: {repos}')
    return repos



def get_repo_choice(repos) -> int:
    """
    Prompts the user to select from a list of runbook repositories.
    Based on subsequently called functions, this will return a valid option or exit the script.

    :param repos: List of repostories returned from the POST RunbookRepositoryListV2 endpoint
    :type repos: list[repository objects]
    :return: 0-based index of selected repo from the list provided
    :rtype: int
    """
    log.info(f'List of Runbook Repositories (repos with no procedures are not listed):')
    index = 1
    for repo in repos:
        log.info(f'{index} | Name: {repo["name"]}  |  Repo ID Prefix: {repo["shortName"]}  |  Type: {repo["type"]}  |  Num Procedures: {len(repo["procedures"])}')
        index += 1
    return input.user_list("Select a repository", "Invalid choice", len(repos)) - 1


def create_new_repo():
    # create new repo
    repo_name = input.prompt_user(f'Enter a \'Repository Name\' for a new repository to duplicate procedures to')
    repo_code = input.prompt_user(f'Enter a UNIQUE \'Repository ID Prefix\' for the new repository')
    repo_description = input.prompt_user(f'Enter a \'Description\' for the new repository')
    repo_id = None
    try:
        payload = {"operationName":"RunbookRepositoryCreateV2","variables":{"data":{"name":repo_name,"shortName":repo_code,"description":repo_description,"type":"open"}},"query":"mutation RunbookRepositoryCreateV2($data: RunbookRepositoryInputV2!) {\n  runbookRepositoryCreateV2(input: $data) {\n    id\n    name\n    shortName\n    description\n    type\n    isEditable\n    __typename\n  }\n}\n"}
        response = api._runbooks._runbooks_v2._runbooksdb.repositories.runbookrepositorycreatev2(auth.base_url, auth.get_auth_headers(), payload)
        if response.has_json_response:
            if response.json.get("errors") != None:
                log.critical(f'Could not create repo: {response.json.get("errors")[0].get("message", "No error message provided")}')
                exit()
            repo_id = response.json.get('data', {}).get('runbookRepositoryCreateV2', {}).get('id')
        if repo_id == None:
            log.critical(f'Could not get id of new repository, exiting...')
            exit()
        log.success(f'Created new repository')
    except Exception as e:
        log.exception(e)
        exit() # must exit or check that repo_id gets set
    return repo_id


def delete_repo(repo_id):
    # since the script can run into issues with loading data from the instance, this function is used to help clean up
    # and not leave artifacts of a failed execution
    log.info(f'Cleaning up unfinished duplication')
    try:
        payload = {"operationName":"RunbookRepositoryDeleteV2","variables":f"{'{'}\n    \"id\": \"{repo_id}\"\n{'}'}","query":"mutation RunbookRepositoryDeleteV2($id: ID!) {\n   runbookRepositoryDeleteV2(id: $id) {\n     id\n     deletedAt\n     __typename\n   }\n }"}
        response = api._runbooks._runbooks_v2._runbooksdb.repositories.runbookrepositorydeletev2(auth.base_url, auth.get_auth_headers(), payload)
        if not response.has_json_response or not response.json.get('data', {}).get('runbookRepositoryDeleteV2', {}).get('deletedAt') != None:
            log.exception(f'Could not delete repository')
    except Exception as e:
        log.exception(e)


def get_page_of_runbook_procedures(page: int = 0, procedures: list = [], total_procedures: int = -1) -> None:
    """
    Handles traversing pagination results to create a list of all items.

    :param page: page to start on, for all results use 0, defaults to 0
    :type page: int, optional
    :param clients: the list passed in will be added to, acts as return, defaults to [], not specifing this parameter will yield no results
    :type clients: list, optional
    :param total_clients: used for recursion to know when all pages have been gathered, defaults to -1
    :type total_clients: int, optional
    """
    # client data from response is shaped like
    # {
    #     "id": "clacwm7pe04hn29mqbu96b4n7",
    #     "name": "Plist Modification",
    #     "shortName": "T1647",
    #     "description": "Modify MacOS plist file in one of two directories\n\n\n**Supported Platforms:** macos\n\n",
    #     "isEditable": false,
    #     "updatedAt": "2022-11-11T19:40:47.618Z",
    #     "deletedAt": null,
    #     "repository": {
    #         "id": "clacwm17b000029mqcwg1etc9",
    #         "name": "PlexTrac Curated",
    #         "shortName": "PlexTrac",
    #         "type": "curated",
    #         "__typename": "RunbookRepositoryV2"
    #     },
    #     "techniques": [
    #         {
    #             "id": "clacwm6bg03ag29mq06ho26ob",
    #             "name": "Plist File Modification",
    #             "shortName": "T1647",
    #             "methodologies": [
    #                 {
    #                     "name": "Mitre ATT&CK 11.3",
    #                     "shortName": "Mitre-11.3",
    #                     "__typename": "RunbookMethodologyV2"
    #                 }
    #             ],
    #             "__typename": "RunbookTechniqueV2"
    #         }
    #     ],
    #     "__typename": "RunbookProcedureV2"
    # }
    payload = {"operationName":"RunbookProcedureListV2","variables":{"args":{"pagination":{"limit":100,"offset":page*100},"sort":[{"by":"shortName","order":"DESC"},{"by":"name","order":"DESC"}],"filters":[{"by":"tacticIds","value":[]},{"by":"methodologyIds","value":[]},{"by":"searchTerm","value":""}]}},"query":"query RunbookProcedureListV2($args: ListArgs!) {\n  runbookProcedureListV2(args: $args) {\n    data {\n      ...RunbookProcedureDataGridV2\n      __typename\n    }\n    meta {\n      ...ListMetaData\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment RunbookProcedureDataGridV2 on RunbookProcedureV2 {\n  id\n  name\n  shortName\n  description\n  isEditable\n  updatedAt\n  deletedAt\n  repository {\n    id\n    name\n    shortName\n    type\n    __typename\n  }\n  techniques {\n    id\n    name\n    shortName\n    methodologies {\n      name\n      shortName\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment ListMetaData on ListMeta {\n  pagination {\n    limit\n    offset\n    total\n    __typename\n  }\n  sort {\n    by\n    order\n    __typename\n  }\n  filters {\n    by\n    value\n    __typename\n  }\n  __typename\n}\n"}
    response = api._runbooks._runbooks_v2._runbooksdb.procedures.runbookprocedurelistv2(auth.base_url, auth.get_auth_headers(), payload)
    if response.json.get("data", {}).get("runbookProcedureListV2") == None:
        log.critical(f'Could not retrieve runbook procedures from instance. Exiting...')
        exit()
    data_in_scope = response.json.get("data", {}).get("runbookProcedureListV2", {})
    if len(data_in_scope.get("data", [])) > 0:
        procedures += deepcopy(data_in_scope['data'])
        total_procedures = data_in_scope['meta']['pagination']['total']

    if len(procedures) != total_procedures:
        return get_page_of_runbook_procedures(page+1, procedures, total_procedures)

    return None


def load_procedures_from_instance(repo) -> list:
     # load procedures from repo in param
    log.info(f'Loading procedures from Plextrac instance, this may take awhile...')
    list_procedures = []
    get_page_of_runbook_procedures(procedures=list_procedures)
    log.debug(f'total: {len(list_procedures)}')
    list_procedures = list(filter(lambda x: x['repository']['id']==repo['id'], list_procedures))
    log.debug(f'filtered: {len(list_procedures)}')
    log.success(f'Found {len(list_procedures)} procedures from \'{repo["name"]}\' repository, loading...')

    procedures = []
    metrics = IterationMetrics(len(list_procedures))
    for procedure in list_procedures:
        log.info(f'Loading procedure \'{procedure["name"]}\'')
        # shape of expected response of procedure
            # {
                # "data": {
                    # "runbookProcedureV2": {
                        # "id": "clacwm7pe04hn29mqbu96b4n7",
                        # "name": "Plist Modification",
                        # "description": "Modify MacOS plist file in one of two directories\n\n\n**Supported Platforms:** macos\n\n",
                        # "shortName": "T1647",
                        # "isEditable": false,
                        # "repository": {
                            # "id": "clacwm17b000029mqcwg1etc9",
                            # "name": "PlexTrac Curated",
                            # "shortName": "PlexTrac",
                            # "__typename": "RunbookRepositoryV2"
                        # },
                        # tags': [
                        #     {
                        #         'id': 'clkk8keob01b50zm21v6k6qgb',
                        #         'tag': 'hotdog',
                        #         '__typename': 'RunbookTag'
                        #     }
                        # ]
                        # "executionSteps": [
                            # {
                                # "id": "clacwm7pe04ho29mqds8u98xg",
                                # "description": "1. Modify a .plist in\n\n    /Library/Preferences\n\n    OR\n\n    ~/Library/Preferences\n\n2. Subsequently, follow the steps for adding and running via [Launch Agent](Persistence/Launch_Agent.md)\n",
                                # "successCriteria": null,
                                # "__typename": "RunbookProcedureStep"
                            # }
                        # ],
                        # "techniques": [
                            # {
                                # "id": "clacwm6bg03ag29mq06ho26ob",
                                # "name": "Plist File Modification",
                                # "shortName": "T1647",
                                # "tactics": [
                                    # {
                                        # "id": "clacwm5oh02mf29mqf5andaw8",
                                        # "name": "Defense Evasion",
                                        # "methodologies": [
                                            # {
                                                # "id": "clacwm5nx02m229mqci14ckrd",
                                                # "name": "Mitre ATT&CK 11.3",
                                                # "__typename": "RunbookMethodologyV2"
                                            # }
                                        # ],
                                        # "__typename": "RunbookTacticV2"
                                    # }
                                # ],
                                # "__typename": "RunbookTechniqueV2"
                            # }
                        # ],
                        # "__typename": "RunbookProcedureV2"
                    # }
                # }
            # }
        try:
            payload = {"operationName":"RunbookProcedureDetailV2","variables": f"{'{'}\n    \"id\": \"{procedure['id']}\"\n{'}'}","query": "query RunbookProcedureDetailV2($id: ID!) {\n  runbookProcedureV2(id: $id) {\n    id\n    name\n    description\n    shortName\n    isEditable\n    repository {\n      id\n      name\n      shortName\n      __typename\n    }\n    tags {\n      id\n      tag\n      __typename\n    }\n    executionSteps {\n      id\n      description\n      successCriteria\n      __typename\n    }\n    techniques {\n      ...RunbookProcedureDetailTechniqueV2\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment RunbookProcedureDetailTechniqueV2 on RunbookTechniqueV2 {\n  id\n  name\n  shortName\n  tactics {\n    id\n    name\n    methodologies {\n      id\n      name\n      __typename\n    }\n    __typename\n  }\n  __typename\n}"}
            response = api._runbooks._runbooks_v2._runbooksdb.procedures.runbookproceduredetailv2(auth.base_url, auth.get_auth_headers(), payload)
            if response.has_json_response:
                log.debug(f'JSON received from get runbookproceduredetailv2: {response.json}')
                data = response.json.get("data", {}).get("runbookProcedureV2", {})
                #  shape of required input when creating procedures
                # {
                #     "data": {
                #         "name": "Test Procedure",
                #         "shortName": "pid",
                #         "repositoryId": "clc0rr6v500540zo31c5i4cz2",
                #         "description": "<p>desc</p>"
                #     },
                #     "executionSteps": [
                #         {
                #             "description": "<p>step 1</p>",
                #             "successCriteria": "<p>did the thing</p>"
                #         }
                #     ],
                #     "techniqueIds": [
                #         "clacwm5ot02mv29mqevmb44lh"
                #     ],
                #     "tags": [
                #         "test_tag"
                #     ]
                # }
                data_formated = {}
                data_formated['data'] = {}
                data_formated['data']['name'] = data['name']
                data_formated['data']['shortName'] = data['shortName']
                data_formated['data']['description'] = data['description']
                data_formated['executionSteps'] = [{"description":x['description'], "successCriteria":x['successCriteria']} for x in data['executionSteps']]
                data_formated['techniqueIds'] = [x['id'] for x in data['techniques']]
                data_formated['tags'] = data['tags']
                data_formated['tags'] = [x['tag'] for x in data['tags']]
                log.debug(f'Formatted data to be used to create new procedure: {data_formated}')
                procedures.append(data_formated)
        except Exception as e:
            log.exception(e)
            log.exception(f'Could not load procedure \'{procedure["name"]}\', skipping...')
            log.info(metrics.print_iter_metrics())
            continue

        log.info(metrics.print_iter_metrics())
    log.success(f'Loaded {len(procedures)} procedures from \'{repo["name"]}\' repository')

    # make sure all procedures were loaded
    if len(list_procedures) != len(procedures):
        if not input.continue_anyways(f'Found {len(list_procedures)} procedures, but only loaded {len(procedures)} procedures'):
            return False

    return procedures


def add_procedures_to_repo(repo_id, procedures):
    # create procedures in new repo
    log.info(f'Creating procedures in new repository...')
    success_count = 0
    metrics = IterationMetrics(len(procedures))
    for procedure in procedures:
        log.info(f'Creating procedure \'{procedure["data"]["name"]}\'...')
        try:
            procedure['data']['repositoryId'] = repo_id
            payload = {"operationName":"RunbookProcedureCreateV2","variables":procedure,"query":"mutation RunbookProcedureCreateV2($data: RunbookProcedureInputV2!, $executionSteps: [RunbookProcedureExecutionStepInput!]!, $techniqueIds: [ID!], $tags: [String!]) {\n  runbookProcedureCreateV2(\n    input: $data\n    executionSteps: $executionSteps\n    techniqueIds: $techniqueIds\n    tags: $tags\n  ) {\n    ...RunbookProcedureFormDataV2\n    __typename\n  }\n}\n\nfragment RunbookProcedureFormDataV2 on RunbookProcedureV2 {\n  id\n  name\n  shortName\n  description\n  isEditable\n  repositoryId\n  executionSteps {\n    id\n    description\n    successCriteria\n    sortOrder\n    __typename\n  }\n  techniques {\n    ...RunbookProcedureFormTechniqueDataV2\n    __typename\n  }\n  tags {\n    id\n    tag\n    __typename\n  }\n  __typename\n}\n\nfragment RunbookProcedureFormTechniqueDataV2 on RunbookTechniqueV2 {\n  id\n  name\n  shortName\n  description\n  tactics {\n    id\n    name\n    shortName\n    __typename\n  }\n  methodologies {\n    id\n    name\n    shortName\n    __typename\n  }\n  __typename\n}\n"}
            response = api._runbooks._runbooks_v2._runbooksdb.procedures.runbookprocedurecreatev2(auth.base_url, auth.get_auth_headers(), payload)
            log.debug(f'JSON response from create procedure request: {response.json}')
            success_count += 1
            log.success(f'Created procedure \'{procedure["data"]["name"]}\'')
        except Exception as e:
            log.exception(e)
            log.exception(f'Could not create procedure, skipping...')
            log.info(metrics.print_iter_metrics())
            continue
        log.info(metrics.print_iter_metrics())

    log.success(f'Added {success_count}/{len(procedures)} procedure(s) into the new repository')



if __name__ == '__main__':
    for i in settings.script_info:
        print(i)

    with open("config.yaml", 'r') as f:
        args = yaml.safe_load(f)

    auth = Auth(args)
    auth.handle_authentication()

    # load all repos from instance
    repos = load_repos_from_instance()

    # prompt user to select a repo for duplication
    while True:
        choice = get_repo_choice(repos)
        if input.continue_anyways(f'Select \'{repos[choice]["name"]}\' to duplicate?'):
            break
    selected_repo = repos[choice]

    # prompt user to create new repo where procedures will be copied to
    repo_id = create_new_repo()

    # load procedures related to selected repo from instance
    # since this step takes the longest, all user options are selected before
    procedures = load_procedures_from_instance(selected_repo)
    if procedures == False: # user chose not continue with script execution
        delete_repo(repo_id) # delete repo that user newly created since we're exiting early and won't add procedures to it
        log.info("Exiting...")
        exit()
    if not input.continue_anyways(f'Load {len(procedures)} procedures into new repository'):
        delete_repo(repo_id) # delete repo that user newly created since we're exiting early and won't add procedures to it
        log.info("Exiting...")
        exit()
    add_procedures_to_repo(repo_id, procedures)
