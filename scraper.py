#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
import requests
import time
from collections import defaultdict
from datetime import date, timedelta
from HTMLParser import HTMLParser

ALL_DAYS = ['weekday', 'saturday', 'sunday']
ALL_BUT_SUNDAY = ['weekday', 'saturday']
WEEKDAYS = ['weekday']

ROUTES = {
    1: { 'directions': 2, 'days': ALL_DAYS },
    2: { 'directions': 2, 'days': ALL_DAYS },
    3: { 'directions': 2, 'days': ALL_DAYS },
    4: { 'directions': 2, 'days': ALL_DAYS },
    5: { 'directions': 2, 'days': ALL_DAYS },
    6: { 'directions': 2, 'days': ALL_DAYS },

    11: { 'directions': 2, 'days': ALL_DAYS },
    12: { 'directions': 2, 'days': ALL_DAYS },
    13: { 'directions': 2, 'days': ALL_DAYS },
    14: { 'directions': 2, 'days': ALL_DAYS },
    15: { 'directions': 2, 'days': ALL_DAYS },
    17: { 'directions': 2, 'days': ALL_BUT_SUNDAY },
    18: { 'directions': 2, 'days': ALL_DAYS },
    19: { 'directions': 2, 'days': ALL_DAYS },

    21: { 'directions': 2, 'days': ALL_BUT_SUNDAY },
    22: { 'directions': 2, 'days': WEEKDAYS },
    23: { 'directions': 1, 'days': ALL_DAYS },
    24: { 'directions': 2, 'days': ALL_DAYS },
    26: { 'directions': 2, 'days': WEEKDAYS },
    27: { 'directions': 1, 'days': ALL_DAYS },
    28: { 'directions': 2, 'days': ALL_DAYS },

    31: { 'directions': 2, 'days': WEEKDAYS },
    33: { 'directions': 1, 'days': WEEKDAYS },
    34: { 'directions': 1, 'days': WEEKDAYS },
    35: { 'directions': 1, 'days': ALL_DAYS },

    43: { 'directions': 1, 'days': ALL_DAYS },
    44: { 'directions': 1, 'days': ALL_DAYS },
}

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
    def __init__(self, content, timetable, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self.in_timetable = False
        self.index = -1
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

    def table_end(self):
        self.in_timetable = False

    def tr_start(self, attrs):
        self.index = -1

    def td_start(self, attrs):
        cl = attrs.get('class', '').split()
        if 'timingPoint' in cl:
            self.timing_point = True
        elif 'intermediateStop' in cl:
            self.intermediate_stop = True
        elif 'eventTimes' in cl:
            self.event_times = True
            self.index += 1

    def td_end(self):
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

    def add_time(self, time):
        timelist = self.timelists[self.index]
        timelist.append({
            'stop': self.current_stop.encode('utf-8'),
            'type': self.current_stop_type,
            'time': time,
        })

class ValidParser(HTMLParser):
    def __init__(self, content, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self.in_superseded = False
        self.in_data = False
        self.valid = None
        self.feed(self.unescape(content))

    def handle_starttag(self, tag, attrs):
        if tag != 'span':
            return
        attrs = dict(attrs)
        if not self.in_superseded and attrs.get('id', '') == 'search_timetableSuperseded':
            self.in_superseded = True
        elif self.in_superseded and attrs.get('class', '') == 'data':
            self.in_data = True

    def handle_data(self, data):
        if not self.in_data:
            return
        data = data.strip()
        self.valid = '%s-%s-%s' % (data[6:10], data[3:5], data[0:2])
        self.in_superseded = False
        self.in_data = False

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
        match = re.match(r'\d+ -\W+(.*)', data, re.UNICODE)
        if not match:
            return
        self.route_name = match.groups()[0].encode('utf-8')
        self.in_timetable_name = False
        self.in_data = False

def data1(route, dt):
    return {
        'hss': get_hss(),
        'serviceNumber': route,
        'serviceTime': '0:00:00', #'%d:%02d:%02d' % (dt.hour, dt.minute, dt.second),
        'serviceTimeH': 0,
        'serviceTimeM': 0,
        'serviceDate': '%02d/%02d/%d' % (dt.day, dt.month, dt.year),
        'serviceDateD': dt.day,
        'serviceDateMY': '%s-%s' % (dt.year, dt.month),
        'methoddefaultMethod': 'Leita...',
    }

def data2(selectedIndex, response):
    return {
        'hss': get_hss(response),
        'selectedIndex': selectedIndex,
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

def save_route(info, route):
    print 'Saving route %d' % route
    filename = 'route-%02d.json' % route
    with open(filename, 'w') as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

def scrape_data(route, direction, dt):
    stops = []
    response = session.post(URL1, data=data1(route, dt))
    response = session.post(URL2, data=data2(direction, response))
    response = session.post(URL3, data=data3(response))
    response = session.post(URL4, data=data4(response))
    tp = TimetableParser(response.text, stops)
    valid = ValidParser(response.text).valid
    route_name = RouteNameParser(response.text).route_name
    cont = ContinueParser(response.text).cont
    while cont:
        response = session.post(URL5, data=data5(response))
        tp = TimetableParser(response.text, stops)
        cont = ContinueParser(response.text).cont
    return route_name, valid, stops

def scrape(route, directions, dt):
    info = []
    for direction in directions:
        route_name, valid, stops = scrape_data(route, direction, dt)
        info.append({
            'name': route_name,
            'valid': valid,
            'stops': stops,
        })
    return info

def next_weekday():
    today = date.today()
    weekday = today.weekday()
    if weekday in [0, 1, 2, 3, 4]:
        return today
    if weekday == 5:
        return today + timedelta(days=2)
    if weekday == 6:
        return today + timedelta(days=1)

def next_saturday():
    today = date.today()
    weekday = today.weekday()
    return today + timedelta(days=(5 - weekday) % 7)

def next_sunday():
    today = date.today()
    weekday = today.weekday()
    return today + timedelta(days=(6 - weekday) % 7)

def main():
    for route, data in ROUTES.iteritems():
        info = {}
        directions = range(data['directions'])
        days = data['days']

        # get weekday
        if 'weekday' in days:
            dt = next_weekday()
            info['weekday'] = scrape(route, directions, dt)
        # get saturday
        if 'saturday' in days:
            dt = next_saturday()
            info['saturday'] = scrape(route, directions, dt)
        # get sunday
        if 'sunday' in days:
            dt = next_sunday()
            info['sunday'] = scrape(route, directions, dt)

        save_route(info, route)
        time.sleep(10)

if __name__ == "__main__":
    main()
