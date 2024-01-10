#!/usr/bin/env python3
import cloudgenix
import argparse
from cloudgenix import jd, jd_detailed, jdout
import yaml
import cloudgenix_settings
import sys
import logging
import ipcalc
import ipaddress
import os
import datetime
import sys
import csv


# Global Vars
TIME_BETWEEN_API_UPDATES = 60       # seconds
REFRESH_LOGIN_TOKEN_INTERVAL = 7    # hours
SDK_VERSION = cloudgenix.version
SCRIPT_NAME = 'CloudGenix: DHCP Clone'
SCRIPT_VERSION = "1"

# Set NON-SYSLOG logging to use function name
logger = logging.getLogger(__name__)

####################################################################
# Read cloudgenix_settings file for auth token or username/password
####################################################################

sys.path.append(os.getcwd())
try:
    from cloudgenix_settings import CLOUDGENIX_AUTH_TOKEN

except ImportError:
    # Get AUTH_TOKEN/X_AUTH_TOKEN from env variable, if it exists. X_AUTH_TOKEN takes priority.
    if "X_AUTH_TOKEN" in os.environ:
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
    elif "AUTH_TOKEN" in os.environ:
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
    else:
        # not set
        CLOUDGENIX_AUTH_TOKEN = None

def clone_dhcp(cgx, source_site, destination_site): 
    dhcp_list = []
    source_site_id = None
    destination_site_id = None
    for site in cgx.get.sites().cgx_content['items']:
        if site["name"] == source_site:
            source_site_id = site["id"]
        elif site["name"] == destination_site:
            destination_site_id = site["id"]
    
    
    if not source_site_id:
        print("Unable to find source branch site " + source_site)
    if not destination_site_id:
        print("Unable to find destination branch site " + destination_site)
        
    for scope_source in cgx.get.dhcpservers(site_id=source_site_id).cgx_content['items']:
        found = False
        for scope_destination in cgx.get.dhcpservers(site_id=destination_site_id).cgx_content['items']:
            if scope_source["subnet"] == scope_destination["subnet"]:
                found = True
        
        if found:
            print("DHCP Subnet " + scope_source["subnet"] + " is already configured on " + destination_site)
        else:
            scope_source.pop("id")
            scope_source.pop("_etag")
            scope_source.pop("_schema")
            scope_source.pop("_created_on_utc")
            scope_source.pop("_updated_on_utc")
            scope_source.pop("_debug")
            scope_source.pop("_info")
            scope_source.pop("_warning")
            scope_source.pop("_error")
            
            resp = cgx.post.dhcpservers(site_id=destination_site_id, data = scope_source)
            if not resp:
                print("--ERROR creating DHCP on " + destination_site + " subnet " + scope_source["subnet"])
                print(str(jdout(resp)))
            else:
                print("--CREATING DHCP on " + destination_site + " subnet " + scope_source["subnet"])

    return
                                 
def go():
    ############################################################################
    # Begin Script, parse arguments.
    ############################################################################

    # Parse arguments
    parser = argparse.ArgumentParser(description="{0}.".format(SCRIPT_NAME))

    # Allow Controller modification and debug level sets.
    config_group = parser.add_argument_group('Name', 'These options change how the configuration is loaded.')
    config_group.add_argument("--source_name", "-S", help="Source Site Name", required=True, default=None)
    config_group.add_argument("--destination_name", "-D", help="Destination Site Name", required=True, default=None)
    
    controller_group = parser.add_argument_group('API', 'These options change how this program connects to the API.')
    controller_group.add_argument("--controller", "-C",
                                  help="Controller URI, ex. "
                                       "Alpha: https://api-alpha.elcapitan.cloudgenix.com"
                                       "C-Prod: https://api.elcapitan.cloudgenix.com",
                                  default=None)
    controller_group.add_argument("--insecure", "-I", help="Disable SSL certificate and hostname verification",
                                  dest='verify', action='store_false', default=True)
    login_group = parser.add_argument_group('Login', 'These options allow skipping of interactive login')
    login_group.add_argument("--email", "-E", help="Use this email as User Name instead of prompting",
                             default=None)
    login_group.add_argument("--pass", "-PW", help="Use this Password instead of prompting",
                             default=None)
                             
    args = vars(parser.parse_args())
    
    ############################################################################
    # Instantiate API
    ############################################################################
    cgx_session = cloudgenix.API(controller=args["controller"], ssl_verify=args["verify"])


    ##
    # ##########################################################################
    # Draw Interactive login banner, run interactive login including args above.
    ############################################################################
    print("{0} v{1} ({2})\n".format(SCRIPT_NAME, SCRIPT_VERSION, cgx_session.controller))

    # login logic. Use cmdline if set, use AUTH_TOKEN next, finally user/pass from config file, then prompt.
    # check for token
    if CLOUDGENIX_AUTH_TOKEN and not args["email"] and not args["pass"]:
        cgx_session.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if cgx_session.tenant_id is None:
            print("AUTH_TOKEN login failure, please check token.")
            sys.exit()

    else:
        while cgx_session.tenant_id is None:
            cgx_session.interactive.login(user_email, user_password)
            # clear after one failed login, force relogin.
            if not cgx_session.tenant_id:
                user_email = None
                user_password = None

    ############################################################################
    # End Login handling, begin script..
    ############################################################################

    # get time now.
    curtime_str = datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')

    # create file-system friendly tenant str.
    tenant_str = "".join(x for x in cgx_session.tenant_name if x.isalnum()).lower()
    cgx = cgx_session
    
    source_site = args["source_name"]
    destination_site = args["destination_name"]
    
    clone_dhcp(cgx, source_site, destination_site) 
    # end of script, run logout to clear session.
    print("End of script. Logout!")
    cgx_session.get.logout()

if __name__ == "__main__":
    go()