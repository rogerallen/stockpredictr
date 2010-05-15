# stockpredictr.py
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

"""
stockpredictr.py - main code for handling the http://stockpredictr.appspot.com/
website via google's app engine system.
"""
import cgi
import os
import logging
import datetime as datetime_module
import random
import hashlib
from django.utils import simplejson
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import urlfetch

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# some global strings
g_footer = """
<p>Copyright (c) 2009-2010 Stockpredictr. All rights reserved.
Design by <a href="http://www.freecsstemplates.org/">Free CSS Templates</a>.</p>
"""

g_welcome_warning = """<h2>Welcome</h2>
<p>Welcome to Stockpredictr, the site for stock
prediction contests.</p>
<h2>Warning</h2>
<p>This site is being actively developed and the software is
beta-quality.  Please report any issues to the
<a href="http://code.google.com/p/stockpredictr/issues">the development
site</a>.  Thanks!</p>
"""


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

class Prediction(db.Model):
  """
  Table of Predictions - one per user per contest.  updates allowed.
  """
  user    = db.ReferenceProperty(MyUser)
  contest = db.ReferenceProperty(Contest)
  value   = db.FloatProperty()
  winner  = db.BooleanProperty()

class FauxPrediction(object):
  """
  a version of a Prediction we use just for the webpage presentation
  """
  def __init__(self,user_nickname,user_id,value,winner,is_price):
    self.user_nickname = user_nickname
    self.user_id       = user_id
    self.value         = value
    self.winner        = winner
    self.is_price      = is_price
    self.leader        = False

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
# session utils
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

def myhash(salted_password):
  x = hashlib.sha256()
  x.update(salted_password)
  return x.hexdigest()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# stock utils
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
  if dt > datetime_module.timedelta(0,STOCK_CACHE_SECONDS,0):
    logging.info("going to get stock price...")
    stock_price = get_stock_price_uncached(symbol)
    stock.recent_price = stock_price
    stock.put()
  else:
    logging.info("returning cached stock price")
    stock_price = stock.recent_price
  return stock_price

