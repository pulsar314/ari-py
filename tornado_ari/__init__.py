#
# Copyright (c) 2013, Digium, Inc.
#

"""ARI client library
"""

from tornado.httpclient import AsyncHTTPClient
import tornado_ari.client

Client = client.Client


def connect(base_url, username, password):
    """Helper method for easily connecting to ARI.

    :param base_url: Base URL for Asterisk HTTP server (http://localhost:8088/)
    :param username: ARI username
    :param password: ARI password.
    :return:
    """
    http_client = AsyncHTTPClient(
        defaults=dict(
            auth_username=username,
            auth_password=password,
            allow_nonstandard_methods=True,
        )
    )
    return Client(base_url, http_client=http_client)
