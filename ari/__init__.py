#
# Copyright (c) 2013, Digium, Inc.
#

"""ARI client library
"""

import ari.client

Client = client.Client


def connect(base_url, username, password):
    """Helper method for easily connecting to ARI.

    :param base_url: Base URL for Asterisk HTTP server (http://localhost:8088/)
    :param username: ARI username
    :param password: ARI password.
    :return:
    """
    return Client(base_url, auth_username=username, auth_password=password)
