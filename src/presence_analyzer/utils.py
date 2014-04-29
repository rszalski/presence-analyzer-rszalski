# -*- coding: utf-8 -*-
"""
Helper functions used in views.
"""

import csv
from collections import defaultdict
from json import dumps
from functools import wraps
from datetime import datetime
import threading
import time

from flask import Response
from lxml import etree

from presence_analyzer.main import app

import logging
log = logging.getLogger(__name__)  # pylint: disable=C0103


def jsonify(function):
    """
    Creates a response with the JSON representation of wrapped function result.
    """
    @wraps(function)
    def inner(*args, **kwargs):
        return Response(dumps(function(*args, **kwargs)),
                        mimetype='application/json')
    return inner


def cache(cache_time):
    """
    Caches the data for ``cache_time`` seconds.
    """
    __cache = defaultdict(dict)
    __cache_lock = threading.Lock()

    def is_cache_expired(func_name):
        return (time.time() - __cache[func_name]['created']) > cache_time

    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            func_name = repr(func) + repr(args) + repr(kwargs)

            with __cache_lock:
                if func_name not in __cache or is_cache_expired(func_name):
                    __cache[func_name]['data'] = func(*args, **kwargs)
                    __cache[func_name]['created'] = time.time()

                return __cache[func_name]['data']
        return inner
    return decorator


@cache(600)
def get_data():
    """
    Extracts presence data from CSV file and groups it by user_id.

    It creates structure like this:
    data = {
        'user_id': {
            datetime.date(2013, 10, 1): {
                'start': datetime.time(9, 0, 0),
                'end': datetime.time(17, 30, 0),
            },
            datetime.date(2013, 10, 2): {
                'start': datetime.time(8, 30, 0),
                'end': datetime.time(16, 45, 0),
            },
        }
    }
    """
    data = {}
    with open(app.config['DATA_CSV'], 'r') as csvfile:
        presence_reader = csv.reader(csvfile, delimiter=',')
        for i, row in enumerate(presence_reader):
            if len(row) != 4:
                # ignore header and footer lines
                continue

            try:
                user_id = int(row[0])
                date = datetime.strptime(row[1], '%Y-%m-%d').date()
                start = datetime.strptime(row[2], '%H:%M:%S').time()
                end = datetime.strptime(row[3], '%H:%M:%S').time()
            except (ValueError, TypeError):
                log.debug('Problem with line %d: ', i, exc_info=True)

            data.setdefault(user_id, {})[date] = {'start': start, 'end': end}

    return data


def parse_users_xml():
    """
    Parses the XML file with users data.

    Returns:

    users = [
        {
            'user_id': '<id>',
            'name': '<name>',
            'avatar': '<avatar_path>',
        },
        ...
    ]
    """
    users_xml = app.config['USERS_XML']

    with open(users_xml, 'r') as xmlfile:
        users = etree.parse(xmlfile).find('users')

    users_list = [
        {
            'user_id': int(user.get('id')),
            'name': user.find('name').text,
            'avatar': user.find('avatar').text,
        }
        for user in users
    ]

    return users_list


def get_server_addr_xml():
    """
    Returns a dict with adress and protocol of server
    where avatars are stored.
    """
    users_xml = app.config['USERS_XML']

    with open(users_xml, 'r') as xmlfile:
        server = etree.parse(xmlfile).find('server')

    config = {
        'host': server.find('host').text,
        'protocol': server.find('protocol').text,
        'avatar_path': '/api/images/users/',
    }
    return config


def group_by_weekday(items):
    """
    Groups presence entries by weekday.
    """
    result = {i: [] for i in range(7)}
    for date in items:
        start = items[date]['start']
        end = items[date]['end']
        result[date.weekday()].append(interval(start, end))
    return result


def group_by_weekday_start_end(items):
    """
    Groups start and end presence entries by weekday.
    """
    result = {i: defaultdict(list) for i in range(7)}

    for date in items:
        start = items[date]['start']
        end = items[date]['end']
        result[date.weekday()]['start'].append(seconds_since_midnight(start))
        result[date.weekday()]['end'].append(seconds_since_midnight(end))

    return result


def seconds_since_midnight(time):   # pylint: disable=W0621
    """
    Calculates amount of seconds since midnight.
    """
    return time.hour * 3600 + time.minute * 60 + time.second


def interval(start, end):
    """
    Calculates inverval in seconds between two datetime.time objects.
    """
    return seconds_since_midnight(end) - seconds_since_midnight(start)


def mean(items):
    """
    Calculates arithmetic mean. Returns zero for empty lists.
    """
    return float(sum(items)) / len(items) if len(items) > 0 else 0
