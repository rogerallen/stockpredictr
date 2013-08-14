# stockpredictr_models.py
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

import bisect
import datetime as datetime_module
from django.utils import simplejson
import webapp2 as webapp
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext import db

from stockpredictr_config import G_LIST_SIZE
from stockpredictr_utils import *

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# we need to assign keys ourselves for Contests & such.
# see get_new_contest_key for usage
def get_new_key(model, model_str):
  mckey = "%s_ids"%(model_str)
  model_ids = memcache.get(mckey)
  if ((model_ids is not None) and (len(model_ids) > 0)):
    logging.info("get_new_key from memcache")
  else:
    logging.info("get_new_key alloc new")
    try:
      model_ids_batch = db.allocate_ids(model.all().get().key(), 10)
    except AttributeError:
      model_ids_batch = db.allocate_ids(db.Key.from_path(model_str, 1), 10)
    model_ids = range(model_ids_batch[0], model_ids_batch[1] + 1)
  model_key = db.Key.from_path(model_str, model_ids.pop(0))
  if not memcache.set(mckey,model_ids,30*24*60*60): # 30 days
    logging.error('get_new_key memcache set failure')
  logging.info("get_new_key: model=%s id=%s"%(model_str, model_key.id()))
  return model_key

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# our databases
class Stock(db.Model):
  """
  Table of Stocks used in contests.
  symbol - an all-caps version of the stock symbol
  recent_price[_time] - cache the latest price.
  """
  symbol            = db.StringProperty()
  recent_price      = db.FloatProperty()
  recent_price_time = db.DateTimeProperty(auto_now=True)

def get_or_add_stock_from_symbol(symbol):
  """get stock from symbol.  if it is invalid, return None.
  if it doesn't exist, add it to db
  """
  symbol = symbol.upper()
  stock = get_stock_from_symbol(symbol)
  if stock == None:
    logging.info('validating stock %s' % (symbol))
    stock_price = get_stock_price_uncached(symbol)
    if type(stock_price) != type(float()):
      logging.info('invalid stock')
      return None
    logging.info('adding stock %s and price %f to db' % (symbol, stock_price))
    stock = Stock()
    stock.symbol = symbol
    stock.recent_price = stock_price
    stock.put()
  return stock

def get_stock_from_symbol(symbol):
  """return the Stock for the symbol.  None if it doesn't exist."""
  symbol = symbol.upper()
  stocks   = db.GqlQuery("SELECT * FROM Stock WHERE symbol = :1",
                         symbol).fetch(1)
  if len(stocks) == 0:
    return None
  else:
    assert(len(stocks) == 1)
    stock = stocks[0]
  return stock

STOCK_CACHE_SECONDS = 60 # Update every minute, at most
def get_stock_price(symbol):
  """get stock price and cache the result"""
  stock = get_stock_from_symbol(symbol)
  if stock == None:
    logging.info("didn't find symbol %s"%(symbol))
    return "Unknown"
  now = datetime_module.datetime.utcnow()
  dt = now - stock.recent_price_time
  #logging.info("now "+str(now))
  #logging.info("dt  "+str(dt))
  #logging.info("d   "+str(datetime.timedelta(0,STOCK_CACHE_SECONDS,0)))
  if market_open():
    N = 1  # one period during open
  else:
    N = 15 # 15x slower during close
  if dt > datetime_module.timedelta(0,N*STOCK_CACHE_SECONDS,0):
    logging.info("going to get stock price...")
    try:
      stock_price = get_stock_price_uncached(symbol)
      stock.recent_price = stock_price
      stock.put()
    except urlfetch.DownloadError:
      logging.exception("GetStockPrice DownloadError. Returning cached value")
      stock_price = stock.recent_price
    except db.BadValueError:
      logging.exception("GetStockPrice BadValueError. Returning cached value")
      stock_price = stock.recent_price
  else:
    logging.info("returning cached stock price")
    stock_price = stock.recent_price
  return stock_price

def get_stock_price_uncached(symbol):
  # add 'TEST' short-circuit stock that is always $12.0625/share
  if symbol == 'TEST':
    return 12.0625
  #stock_price_url = "http://brivierestockquotes.appspot.com/?q=%s" % (symbol)
  stock_price_url = "http://finance.google.com/finance/info?client=ig&q=%s" % (symbol)
  stock_price_result = urlfetch.fetch(stock_price_url)
  if stock_price_result.status_code == 200:
    #tmp = stock_price_result.content.replace(',]',']')
    tmp = stock_price_result.content.replace('// ','')
    logging.info("stock response = %s" % (tmp))
    stock_data = simplejson.loads(tmp)
    if len(stock_data) > 0:
      #stock_price = float(stock_data[0]["price"])
      stock_price = float(stock_data[0]["l"])
    else:
      stock_price = "Unknown"
  else:
    stock_price = "Unavailable"
  logging.info("stock price = %s" % (stock_price))
  return stock_price

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class MyUser(db.Model):
  """
  Table of Users that play in the contests.
  nickname - how they want to call themselves
  user - how google tracks them
  """
  nickname = db.StringProperty() # custom nickname for this site
  wins     = db.IntegerProperty()
  losses   = db.IntegerProperty()
  win_pct  = db.FloatProperty()
  user     = db.UserProperty()
  authorized_contest_list = db.ListProperty(db.Key)

