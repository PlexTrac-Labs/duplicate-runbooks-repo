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
    payload = {"operationName":"RunbookProcedureListV2","variables":{"args":{"pagination":{"limit":100,"offset":page*100},"sort":[{"by":"shortName","order":"DESC"},{"by":"name","order":"DESC"}],"filters":[{"by":"tacticIds","value":[]},{"by":"methodologyIds","value":[]},{"by":"searchTerm","value":""}]}},"query":"query RunbookProcedureListV2($args: ListArgs!) {\n  runbookProcedureListV2(args: $args) {\n    data {\n      ...RunbookProcedureDataGridV2\n      __typename\n    }\n    meta {\n      ...ListMetaData\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment RunbookProcedureDataGridV2 on RunbookProcedureV2 {\n  id\n  name\n  shortName\n  description\n  isEditable\n  updatedAt\n  deletedAt\n  repository {\n    id\n    name\n    shortName\n    type\n    __typename\n  }\n  techniques {\n    id\n    name\n    shortName\n    methodologies {\n      name\n      shortName\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment ListMetaData on ListMeta {\n  pagination {\n    limit\n    offset\n    total\n    __typename\n  }\n  sort {\n    by\n    order\n    __typename\n  }\n  filters {\n    by\n    value\n    __typename\n  }\n  __typename\n}\n"}
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


def load_procedures_from_file(file_name):
    NUM_PROCEDURES_IN_DEFAULT_REPO = 1163
    procedures = []
    try:
        with open(file_name, 'r') as file:
            procedures = json.load(file)
    except Exception as e:
        log.exception(e)
        log.exception('Could not load procedures from file. File may have been deleted from antivirus software.\nCheck file status or rerun script without file name in config.yaml, exiting...')
        exit()

    log.debug(f'Loaded {len(procedures)} procedures from file')
    if len(procedures) != NUM_PROCEDURES_IN_DEFAULT_REPO:
        if not input.continue_anyways(f'Loaded unexpected number of procedures from file. Expected {NUM_PROCEDURES_IN_DEFAULT_REPO} but loaded {len(procedures)} procedures'):
            exit()

    return procedures


def load_procedures_from_instance() -> list:
     # load procedures from default repo
    log.info(f'Loading procedures from Plextrac instance...')
    list_procedures = []
    get_page_of_runbook_procedures(procedures=list_procedures)
    log.debug(f'total: {len(list_procedures)}')
    list_procedures = list(filter(lambda x: x['repository']['type']=="curated" and x['isEditable']==False, list_procedures))
    log.debug(f'filtered: {len(list_procedures)}')
    log.success(f'Found {len(list_procedures)} procedures from default PlexTrac Curated repository, loading...')

    procedures = []
    metrics = IterationMetrics(len(list_procedures))
    for procedure in list_procedures:
        log.info(f'Loading procedure \'{procedure["name"]}\'')
        try:
            payload = {"variables": f"{'{'}\n    \"id\": \"{procedure['id']}\"\n{'}'}","query": "query RunbookProcedureDetailV2($id: ID!) {\n  runbookProcedureV2(id: $id) {\n    id\n    name\n    description\n    shortName\n    isEditable\n    repository {\n      id\n      name\n      shortName\n      __typename\n    }\n    tags {\n      id\n      tag\n      __typename\n    }\n    executionSteps {\n      id\n      description\n      successCriteria\n      __typename\n    }\n    techniques {\n      ...RunbookProcedureDetailTechniqueV2\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment RunbookProcedureDetailTechniqueV2 on RunbookTechniqueV2 {\n  id\n  name\n  shortName\n  tactics {\n    id\n    name\n    methodologies {\n      id\n      name\n      __typename\n    }\n    __typename\n  }\n  __typename\n}"}
            response = api._runbooks._runbooks_v2._runbooksdb.procedures.runbookproceduredetailv2(auth.base_url, auth.get_auth_headers(), payload)
            if response.has_json_response:
                data = response.json['data']['runbookProcedureV2']
                data.pop("id")
                data.pop('isEditable')
                data['repositoryId'] = data['repository']['id']
                data.pop('repository')
                data['executionSteps'] = [{"description":x['description'], "successCriteria":x['successCriteria']} for x in data['executionSteps']]
                data['techniqueIds'] = [x['id'] for x in data['techniques']]
                data.pop('techniques')
                data.pop('__typename')
                #  shape of expected input
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
                data_formated['data']['repositoryId'] = data['repositoryId']
                data_formated['data']['description'] = data['description']
                data_formated['executionSteps'] = data['executionSteps']
                data_formated['techniqueIds'] = data['techniqueIds']
                data_formated['tags'] = data['tags']
                procedures.append(data_formated)
        except Exception as e:
            log.exception(e)
            log.exception(f'Could not get procedure \'{procedure["name"]}\', skipping...')
            log.info(metrics.print_iter_metrics())
            continue

        log.info(metrics.print_iter_metrics())
    log.success(f'Loaded {len(procedures)} procedures from default PlexTrac Curated repository')

    # make sure all procedures were loaded
    if len(list_procedures) != len(procedures):
        if not input.continue_anyways(f'Found {len(list_procedures)} procedures, but only loaded {len(procedures)} procedures'):
            exit()

    return procedures