def get_stock_price_uncached(symbol):
  # add 'TEST' short-circuit stock that is always $12.0625/share
  if symbol == 'TEST':
    return 12.0625
  stock_price_url = "http://brivierestockquotes.appspot.com/?q=%s" % (symbol)
  stock_price_result = urlfetch.fetch(stock_price_url)
  if stock_price_result.status_code == 200:
    tmp = stock_price_result.content.replace(',]',']')
    logging.info("stock response = %s" % (tmp))
    stock_data = simplejson.loads(tmp)
    if len(stock_data) > 0:
      stock_price = float(stock_data[0]["price"])
    else:
      stock_price = "Unknown"
  else:
    stock_price = "Unavailable"
  logging.info("stock price = %s" % (stock_price))
  return stock_price

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET index.html
# POST / for a new_contest
class HandleRoot(webapp.RequestHandler):
  def get(self,
          error_flag=False, error_message=None,
          form_symbol="",
          form_year="", form_month="", form_day="",
          form_private="", form_passphrase=""
          ):
    # TODO - user privacy
    #users_query = db.GqlQuery("SELECT * FROM MyUser WHERE win_pct > 0.0 ORDER BY win_pct DESC")
    #users = users_query.fetch(25)
    today = datetime_module.date.today()
    open_contests_query = db.GqlQuery(
      "SELECT * FROM Contest " +
      "WHERE close_date >= :1 " +
      "ORDER BY close_date ASC", today)
    open_contests = open_contests_query.fetch(25)
    closed_contests_query = db.GqlQuery(
      "SELECT * FROM Contest " +
      "WHERE close_date < :1 " +
      "ORDER BY close_date DESC", today)
    closed_contests = closed_contests_query.fetch(25)
    (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)
    cur_user = get_my_current_user()

    template_values = {
      # TODO - user privacy
      #'users':              users,
      'open_contests':      open_contests,
      'closed_contests':    closed_contests,
      'cur_user':           cur_user,
      'login_url':          login_url,
      'login_url_linktext': login_url_linktext,
      'logged_in_flag':     logged_in_flag,
      'error_flag':         error_flag,
      'error_message':      error_message,
      'form_symbol':        form_symbol,
      'form_year':          form_year,
      'form_month':         form_month,
      'form_day':           form_day,
      'form_private':       form_private,
      'form_passphrase':    form_passphrase,
      'g_footer':           g_footer,
      'g_welcome_warning':  g_welcome_warning,
      }
    
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    self.response.out.write(template.render(path, template_values))

  def post(self):
    """Create a new contest..."""
    try:
      if users.get_current_user():
        cur_user = get_my_current_user()
        stock = get_or_add_stock_from_symbol(self.request.get('symbol'))
        if stock == None:
          raise ValueError('could not find the stock symbol')
        logging.info('adding contest to db')
        contest = Contest()
        contest.owner        = cur_user
        contest.stock        = stock
        contest.close_date   = datetime_module.date(
          int(self.request.get('year')),
          int(self.request.get('month')),
          int(self.request.get('day')))
        if contest.close_date <= datetime_module.date.today():
          raise ValueError('contest date must be in the future')
        if contest.close_date.weekday() >= 5:
          raise ValueError('contest date must be a weekday')
        contest.final_value  = -1.0
        make_private(contest,
                     self.request.get('private') == '1',
                     self.request.get('passphrase'))
        contest.put()
        logging.info("contest id"+str(contest.key().id()))
        self.redirect('/contest/'+str(contest.key().id()))
    except ValueError, verr: # python2.6!
      logging.exception("CreateContest ValueError")
      self.get(error_flag      = True,
               error_message   = verr,
               form_symbol     = self.request.get('symbol'),
               form_year       = self.request.get('year'),
               form_month      = self.request.get('month'),
               form_day        = self.request.get('day'),
               form_private    = self.request.get('private'),
               form_passphrase = self.request.get('passphrase'),
               )
    except:
      logging.exception("CreateContest Error")
      self.get(error_flag      = True,
               error_message   = "There was an error.  Sorry I can't be more specific.",
               form_symbol     = self.request.get('symbol'),
               form_year       = self.request.get('year'),
               form_month      = self.request.get('month'),
               form_day        = self.request.get('day'),
               form_private    = self.request.get('private'),
               form_passphrase = self.request.get('passphrase'),
               )

  
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET about.html
class HandleAbout(webapp.RequestHandler):
  def get(self):
    (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)
    cur_user = get_my_current_user()
    template_values = {
      'cur_user':            cur_user,
      'login_url':          login_url,
      'login_url_linktext': login_url_linktext,
      'g_footer':           g_footer,
      'g_welcome_warning':  g_welcome_warning,
      }
    path = os.path.join(os.path.dirname(__file__), 'about.html')
    self.response.out.write(template.render(path, template_values))

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
# GET contest/id
class HandleContest(webapp.RequestHandler):
  def get(self,contest_id,
          prediction_error_flag=False,
          final_value_error_flag=False,
          passphrase_error_flag=False,
          error_message=None,
          form_prediction="",
          form_final_value="",
          form_passphrase=""):
    try:
      cur_user = get_my_current_user()
      (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)
      logging.info("HandleContest/%d (GET)" % int(contest_id))
      contest = Contest.get_by_id(long(contest_id))
      # check for privacy and authorization
      owner_flag = users.get_current_user() == contest.owner.user
      in_authorized_list = False
      if cur_user:
        in_authorized_list = contest.key() in cur_user.authorized_contest_list
      stock_price = None
      authorized_to_view = True
      if contest.private:
        authorized_to_view = users.is_current_user_admin() or owner_flag or in_authorized_list
        logging.info("private: allowed=%s" % (authorized_to_view))

      if authorized_to_view:
        prediction_query = db.GqlQuery("SELECT * FROM Prediction WHERE contest = :1",
                                       contest)
        predictions = prediction_query.fetch(100) # TODO(issue 7) multiple pages?

        # create a list that can get the stock price inserted
        faux_predictions = []
        for p in predictions:
          faux_predictions.append(FauxPrediction(
            p.user.nickname, p.user.key().id(), p.value, p.winner,False
            ))
          
        # see if we should allow the contest to be updated
        now = datetime_module.datetime.now(eastern_tz)
        contest_close_market_open = datetime_module.datetime(
          contest.close_date.year, contest.close_date.month, contest.close_date.day,
          9, 30, 0, 0,
          eastern_tz)
        can_update_flag = now < contest_close_market_open
        open_flag = contest.final_value < 0.0
        stock_name = contest.stock.symbol
        if open_flag:
          stock_name += " Current Price"
          stock_price = get_stock_price(contest.stock.symbol)
        else:
          stock_name += " Final Price"
          stock_price = contest.final_value

        # find the current leader(s)
        if open_flag:
          min_pred = 100000.0
          for prediction in faux_predictions:
            delta = abs(prediction.value - stock_price) 
            if min_pred > delta:
              min_pred = delta
          for prediction in faux_predictions:
            delta = abs(prediction.value - stock_price)
            if min_pred == delta:
              prediction.leader = True

        # add stock price to list of "faux" predictions
        faux_predictions.append(FauxPrediction(
          stock_name, 0, stock_price, False, True
          ))
        faux_predictions.sort(key=lambda p: p.value)
        faux_predictions.reverse()
      else:
        faux_predictions     = []
        can_update_flag = False
        open_flag       = False
        
      template_values = {
        'authorized':         authorized_to_view,
        'contest':            contest,
        'stock_price':        stock_price,
        'predictions':        faux_predictions,
        'can_update_flag':    can_update_flag,
        'owner_flag':         owner_flag,
        'open_flag':          open_flag,
        'cur_user':           cur_user,
        'login_url':          login_url,
        'login_url_linktext': login_url_linktext,
        'logged_in_flag':     logged_in_flag,
        'prediction_error_flag': prediction_error_flag,
        'final_value_error_flag': final_value_error_flag,
        'passphrase_error_flag': passphrase_error_flag,
        'error_message':      error_message,
        'form_prediction':    form_prediction,
        'form_final_value':   form_final_value,
        'form_passphrase':    form_passphrase,
        'g_footer':           g_footer,
        'g_welcome_warning':  g_welcome_warning,
        }
    
      path = os.path.join(os.path.dirname(__file__), 'contest.html')
      self.response.out.write(template.render(path, template_values))
    except:
      logging.exception("HandleContest GET Error")
      error_message = "The requested contest does not exist."
      template_values = {
        'error_message':      error_message,
        'cur_user':           cur_user,
        'login_url':          login_url,
        'login_url_linktext': login_url_linktext,
        'logged_in_flag':     logged_in_flag,
        'g_footer':           g_footer,
        'g_welcome_warning':  g_welcome_warning,
        }
      path = os.path.join(os.path.dirname(__file__), 'error.html')
      self.response.out.write(template.render(path, template_values))
      
  def post(self,contest_id):
    """There are 3 different forms to handle:
    passphrase, prediction and final_value
    """
    if self.request.get('passphrase') != "":
      self.authorize_contest(contest_id)
    elif self.request.get('prediction') != "":
      self.edit_prediction(contest_id)
    else:
      self.finish_contest(contest_id)
    
  def edit_prediction(self,contest_id):
    try:
      logging.info("HandleContest/%d POST edit_prediction" % int(contest_id))
      if users.get_current_user():
        contest = Contest.get_by_id(long(contest_id))
        cur_user = get_my_current_user()
        value = float(self.request.get('prediction'))
        prediction_query = db.GqlQuery("SELECT * FROM Prediction WHERE user = :1 AND contest = :2",
                                       cur_user,
                                       contest)
        predictions = prediction_query.fetch(2)
        if predictions:
          assert(len(predictions) == 1)
          logging.info('found previous prediction')
          prediction = predictions[0]
        else:
          logging.info('adding prediction to db')
          prediction = Prediction()
        prediction.user       = cur_user
        prediction.contest    = contest
        prediction.value      = value
        prediction.winner     = False
        prediction.put()
        self.get(contest_id)
    except:
      logging.exception("EditPrediction Error")
      self.get(contest_id,
               prediction_error_flag=True,
               error_message="There was an error with your prediction.",
               form_prediction=self.request.get('prediction')
               )

  def finish_contest(self,contest_id):
    try:
      logging.info("HandleContest/%d POST finish_contest" % int(contest_id))
      contest = Contest.get_by_id(long(contest_id))
      final_value = float(self.request.get('final_value'))
      finish_contest(contest,final_value)
      self.get(contest_id)
    except:
      logging.exception("FinishContest Error")
      self.get(contest_id,
               final_value_error_flag=True,
               error_message="There was an error with your final value.",
               form_final_value=self.request.get('final_value')
               )

  def authorize_contest(self,contest_id):
    """Authorize the current user to view this contest
    """
    try:
      logging.info("HandleContest/%d POST authorize_contest" % int(contest_id))
      if users.get_current_user():
        logging.info('got cur_user')
        cur_user = get_my_current_user()
        contest = Contest.get_by_id(long(contest_id))
        passphrase = self.request.get('passphrase')
        passphrase_match = contest.hashphrase == myhash(passphrase+contest.salt)
        logging.info('passphrase=%s match=%s'%(passphrase,passphrase_match))
        if passphrase_match:
          cur_user.authorized_contest_list.append(contest.key())
          cur_user.put()
          self.get(contest_id)
        else:
          self.get(contest_id,
                   passphrase_error_flag=True,
                   error_message="Your passphrase did not match.",
                   form_passphrase=passphrase
                   )
    except:
      logging.exception("AuthorizeContest Error")
      self.get(contest_id,
               passphrase_error_flag=True,
               error_message="There was an error with your passphrase.",
               form_passphrase=passphrase
               )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_contest_index(s):
  try:
    i = int(s)
  except ValueError:
    i = 0
  return i

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET /contests
class HandleContests(webapp.RequestHandler):
  def get(self):
    (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)
    cur_user = get_my_current_user()
    contest_count = 25
    cur_index = get_contest_index(self.request.get('i'))
    contests_query = db.GqlQuery(
      "SELECT * FROM Contest ORDER BY close_date DESC")
    # TODO(issue 7) eventual bugfix: offset must be less than 1000
    contests = contests_query.fetch(contest_count,cur_index)
    later_index = max(0,cur_index-contest_count)
    later_contests_flag = later_index < cur_index
    earlier_index = cur_index+len(contests)
    # TODO(issue 7) this isn't perfect
    earlier_contests_flag = earlier_index == cur_index+contest_count
    template_values = {
      'cur_user':              cur_user,
      'login_url':             login_url,
      'login_url_linktext':    login_url_linktext,
      'g_footer':              g_footer,
      'g_welcome_warning':     g_welcome_warning,
      'contests':              contests,
      'later_contests_flag':   later_contests_flag,
      'earlier_contests_flag': earlier_contests_flag,
      'later_index':           later_index,
      'earlier_index':         earlier_index
      }
    path = os.path.join(os.path.dirname(__file__), 'contests.html')
    self.response.out.write(template.render(path, template_values))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET user/id