def get_my_current_user():
  """return the MyUser for the current_user, adding if necessary"""
  if users.get_current_user() == None:
    return None

  my_users = db.GqlQuery("SELECT * FROM MyUser WHERE user = :1",
                         users.get_current_user()).fetch(1)
  if len(my_users) == 0:
    logging.info('adding current user %s to db' % (users.get_current_user().nickname()))
    my_user = MyUser()
    my_user.user     = users.get_current_user()
    my_user.nickname = users.get_current_user().nickname()
    my_user.wins     = 0
    my_user.losses   = 0
    my_user.win_pct  = 0.0
    my_user.put()
  else:
    assert(len(my_users) == 1)
    my_user = my_users[0]
  logging.info('get_my_current_user %s' % (my_user.nickname))
  return my_user

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class Contest(db.Model):
  """
  The Contests that we play
  private is a flag for requiring a passphrase
  salt is a random number that we use for defeating rainbow attacks (unlikely!)
  hashphrase is the hashed result of passphrase + salt
  """
  owner       = db.ReferenceProperty(MyUser)
  stock       = db.ReferenceProperty(Stock)
  close_date  = db.DateProperty()
  final_value = db.FloatProperty()
  private     = db.BooleanProperty()
  salt        = db.StringProperty()
  hashphrase  = db.StringProperty()

# shared make_private routine
def make_private(contest, private, passphrase):
  contest.private = private
  if contest.private:
    logging.info('this is a private contest')
    contest.salt       = str(int(random.randint(1000,10000)))
    contest.hashphrase = myhash(passphrase+contest.salt)
  else:
    logging.info('this is a public contest')
    contest.salt       = None
    contest.hashphrase = None

def get_new_contest_key():
  return get_new_key(Contest,'Contest')

def get_contests(contests_query,contest_str,timeout):
  num = G_LIST_SIZE
  mckey = contest_str
  contests = memcache.get(mckey)
  if contests is not None:
    logging.info("get_%s from memcache"%(contest_str))
  else:
    logging.info("get_%s from DB",contest_str)
    contests = contests_query.fetch(num)
    if not memcache.set(mckey,contests,timeout):
      logging.error('get_%s memcache set failure'%(contest_str))
  # what happens on none? if contests is not None:
  return contests[:num] # in case cache has more

def get_open_contests():
  today = datetime_module.date.today()
  return get_contests(db.GqlQuery("SELECT * FROM Contest " +
                                  "WHERE close_date >= :1 " +
                                  "ORDER BY close_date ASC", today),
                      "open_contests",
                      60)

def get_closed_contests():
  today = datetime_module.date.today()
  return get_contests(db.GqlQuery("SELECT * FROM Contest " +
                                  "WHERE close_date < :1 " +
                                  "ORDER BY close_date DESC", today),
                      "closed_contests",
                      60)

def put_contest(contest):
  contest_id = str(contest.key().id())
  logging.info("put_contest:"+contest_id)
  contest.put()
  mckey = "contest"+contest_id
  if not memcache.set(mckey,contest,60):
    logging.error('put_contest:%s memcache set failure'%(mckey))
  # also insert into the open_contests list
  contests = memcache.get("open_contests")
  if contests is not None:
    close_dates = [v.close_date for v in contests]
    i = bisect.bisect_left(close_dates,contest.close_date)
    contests = contests[0:i] + [contest] + contests[i:]
  else:
    contests = [contest]
  for i,c in enumerate(contests):
    logging.info("put_contest: %d %s"%(i,c.key().id()))
  if not memcache.set("open_contests",contests,60):
    logging.error('put_contest:open_contests memcache set failure')



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def finish_contest(contest, final_value):
  """
  Finalize a contest's final_value and prediction winner
  """
  logging.info("Closing contest %s %s" % ( contest.owner, contest.stock ))
  contest.final_value = final_value
  contest.put()
  prediction_query = db.GqlQuery("SELECT * FROM Prediction WHERE contest = :1", contest)
  min_pred = 100000.0
  for prediction in prediction_query:
    prediction.winner = False
    prediction.put()
    delta = abs(prediction.value - contest.final_value)
    if min_pred > delta:
      min_pred = delta
  if contest.final_value >= 0.0:
    for prediction in prediction_query:
      delta = abs(prediction.value - contest.final_value)
      if min_pred == delta:
        prediction.winner = True
        prediction.put()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class Prediction(db.Model):
  """
  Table of Predictions - one per user per contest.  updates allowed.
  """
  user    = db.ReferenceProperty(MyUser)
  contest = db.ReferenceProperty(Contest)
  value   = db.FloatProperty()
  winner  = db.BooleanProperty()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class FauxPrediction(object):
  """
  a version of a Prediction we use just for the webpage presentation
  """
  def __init__(self,user_nickname,user_id,value,winner,is_price):
    self.user_nickname = user_nickname
    self.user_id       = user_id
    self.value         = value
    self.value_str     = get_price_str(value)
    self.winner        = winner
    self.is_price      = is_price
    self.leader        = False
