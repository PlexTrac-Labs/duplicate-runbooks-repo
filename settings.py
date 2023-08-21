import logging


# LOGGING
console_log_level = logging.INFO
file_log_level = logging.INFO
save_logs_to_file = False

# REQUESTS
# if the Plextrac instance is running on https without valid certs, requests will respond with cert error
# change this to false to override verification of certs
verify_ssl = True
# number of times to rety a request before throwing an error. will only throw the last error encountered if
# number of retries is exceeded. set to 0 to disable retrying requests
retries = 0

# description of script that will be print line by line when the script is run
script_info = ["====================================================================",
               "= Duplicate Default 'PlexTrac Curated' Runbooks Repository Script  =",
               "=------------------------------------------------------------------=",
               "= Use this script to create a new repository in Plextrac and load  =",
               "= in the default runbooks procedures. This allows editing of the   =",
               "= procedures in a new location that doesn't modify the defaults.   =",
               "=                                                                  =",
               "===================================================================="
            ]