# POST user/id 
class HandleUser(webapp.RequestHandler):
  def get(self,user_id):
    try:
      cur_user = get_my_current_user()
      (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)
      the_user = MyUser.get_by_id(long(user_id))
      logging.info("HandleUser/%d GET" % int(user_id))
      # TODO - user privacy
      try:
        authorized_to_view = the_user.user == cur_user.user or users.is_current_user_admin()
        authorized_to_edit = the_user.user == cur_user.user
      except AttributeError:
        authorized_to_view = False
        authorized_to_edit = False
      # NOTE the use of reference properties instead of a query
      # AND they are sorted by contest close date!  (yay)
      predictions = sorted(the_user.prediction_set,key=lambda obj: obj.contest.close_date)
      closed_predictions = filter(lambda obj: obj.contest.final_value >= 0.0, predictions)
      open_predictions = filter(lambda obj: obj.contest.final_value < 0.0, predictions)
      template_values = {
        'the_user':           the_user,
        'closed_predictions': closed_predictions,
        'open_predictions':   open_predictions,
        'authorized_to_view': authorized_to_view,
        'authorized_to_edit': authorized_to_edit,
        'cur_user':           cur_user,
        'login_url':          login_url,
        'login_url_linktext': login_url_linktext,
        'logged_in_flag':     logged_in_flag,
        'g_footer':           g_footer,
        'g_welcome_warning':  g_welcome_warning,
        }
      path = os.path.join(os.path.dirname(__file__), 'user.html')
      self.response.out.write(template.render(path, template_values))
    except:
      logging.exception("HandleUser GET Error")
      error_message = "The requested user does not exist."
      template_values = {
        'error_message':      error_message,
        'cur_user':           cur_user,
        'login_url':          login_url,
        'login_url_linktext': login_url_linktext,
        'logged_in_flag':     logged_in_flag,
        'g_footer':           g_footer,
        'g_welcome_warning':  g_welcome_warning,
        }
      path = os.path.join(os.path.dirname(__file__), 'error.html')
      self.response.out.write(template.render(path, template_values))
      
  def post(self,user_id):
     try:
       logging.info("HandleUser/%d POST" % int(user_id))
       my_user = MyUser.get_by_id(long(user_id))
       if my_user.user == users.get_current_user():
         my_user.nickname = self.request.get('nickname')
         my_user.put()
         logging.info('updated nickname to %s' % (my_user.nickname))
     except: 
      logging.exception("HandleUser Error")
     self.redirect('/user/'+user_id)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET /admin/finish_any
