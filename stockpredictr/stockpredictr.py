# stockpredictr.py
#
# Copyright (C) 2009-2013 Roger Allen (rallen@gmail.com)
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
"""
stockpredictr.py - main code for handling the http://stockpredictr.appspot.com/
website via google's app engine system.
"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# changed to use appengine_config.py
#
# even though I don't use django, apparently I need to pick the version
# see http://code.google.com/appengine/docs/python/tools/libraries.html#Django
#import os
#os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
#
#from google.appengine.dist import use_library
#use_library('django', '1.2')
#use_library('django', '0.96')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
import webapp2 as webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from stockpredictr_views  import *

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
application = webapp.WSGIApplication(
  [ ( '/',                    HandleRoot),          # GET/POST list of contests
    ( '/about',               HandleAbout),         # GET some info
    (r'/contest/(.*)',        HandleContest),       # GET contest detail
    ( '/contests',            HandleContests),      # GET list of contests
    (r'/user/(.*)',           HandleUser),          # GET/POST user attributes
    ( '/admin/finish_any',    FinishAnyContests),   # GET finish contests
    ( '/admin/do_that_thing', DoThatThing),         # GET something special
    ( '/.*',                  NotFoundPageHandler), # 404 Error
    ],
  debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__": # pragma: no cover
  main()
