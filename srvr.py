#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import re
import json

route_regex = re.compile(r'route-(\d+).json')


routes = {}

with open('station-names.json', 'r') as f:
    station_names = json.load(f)


class Station(object):
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.stops = []


def get_route(route_id):
    global routes
    if not routes.has_key(route_id):
        try:
            filename = 'route-%s.json' % route_id
            with open(filename, 'r') as f:
                routes[route_id] = json.load(f)
        except:
            return None
    return routes[route_id]


def get_list():
    routes = []
    for filename in os.listdir('.'):
        m = route_regex.match(filename)
        if m:
            routes.append(m.groups()[0])
    routes.sort()

    data = '<h1>Routes</h1>'
    data += '<br>'.join('<a href={id}>{name}</a>'.format(id=route, name=int(route)) for route in routes)
    return data

def get_table(path):
    global station_names
    route_info = get_route(path[1:])
    if not route_info:
        return None

    data = ['<h1>Route %d</h1>' % int(path[1:])]

    for direction in route_info['directions']:
        data.append('<h2>%s</h2>' % direction['name'])
        for day, schedule in direction['schedule'].iteritems():
            stations = [Station(id, station_names[str(id)]) for id in direction['stations']]
            data.append('<h3>%s</h3>' % day)
            for way in schedule:
                for index, stop in enumerate(way):
                    stations[index].stops.append(stop['time'])
            data.append('<table border=1 style="border-collapse: collapse">')
            for station in stations:
                data.append('<tr><th>%s</th>' % station.name)
                data.extend('<td>%s</td>' % time for time in station.stops)
                data.append('</tr>')
            data.append('</table>')

    return ''.join(data)


def app(environ, start_response):
    status_code = '200 OK'
    if environ['PATH_INFO'] == '/':
        data = get_list()
    else:
        data = get_table(environ['PATH_INFO'])

    if not data:
        status_code = '404 Not Found'
        data = '<h1>404 - Page not found</h1>Try the <a href=/>frontpage</a>'

    data = data.encode('utf-8')
    start_response(status_code, [
        ('Content-Type', 'text/html; charset=utf-8'),
        ('Content-Length', str(len(data))),
    ])
    return iter([data])

