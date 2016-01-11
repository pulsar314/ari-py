#
# Copyright (c) 2013, Digium, Inc.
#

"""ARI client library.
"""

import json
import urlparse
from collections import defaultdict
from tornado.ioloop import IOLoop
from tornado.gen import coroutine
from tornado.concurrent import TracebackFuture
from tornado.log import app_log as log
import tornado_swagger.client

from .model import Repository, CLASS_MAP


class Client(object):
    """ARI Client object.

    :param base_url: Base URL for accessing Asterisk.
    :param http_client: HTTP client interface.
    """

    def __init__(self, base_url, io_loop=None, http_client=None):
        url = urlparse.urljoin(base_url, 'ari/api-docs/resources.json')
        if io_loop is None:
            io_loop = IOLoop.current()
        self.io_loop = io_loop

        self.swagger = tornado_swagger.client.SwaggerClient(
                url,
                io_loop=io_loop,
                http_client=http_client
        )

        self.repositories = {
            name: Repository(self, name, api)
            for (name, api) in self.swagger.resources.items()}

        # Extract models out of the events resource
        events = [api['api_declaration']
                  for api in self.swagger.api_docs['apis']
                  if api['name'] == 'events']
        if events:
            self.event_models = events[0]['models']
        else:
            self.event_models = dict()

        self.websockets = set()
        self.event_listeners = defaultdict(list)

    def __getattr__(self, item):
        """Exposes repositories as fields of the client.

        :param item: Field name
        """
        repo = self.get_repo(item)
        if not repo:
            raise AttributeError(
                    '"{0}" object has no attribute "{1}"'.format(self, item))
        return repo

    def close(self):
        """Close this ARI client.

        This method will close any currently open WebSockets, and close the
        underlying Swaggerclient.
        """
        for ws in self.websockets:
            ws.close()
        self.swagger.close()

    def get_repo(self, name):
        """Get a specific repo by name.

        :param name: Name of the repo to get
        :return: Repository, or None if not found.
        :rtype:  ari.model.Repository
        """
        return self.repositories.get(name)

    @coroutine
    def __run(self, ws):
        """Receives message from a WebSocket, sends them to the client's
        listeners.
        """
        while True:
            msg_str = yield ws.read_message()
            if msg_str is None:
                break
            try:
                msg_json = json.loads(msg_str)
            except (TypeError, ValueError):
                log.error('Invalid event: {0}'.format(msg_str))
                continue
            if not isinstance(msg_json, dict) or 'type' not in msg_json:
                log.error('Invalid event: {0}'.format(msg_str))
                continue

            event_type = msg_json['type']
            listeners = self.event_listeners.get(event_type)
            if listeners:
                # Extract objects from the event
                event_model = self.event_models.get(event_type)
                if not event_model:
                    log.warning('Cannot find model "{0}" for received event. '
                                'Pass raw event.'.format(event_type))
                    event = msg_json
                else:
                    event = dict()
                    properties = event_model['properties']
                    for field, value in msg_json.items():
                        if field in properties:
                            type_ = properties[field]['type']
                            if type_ in CLASS_MAP:
                                value = CLASS_MAP[type_](self, value)
                        event[field] = value

                # Set a result of pending futures
                for listener in listeners:
                    future, event_filter = listener
                    if future.done():
                        listeners.remove(listener)
                        continue

                    if event_filter is None or event_filter(event):
                            future.set_result(event)
                            listeners.remove(listener)

    @coroutine
    def run(self, apps):
        """Connect to the WebSocket and begin processing messages.

        This method will block until all messages have been received from the
        WebSocket, or until this client has been closed.

        :param apps: Application (or list of applications) to connect for
        :type  apps: str or list of str
        """
        if isinstance(apps, list):
            apps = ','.join(apps)
        ws = yield self.swagger.events.eventWebsocket(app=apps)
        self.websockets.add(ws)
        yield self.__run(ws)

    def on_event(self, event_type, event_filter=None):
        """Register listener for events with given type.

        :param event_type: String name of the event to register for.
        :param event_filter: Function to filter event objects.
        :type  event_filter: (dict) -> bool
        :rtype: tornado.concurrent.Future
        """
        if event_type not in self.event_models:
            raise ValueError('Cannot find event model "{0}"'.format(event_type))
        future = TracebackFuture()
        self.event_listeners[event_type].append((future, event_filter))
        return future
