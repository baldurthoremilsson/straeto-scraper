#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
import re
import requests
import time
from collections import defaultdict
from datetime import date, timedelta
from HTMLParser import HTMLParser

from stations import station_ids, station_names
from fridagar import get_holidays


class NoTimetableException(Exception):
    pass


class HSSParser(HTMLParser):
    def __init__(self, content, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self.hss = None
        self.feed(content)

    def handle_input(self, attrs):
        if attrs['name'] == 'hss':
            self.hss = attrs['value']

    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            self.handle_input(dict(attrs))

class ContinueParser(HTMLParser):
    def __init__(self, content, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self.cont = False
        self.feed(content)

    def handle_input(self, attrs):
        if attrs['name'] == 'methodLaterTimetable'\
                and 'disabled' not in attrs.keys():
            self.cont = True

    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            self.handle_input(dict(attrs))

class TimetableParser(HTMLParser):
    def __init__(self, content, timetable, ids, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self.ids = ids
        self.in_timetable = False
        self.index = -1
        self.station_index = -1
        self.timing_point = False
        self.intermediate_stop = False
        self.event_times = False
        self.timelists = defaultdict(list)
        self.current_stop = None
        self.current_stop_type = None
        self.feed(self.unescape(content))

        for key, val in self.timelists.iteritems():
            timetable.append(val)

    def table_start(self, attrs):
        if attrs.get('class', '') == 'timetable':
            self.in_timetable = True
            self.station_index = -1

    def table_end(self):
        self.in_timetable = False

    def tr_start(self, attrs):
        self.index = -1

    def td_start(self, attrs):
        cl = attrs.get('class', '').split()
        if 'timingPoint' in cl:
            self.timing_point = True
            self.station_index += 1
        elif 'intermediateStop' in cl:
            self.intermediate_stop = True
            self.station_index += 1
        elif 'eventTimes' in cl:
            self.event_times = True
            self.index += 1

    def td_end(self):
        if self.event_times:
            self.add_time('')
            self.event_times = False

    def handle_starttag(self, tag, attrs):
        func = getattr(self, tag + '_start', None)
        if func:
            func(dict(attrs))

    def handle_endtag(self, tag):
        func = getattr(self, tag + '_end', None)
        if func:
            func()

    def handle_data(self, data):
        if not self.in_timetable:
            return
        if self.timing_point:
            self.current_stop = data.strip()
            self.current_stop_type = 'major'
            self.timing_point = False
        elif self.intermediate_stop:
            self.current_stop = data.strip()
            self.current_stop_type = 'minor'
            self.intermediate_stop = False
        elif self.event_times:
            self.add_time(data.strip())
            self.event_times = False

    def add_time(self, time):
        # Skip stops with no times.
        if len(time) is 0:
            return

        timelist = self.timelists[self.index]
        timelist.append({
            'station': self.ids[self.station_index],
            'type': self.current_stop_type,
            'time': time,
        })

class RouteNameParser(HTMLParser):
    def __init__(self, content, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self.in_timetable_name = False
        self.in_data = False
        self.route_name = None
        self.feed(self.unescape(content))

    def handle_starttag(self, tag, attrs):
        if tag != 'span':
            return
        attrs = dict(attrs)
        if not self.in_timetable_name and attrs.get('id', '') == 'search_timetableName':
            self.in_timetable_name = True
        elif self.in_timetable_name and attrs.get('class', '') == 'data':
            self.in_data = True

    def handle_data(self, data):
        if not self.in_data and not self.route_name:
            return
        match = re.match(r'\d+ -\s+(.*)', data, re.UNICODE)
        if not match:
            return
        self.route_name = match.groups()[0].encode('utf-8')
        self.in_timetable_name = False
        self.in_data = False

def data1(route_id, dt):
    return {
        'hss': get_hss(),
        'serviceNumber': route_id,
        'serviceTime': '0:00:00', #'%d:%02d:%02d' % (dt.hour, dt.minute, dt.second),
        'serviceTimeH': 0,
        'serviceTimeM': 0,
        'serviceDate': '%02d/%02d/%d' % (dt.day, dt.month, dt.year),
        'serviceDateD': dt.day,
        'serviceDateMY': '%s-%s' % (dt.year, dt.month),
        'methoddefaultMethod': 'Leita...',
    }

def data2(dir_index, response):
    return {
        'hss': get_hss(response),
        'selectedIndex': dir_index,
        'displayedStops': range(200),
        'methodnext': 'Fletta upp leiðakerfi...',
    }

def data3(response):
    return {
        'hss': get_hss(response),
        'methodCustomiseTimetable': 'Breyta sýndum biðstöðvum...',
        'currentRequestIndex': 1,
    }

def data4(response):
    return {
        'hss': get_hss(response),
        'backforward': '{SearchBean.backPage}',
        'displayedStops': ['xxxNOTASTOPxxx'] + range(100),
        'methodConfirm': 'Vista skoðaðar biðstöðvar...',
    }

def data5(response):
    return {
        'hss': get_hss(response),
        'currentRequestIndex': 1,
        'methodLaterTimetable': 'Síðar',
    }

SESSION_URL = 'http://s.is/'
HSS_URL = 'http://s.is/timetableplanner/captureServiceDetails.do'
URL1 = 'http://s.is/timetableplanner/confirmServiceLookup.do'
URL2 = 'http://s.is/timetableplanner/serviceSelect.do'
URL3 = 'http://s.is/timetableplanner/updateTimetableDetails.do'
URL4 = 'http://s.is/timetableplanner/customiseTimetable.do'
URL5 = URL3

session = requests.Session()
session.get(SESSION_URL)

def get_hss(response=None):
    if not response:
        response = session.get(HSS_URL)
    parser = HSSParser(response.text)
    return parser.hss

def save_route(schedule, route):
    print 'Saving route %d' % route
    for direction in schedule['directions']:
        print '\t%s' % direction['name']
    print
    filename = 'route-%02d.json' % route
    with open(filename, 'w') as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)

def save_names(names):
    print 'Saving station names'
    filename = 'station-names.json'
    with open(filename, 'w') as f:
        json.dump(names, f, indent=2, ensure_ascii=False)

def scrape_direction(route_id, dir_index, dt):
    dir_name = None
    stops = []

    ids = station_ids[route_id][dir_index]
    response = session.post(URL1, data=data1(route_id, dt))
    response = session.post(URL2, data=data2(dir_index, response))
    try:
        response.text.index('No Timetable Found')
        raise NoTimetableException('Route %d, direction %d, date %s' % (route_id, dir_index, str(dt)))
    except ValueError:
        pass
    response = session.post(URL3, data=data3(response))
    response = session.post(URL4, data=data4(response))
    tp = TimetableParser(response.text, stops, ids)
    dir_name = RouteNameParser(response.text).route_name
    cont = ContinueParser(response.text).cont
    while cont:
        response = session.post(URL5, data=data5(response))
        tp = TimetableParser(response.text, stops, ids)
        cont = ContinueParser(response.text).cont
    return dir_name, stops

def next_weekday(day, holidays):
    while day.weekday() in (5, 6) or day in holidays:
        day += timedelta(days=1)
    return day

def next_saturday(day, holidays):
    while day.weekday() != 5 or day in holidays:
        day += timedelta(days=1)
    return day

def next_sunday(day, holidays):
    while day.weekday() != 6 or day in holidays:
        day += timedelta(days=1)
    return day

def next_holiday(day):
    return date(day.year, 12, 31)

def get_days(day, holidays):
    return {
        'weekday': next_weekday(day, holidays),
        'saturday': next_saturday(day, holidays),
        'sunday': next_sunday(day, holidays),
        'holiday': next_holiday(day)
    }

def scrape_route(route_id, directions, days):
    schedule = {
        'id': route_id,
        'directions': []
    }
    for dir_index, stations in enumerate(directions):
        dir_schedule = {}
        direction = {
            'name': None,
            'stations': stations,
            'schedule': dir_schedule
        }
        for day_name, date in days.iteritems():
            try:
                dir_name, stops = scrape_direction(route_id, dir_index, date)
                dir_schedule[day_name] = stops
                direction['name'] = dir_name
            except NoTimetableException:
                pass
        schedule['directions'].append(direction)

    save_route(schedule, route_id)


def main():
    today = date.today()
    holidays = get_holidays(today.year)
    days = get_days(today, holidays)
    for route_id, directions in station_ids.iteritems():
        if route_id != 6: continue
        scrape_route(route_id, directions, days)
        time.sleep(10)

    save_names(station_names)

if __name__ == "__main__":
    main()