# - only admin allowed via app.yaml
# - should be called by cron only
class FinishAnyContests(webapp.RequestHandler):
  def get(self):
    logging.info('FinishAnyContests called')
    today = datetime_module.date.today() # 4:30pm != next day...
    logging.info("today=%s"%(today))
    contests_query = db.GqlQuery("SELECT * FROM Contest WHERE close_date <= :1", today)
    for contest in contests_query:
      # only update contests that need a final value to be added
      if contest.final_value < 0.0:
        final_value = get_stock_price(contest.stock.symbol)
        finish_contest(contest,final_value)
    # now get each person's win/loss record straight
    for user in db.GqlQuery("SELECT * FROM MyUser"):
      user.wins = 0
      user.losses = 0
      for prediction in db.GqlQuery("SELECT * FROM Prediction WHERE user = :1",user):
        if prediction.contest.final_value >= 0.0:
          if prediction.winner:
            user.wins += 1
          else:
            user.losses += 1
      try:
        user.win_pct = 100*float(user.wins)/float(user.wins + user.losses)
      except ZeroDivisionError:
        user.win_pct = 0.0
      # round to nearest 100th
      user.win_pct = int(user.win_pct*100)/100.0
      user.put()
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Done')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET /admin/do_that_thing
# - only admin allowed via app.yaml
# meant to be a special one-time call to fixup some database issue
class DoThatThing(webapp.RequestHandler):
  def get(self):
    logging.info('DoThatThing called')
    self.response.headers['Content-Type'] = 'text/plain'
    if 0:
      # example--make an old contest private
      the_owner_nickname = 'Mr Predictr'
      the_stock_symbol   = 'NVDA'
      the_close_date     = datetime_module.date(2009,11,6)
      new_hashphrase     = 'longhexvaluehere'
      new_salt           = 'someseedhere'
      new_private        = True
      #
      the_owner = db.GqlQuery(
        "SELECT * FROM MyUser WHERE nickname = :1",
        the_owner_nickname
        ).fetch(1)
      the_stock = db.GqlQuery(
        "SELECT * FROM Stock WHERE symbol = :1",
        the_stock_symbol
        ).fetch(1)
      contests_query = db.GqlQuery(
        "SELECT * FROM Contest WHERE owner = :1 AND stock = :2 AND close_date = :3",
        the_owner[0],
        the_stock[0],
        the_close_date
        ).fetch(1)
      contest = contests_query[0]
      contest.hashphrase = new_hashphrase
      contest.salt       = new_salt
      contest.private    = new_private
      contest.put()
    self.response.out.write('Done\n')



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET catchall for any page not otherwise handled
class NotFoundPageHandler(webapp.RequestHandler):
  def get(self):
    logging.info("NotFoundPageHandler")
    cur_user = get_my_current_user()
    (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)

    error_message = "The requested page could not be found.  This is also known as a '404 Error'"
    self.error(404)
    template_values = {
      'error_message':      error_message,
      'cur_user':           cur_user,
      'login_url':          login_url,
      'login_url_linktext': login_url_linktext,
      'logged_in_flag':     logged_in_flag,
      'g_footer':           g_footer,
      'g_welcome_warning':  g_welcome_warning,
      }
    
    path = os.path.join(os.path.dirname(__file__), 'error.html')
    self.response.out.write(template.render(path, template_values))
                    
        
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

if __name__ == "__main__":
  main()