def create_new_repo():
    # create new repo
    repo_name = input.prompt_user(f'Enter a \'Repository Name\' for a new repository to duplicate procedures to')
    repo_code = input.prompt_user(f'Enter a UNIQUE \'Repository ID Prefix\' for the new repository')
    repo_description = "Duplicate of the default PlexTrac Curated repository."
    repo_id = None
    try:
        payload = {"operationName":"RunbookRepositoryCreateV2","variables":{"data":{"name":repo_name,"shortName":repo_code,"description":repo_description,"type":"open"}},"query":"mutation RunbookRepositoryCreateV2($data: RunbookRepositoryInputV2!) {\n  runbookRepositoryCreateV2(input: $data) {\n    id\n    name\n    shortName\n    description\n    type\n    isEditable\n    __typename\n  }\n}\n"}
        response = api._runbooks._runbooks_v2._runbooksdb.repositories.runbookrepositorycreatev2(auth.base_url, auth.get_auth_headers(), payload)
        repo_id = response.json.get('data', {}).get('runbookRepositoryCreateV2', {}).get('id')
        log.debug(response.json)
        if repo_id == None:
            log.critical(f'Could not get id of new repository, exiting...')
            exit()
        log.success(f'Created new repository')
    except Exception as e:
        log.exception(e)
        exit() # must exit or check that repo_id gets set
    
    return repo_id


def add_procedures_to_repo(repo_id, procedures):
    # create procedures in new repo
    log.info(f'Creating procedures in new repository...')
    metrics = IterationMetrics(len(procedures))
    for procedure in procedures:
        log.info(f'Creating procedure \'{procedure["data"]["name"]}\'...')
        try:
            procedure['data']['repositoryId'] = repo_id
            payload = {"operationName":"RunbookProcedureCreateV2","variables":procedure,"query":"mutation RunbookProcedureCreateV2($data: RunbookProcedureInputV2!, $executionSteps: [RunbookProcedureExecutionStepInput!]!, $techniqueIds: [ID!], $tags: [String!]) {\n  runbookProcedureCreateV2(\n    input: $data\n    executionSteps: $executionSteps\n    techniqueIds: $techniqueIds\n    tags: $tags\n  ) {\n    ...RunbookProcedureFormDataV2\n    __typename\n  }\n}\n\nfragment RunbookProcedureFormDataV2 on RunbookProcedureV2 {\n  id\n  name\n  shortName\n  description\n  isEditable\n  repositoryId\n  executionSteps {\n    id\n    description\n    successCriteria\n    sortOrder\n    __typename\n  }\n  techniques {\n    ...RunbookProcedureFormTechniqueDataV2\n    __typename\n  }\n  tags {\n    id\n    tag\n    __typename\n  }\n  __typename\n}\n\nfragment RunbookProcedureFormTechniqueDataV2 on RunbookTechniqueV2 {\n  id\n  name\n  shortName\n  description\n  tactics {\n    id\n    name\n    shortName\n    __typename\n  }\n  methodologies {\n    id\n    name\n    shortName\n    __typename\n  }\n  __typename\n}\n"}
            response = api._runbooks._runbooks_v2._runbooksdb.procedures.runbookprocedurecreatev2(auth.base_url, auth.get_auth_headers(), payload)
            log.debug(response.json)
            log.success(f'Created procedure \'{procedure["data"]["name"]}\'')
        except Exception as e:
            log.exception(e)
            log.exception(f'Could not create procedure, skipping...')
            log.info(metrics.print_iter_metrics())
            continue
        log.info(metrics.print_iter_metrics())


if __name__ == '__main__':
    for i in settings.script_info:
        print(i)

    with open("config.yaml", 'r') as f:
        args = yaml.safe_load(f)

    auth = Auth(args)
    auth.handle_authentication()

    # try and load procedures from file
    # I queries all the procedures in the default runbooks repository and saved the data to a file
    # this saves querying the instance (which takes about 15 minutues) everytime the script is run
    # I'm not sure if the defualt repository every gets updated, if so will need to remove the JSON file and tell the script to query the instance.
    saved_repository_procedures_file_name = ""
    if args.get('json_repository_procedures') != None and args.get('json_repository_procedures') != "":
        saved_repository_procedures_file_name = args.get('json_repository_procedures')
        log.info(f'Using JSON repository procedures file path \'{saved_repository_procedures_file_name}\' from config...')

    SAVE_PROCEDURES_TO_JSON = False
    JSON_FILE_NAME = "plextrac_curated_repository_procedures.json"
    if SAVE_PROCEDURES_TO_JSON:
        log.info(f'Selected to load procedures from instance and save to JSON. Loading...')
        procedures = load_procedures_from_instance()
        with open(JSON_FILE_NAME,'w') as file:
            json.dump(procedures, file)
        log.info(f'Saved procedures to file \'{JSON_FILE_NAME}\'')
        if not input.continue_anyways(f'Procedures were saved to file, continue with import half of script?'):
            exit()
    
    if saved_repository_procedures_file_name != "":
        procedures = load_procedures_from_file(saved_repository_procedures_file_name)
        repo_id = create_new_repo()
        if input.continue_anyways(f'Load {len(procedures)} procedures into new repository'):
            add_procedures_to_repo(repo_id, procedures)
    
    if saved_repository_procedures_file_name == "":
        if not input.continue_anyways(f'Did not find a JSON file containing the default runbook repository procedures. Should the script pull these defaults from your instance (may take 5-10 minutes)'):
            exit()
        procedures = load_procedures_from_instance()
        repo_id = create_new_repo()
        if input.continue_anyways(f'Load {len(procedures)} procedures into new repository'):
            add_procedures_to_repo(repo_id, procedures)
