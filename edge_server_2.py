import requests
from requests.models import Response
import csv
from datetime import datetime, timedelta
import time
from typing import NamedTuple


# program opening text, details, version, etc
print("###############################################################################################################")
print("Welcome to the Connector Upgrade Status Check Script ")
print("The goal of this script is to give you visibility to the status of Cloud Connectors in your DaaS site")
print("there are some basic logic tests done on the gathered connector details.  This can become a scheduled")
print("task where any logic test returning True can raise a pager duty / on-call / etc, alert for an admin to ")
print("review and ensure you know of planned / underway upgrades to the Connectors")
print("Version 0.2, 04/20/23")
print("Written by BVB")
print("###############################################################################################################")


class EdgeServer(NamedTuple):
    fqdn: str
    connectorType: str
    location: str
    currentVersion: str
    expectedVersion: str
    currentBootstrapperVersion: str
    expectedBootStrapperVersion: str
    versionState: str
    inMaintenance: bool
    upgradeDisabled: bool
    lastContactDate: str
    id: str
    status: str
    role: str
    upgradingVersion: str
    upgradingStatus: str
    lastUpgradeDate: str
    lastUpgradeCompletedDate: str
    windowsSid: str
    failedUpgradeReason: str
    leaseEndDateTime: str

# customer environment details - for testing these are hard-coded in the script
# recommended to move API credentials to prompt at runtime or reference from secured file


# customer name
customer_name = ""

# client_id
client_id = ""

# client secret
client_secret = ""


# function to retrieve bearer token
def get_bearer_token(clientid, clientsecret):
    content_type = 'application/json'
    data = {"clientId": clientid, "clientSecret": clientsecret}
    headers = {'content-type': content_type}
    trusturl: str = "https://api-us.cloud.com/cctrustoauth2/root/tokens/clients"

    response: Response = requests.post(trusturl, json=data, headers=headers)
    if 200 <= response.status_code <= 299:
        print('API token Accepted, downloading bearer token')
    else:
        print("*********FAILED TO RETRIEVE BEARER TOKEN************")
        print("Response code: {}".format(response.status_code))
        print("please check your customer id, client id, and client secret, and try again")
        input("Press Enter to Exit")
        exit()
    return response


# send parameters to function to retrieve token
token: Response = get_bearer_token(client_id, client_secret)

# Read token from auth response and prepend necessary syntax
bearer_token = 'CwsAuth Bearer=%s' % token.json()["token"]

# store bearer token expiration - needed to check validity for large queries that take more than 60 minutes
bearer_expiration = datetime.now() + (timedelta(seconds=token.json()['expiresIn'] - 120))
print("\n")


def query_workspace_api(queryurl, bearertoken, customername):
    query_headers = {'Authorization': bearertoken, 'Citrix-CustomerId': customername}
    payload = {}
    retries = 4
    while retries > 0:
        response: Response = requests.get(queryurl, headers=query_headers, data=payload)
        if not 200 <= response.status_code <= 299:
            print("API Query failed with error:")
            print("Response code: {}".format(response.status_code))
            time.sleep(2)
            retries -= 1
            continue
        return response
    print("ERROR: Orchestration API did not return data with 4 retries, check status codes returned")
    return {}


# set up variables for looping the application detail collection
Connector_Types = ['Windows', 'Unified']

# set up empty tables for holding connector details
CC_detailsv_table = []
CC_detailsv_list = []


for z in [x['id'] for y in Connector_Types for x in query_workspace_api(
        f"https://agenthub-eastus-release-a.citrixworkspacesapi.net/{customer_name}"
        f"/EdgeServers?extendedData=true&connectorType={y}",
        bearer_token, customer_name).json()]:
    CC_detailsv_dict = query_workspace_api(
            f"https://agenthub-eastus-release-a.citrixworkspacesapi.net/{customer_name}"
            f"/EdgeServers/{z}",
            bearer_token, customer_name).json()
    CC_detailsv_list.append(EdgeServer(**CC_detailsv_dict))

CC_detailsv_table = [[CC_detail.fqdn, CC_detail.connectorType, CC_detail.location, CC_detail.currentVersion,
                      CC_detail.expectedVersion, CC_detail.currentBootstrapperVersion,
                      CC_detail.expectedBootStrapperVersion, CC_detail.versionState,
                      CC_detail.inMaintenance, CC_detail.upgradeDisabled, CC_detail.lastContactDate,
                      CC_detail.id, CC_detail.status, CC_detail.role, CC_detail.upgradingVersion,
                      CC_detail.upgradingStatus, CC_detail.lastUpgradeDate, CC_detail.lastUpgradeCompletedDate]
                     for CC_detail in CC_detailsv_list]

# now we have the full table of Connector details, we can make some logic tests to determine if an admin
# should be alerted about the state of the connectors
connstoupgrade = 0
sitemaint = False
disconnectedconns = 0

for item in CC_detailsv_list:
    # check for version disparity
    if not item.currentVersion and item.expectedVersion and item.connectorType == 'Windows':
        connstoupgrade += 1
    # check if an connector has a current maintenance lock
    if item.inMaintenance and not sitemaint:
        sitemaint = True
    # check if any connectors are reporting disconnected
    if item.status == 'Disconnected':
        disconnectedconns += 1

if disconnectedconns > 0 or connstoupgrade > 0 or sitemaint:
    print("Connectors in maintenance or require attention!")

if connstoupgrade > 0:
    print('A site upgrade is pending, ' + str(connstoupgrade) + ' connector(s) are marked for upgrade')

if sitemaint:
    print("A connector currently has a maintenance lock on the site")

if disconnectedconns > 0:
    print('There are ' + str(disconnectedconns) + ' disconnected Connectors in the site')

print("\n")
print("\n Data Collection Finished, formatting and writing out CSV")
print("\n")
# field names
fields = ['fqdn',
          'connectorType',
          'location',
          'currentVersion',
          'expectedVersion',
          'currentBootstrapperVersion',
          'expectedBootStrapperVersion',
          'versionState',
          'inMaintenance',
          'upgradeDisabled',
          'lastContactDate',
          'id',
          'status',
          'role',
          'upgradingVersion',
          'upgradingStatus',
          'lastUpgradeDate',
          'lastUpgradeCompletedDate']

with open('Connector_status.csv', 'w', newline='') as g:
    writer = csv.writer(g)
    writer.writerow(fields)
    writer.writerows(CC_detailsv_table)

print("All Done, have written a CSV to the same local directory that the EXE was run from called Monitoring Output")
print("\n")
input("Press Enter to Exit")
# home for lunch
