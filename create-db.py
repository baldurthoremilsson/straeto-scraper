#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import sqlite3
import json
import re


ROUTE_FILE_REGEX = re.compile(r'route-[0-9]{2}\.json')


def get_stations():
    with open('station-names.json', 'r') as f:
        return json.load(f)

def get_routes():
    for filename in os.listdir('.'):
        if not ROUTE_FILE_REGEX.match(filename):
            continue
        with open(filename, 'r') as f:
            yield json.load(f)


def create_schema(conn):
    print 'Creating schema'

    c = conn.cursor()
    c.execute('''
        CREATE TABLE station(
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE route(
            id TEXT PRIMARY KEY
        )
    ''')
    c.execute('''
        CREATE TABLE direction(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id TEXT REFERENCES route(id),
            name TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE direction_station(
            direction_id INTEGER REFERENCES direction(id),
            station_id INTEGER REFERENCES station(id),
            ordering INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE stop(
            direction_id INTEGER REFERENCES direction(id),
            station_id INTEGER REFERENCES station(id),
            day TEXT,
            time TEXT
        )
    ''')

    c.execute('CREATE INDEX stop_index ON stop(direction_id, station_id, day, time)')


def populate(conn):
    c = conn.cursor()

    print 'Populationg station table'
    for station_id, station_name in get_stations().iteritems():
        c.execute('INSERT INTO station(id, name) VALUES(?, ?)', (station_id, station_name))

    for route in get_routes():
        print 'Populating route %s' % route['id']
        c.execute('INSERT INTO route(id) VALUES(?)', (route['id'],))
        for direction in route['directions']:
            print '\tDirection %s' % direction['name']
            c.execute('INSERT INTO direction(route_id, name) VALUES(?, ?)',
                    (route['id'], direction['name']))
            c.execute('SELECT last_insert_rowid()')
            direction_id = c.fetchone()[0]
            for ordering, station_id in enumerate(direction['stations'], start=1):
                c.execute('''
                    INSERT INTO direction_station(
                        direction_id,
                        station_id,
                        ordering
                    ) VALUES(?, ?, ?)
                ''', (direction_id, station_id, ordering))
            for day, schedule in direction['schedule'].iteritems():
                for trip in schedule:
                    for stop in trip:
                        c.execute('''
                            INSERT INTO stop(
                                direction_id,
                                station_id,
                                day,
                                time
                            ) VALUES(?, ?, ?, ?)
                        ''', (direction_id, stop['station'], day, stop['time']))

    conn.commit()


def create_db(dbname):
    conn = sqlite3.connect(dbname)
    create_schema(conn)
    populate(conn)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        dbname = 'straeto.db'
    else:
        dbname = sys.argv[1]

    create_db(dbname)

