# stockpredictr_utils.py
#
# Copyright (C) 2009,2010 Roger Allen (rallen@gmail.com)
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

import os
import logging
import datetime as datetime_module
import random
import hashlib
from google.appengine.api import users

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Time utils
# Eastern timezone for market open/close
class Eastern_tzinfo(datetime_module.tzinfo):
  """Implementation of the Eastern timezone where the NYSE is."""
  def utcoffset(self, dt):
    return datetime_module.timedelta(hours=-5) + self.dst(dt)
  
  def _FirstSunday(self, dt):
    """First Sunday on or after dt."""
    return dt + datetime_module.timedelta(days=(6-dt.weekday()))

  def dst(self, dt):
    # 2 am on the second Sunday in March
    dst_start = self._FirstSunday(datetime_module.datetime(dt.year, 3, 8, 2))
    # 1 am on the first Sunday in November
    dst_end = self._FirstSunday(datetime_module.datetime(dt.year, 11, 1, 1))

    if dst_start <= dt.replace(tzinfo=None) < dst_end:
      return datetime_module.timedelta(hours=1)
    else:
      return datetime_module.timedelta(hours=0)

  def tzname(self, dt):
    if self.dst(dt) == datetime_module.timedelta(hours=0):
      return "EST"
    else:
      return "EDT"
# this was from the example, but it doesn't work
# eastern_time_zone = utc_time.astimezone(Eastern_tzinfo())
eastern_tz = Eastern_tzinfo()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_market_time_now():
  return datetime_module.datetime.now(eastern_tz)

def get_market_time_open(y,m,d):
  """given a year/month/day, return the datetime object for the market open
  ==> 09:00"""
  return datetime_module.datetime(y, m, d, 9, 30, 0, 0, eastern_tz)

def get_market_time_close(y,m,d):
  """given a year/month/day, return the datetime object for the market close
  == 16:00"""
  return datetime_module.datetime(y, m, d, 16, 0, 0, 0, eastern_tz)

def market_open():
  """Return True if open.  hours are 9:30 - 4:30, Eastern.  A half-hour
  grace period at the end  to make sure market is settled"""
  now = get_market_time_now()
  open_time = get_market_time_open(now.year, now.month, now.day)
  close_time = get_market_time_close(now.year, now.month, now.day)
  close_time += datetime_module.timedelta(0,30*60) # add 30 mins
  return (now.weekday() < 5 and
          open_time < now < close_time)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# session utils
def get_login_url_info(cls):
  """return (logged_in_flag, login_url, login_url_linktext)."""
  logged_in_flag = False
  if users.get_current_user():
    login_url = users.create_logout_url(cls.request.uri)
    login_url_linktext = 'Logout'
    logged_in_flag = True
  else:
    login_url = users.create_login_url(cls.request.uri)
    login_url_linktext = 'Login'  
  return (logged_in_flag, login_url, login_url_linktext)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def myhash(s):
  """given a string, return a hexdigest hash.  string is normally
  a salted password"""
  x = hashlib.sha256()
  x.update(s)
  return x.hexdigest()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_price_str(f):
  """given a floating point number, return a dollar-based price string"""
  s = str(float(f))
  (si,sf) = s.split('.')
  while len(sf) < 2:
    sf = sf + '0'
  return '$'+si+'.'+sf

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def template_path(s):
  return os.path.join(os.path.dirname(__file__), 'templates', s)
