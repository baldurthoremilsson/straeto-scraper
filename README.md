straeto-scraper
===============

A simple Python scraper for s.is

First version, undocumented and very raw. Run the scraper:

    $ ./scraper.py

and your current directory will fill up with route-XX.json files containing
info for routes 1 - 44.

Depends on the [Requests HTTP library](http://docs.python-requests.org/en/latest/).

When you have scraped all the routes you can manually inspect the data using
srvr.py. It is a simple WSGI server that displays a timetable for the routes
in the current directory. Run the server from the same directory as your json
files are:

    $ gunicorn srvr:app

Now you can browse the timetables on http://localhost:8000.
