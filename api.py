# -*- coding: utf-8 -*-

import sqlite3
from datetime import datetime, timedelta
from time import strptime, mktime

from flask import Flask, g, request, jsonify

from fridagar import get_holidays


app = Flask(__name__)
DATABASE = 'straeto.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def get_stationlist():
    stationlist = []
    cur = get_db().execute('SELECT id, name FROM station')
    for station in cur.fetchall():
        stationlist.append({
            'id': station['id'],
            'name': station['name']
        })
    return stationlist


def get_directions(station):
    curs = get_db().execute('''
        SELECT direction.id, direction.name, direction.route_id
        FROM direction_station
        LEFT JOIN direction ON direction_station.direction_id = direction.id
        WHERE direction_station.station_id = ?
    ''', (station,))
    return curs.fetchall()


def get_weekday(day):
    if day.month == 12 and day.day == 25 or day.month == 1 and day.day == 1:
        return 'none'
    if day.month == 12 and day.day in (24, 31):
        return 'holiday'
    holidays = get_holidays(day.year)
    if day in holidays or day.weekday() == 6:
        return 'sunday'
    if day.weekday() == 5:
        return 'saturday'
    return 'weekday'


def get_stops(station, direction, time, stops):
    stoplist = []
    day = time.date()
    time_str = time.strftime('%H:%M')
    while len(stoplist) < stops:
        weekday = get_weekday(day)
        curs = get_db().execute('''
            SELECT time
            FROM stop
            WHERE station_id = :station
              AND direction_id = :direction
              AND day = :day
              AND time >= :time
            ORDER BY time
        ''', {
            'station': station,
            'direction': direction,
            'day': weekday,
            'time': time_str,
        })
        for stop in curs.fetchall():
            stoplist.append({
                'time': stop[0],
                'date': day.strftime('%Y-%m-%d'),
            })
        day += timedelta(days=1)
        time_str = '00:00'

    return stoplist[:stops]


def get_schedule(station, time, stops):
    schedule = []
    for direction in get_directions(station):
        schedule.append({
            'route': direction['route_id'],
            'name': direction['name'],
            'stops': get_stops(station, direction['id'], time, stops)
        })

    return schedule


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def api():
    stations = request.args.getlist('station')
    time = request.args.get('time', None)
    stops = request.args.get('stops', None)
    stationlist = request.args.get('stationlist', False)

    if time:
        try:
            tstruct = strptime(time, '%Y-%m-%dT%H:%M')
        except ValueError:
            return jsonify({'error': 'Invalid time value: %s' % time})
        time = datetime.fromtimestamp(mktime(tstruct))
    else:
        time = datetime.now()

    try:
        stops = int(stops) if stops else 3
    except ValueError:
        return jsonify({'error': 'Invalid stops value: %s' % stops})

    result = {station: get_schedule(station, time, stops) for station in stations}
    if stationlist == 'true':
        result['stationlist'] = get_stationlist()

    if not result.keys():
        result['about'] = 'Unofficial Strætó API by Baldur Þór Emilsson (baldur@baldur.biz), ' +\
                'pull requests welcome :)'
        result['url'] = 'https://github.com/baldurthoremilsson/straeto-scraper'
        result['example1'] = '/?stationlist=true'
        result['example2'] = '/?station=90000295&station=90000075&stops=10'
        result['example3'] = '/?station=90000295&time=2013-11-03T20:35'
        result['disclaimer'] = 'This is an unofficial API based on data that ' +\
                'has been scraped from straeto.is. No guarantee is given for the ' +\
                'correctness of the data; it is not my fault if you miss your bus. ' +\
                'The API does not know when the current schedule stops being valid ' +\
                'so any date will return the current schedule for that day of the week.'

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)

