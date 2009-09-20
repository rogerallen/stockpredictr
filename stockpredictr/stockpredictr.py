import cgi
import os
import logging
import datetime

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# our databases
class Stock(db.Model):
  symbol = db.StringProperty()
  
class MyUser(db.Model):
  nickname = db.StringProperty() # custom nickname for this site
  user = db.UserProperty()

class Contest(db.Model):
  owner       = db.ReferenceProperty(MyUser)
  stock       = db.ReferenceProperty(Stock)
  close_date  = db.DateProperty()
  final_value = db.FloatProperty()

class Prediction(db.Model):
  user    = db.ReferenceProperty(MyUser)
  contest = db.ReferenceProperty(Contest)
  value   = db.FloatProperty()
  winner  = db.BooleanProperty()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# data utils
def get_my_current_user():
  """return the MyUser for the current_user, adding if necessary"""
  if users.get_current_user() == None:
    return None
  
  my_users = db.GqlQuery("SELECT * FROM MyUser WHERE user = :1",
                         users.get_current_user()).fetch(10)
  if len(my_users) == 0:
    logging.info('adding current user %s to db' % (users.get_current_user().nickname()))
    my_user = MyUser()
    my_user.user     = users.get_current_user()
    my_user.nickname = users.get_current_user().nickname()
    my_user.put()
  else:
    assert(len(my_users) == 1)
    my_user = my_users[0]
  logging.info('get_my_current_user %s' % (my_user.nickname))
  return my_user

def get_stock_from_symbol(symbol):
  """return the Stock for the symbol"""
  symbol = symbol.upper()
  stocks   = db.GqlQuery("SELECT * FROM Stock WHERE symbol = :1",
                         symbol).fetch(1)
  if len(stocks) == 0:
    logging.info('adding stock %s to db' % (symbol))
    stock = Stock()
    stock.symbol = symbol
    stock.put()
  else:
    assert(len(stocks) == 1)
    stock = stocks[0]
  return stock

def get_login_url_info(cls):
  """return (logged_in_flag, login_url, login_url_linktext)"""
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
# our webpages
class MainPage(webapp.RequestHandler):
  def get(self):
    contests_query = Contest.all().order('close_date')
    contests = contests_query.fetch(10)
    (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)
    cur_user = get_my_current_user()

    template_values = {
      'contests':           contests,
      'cur_user':            cur_user,
      'login_url':          login_url,
      'login_url_linktext': login_url_linktext,
      'logged_in_flag':     logged_in_flag,
      }
    
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    self.response.out.write(template.render(path, template_values))

class About(webapp.RequestHandler):
  def get(self):
    (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)
    cur_user = get_my_current_user()
    template_values = {
      'cur_user':            cur_user,
      'login_url':          login_url,
      'login_url_linktext': login_url_linktext,
      }
    path = os.path.join(os.path.dirname(__file__), 'about.html')
    self.response.out.write(template.render(path, template_values))

class CreateContest(webapp.RequestHandler):
  def post(self):
    try:
      if users.get_current_user():
        logging.info('got user')
        cur_user = get_my_current_user()
        logging.info('got myuser')
        stock = get_stock_from_symbol(self.request.get('symbol'))
        logging.info('adding contest to db')
        contest = Contest()
        contest.owner       = cur_user
        contest.stock       = stock
        contest.close_date  = datetime.date(int(self.request.get('year')),
                                            int(self.request.get('month')),
                                            int(self.request.get('day')))
        contest.final_value = -1.0
        contest.put()
        logging.info("contest id"+str(contest.key().id()))
        self.redirect('/contest/'+str(contest.key().id()))
    except:
      logging.info("caught some error")
      self.redirect('/')
  

class ViewContest(webapp.RequestHandler):
  def get(self,contest_id):
    logging.info("ViewContest/%d" % int(contest_id))
    contest = Contest.get_by_id(long(contest_id))
    
    prediction_query = db.GqlQuery("SELECT * FROM Prediction WHERE contest = :1 ORDER BY value DESC",
                                   contest)
    predictions = prediction_query.fetch(100) # xxx multiple pages?

    (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)

    owner_flag = users.get_current_user() == contest.owner.user
    open_flag = contest.final_value < 0.0
    logging.info("owner %s curuser %s owner_flag %s lif %s open_flag %s" %
                 ( contest.owner.user, users.get_current_user(), owner_flag, logged_in_flag, open_flag ))
    cur_user = get_my_current_user()
    template_values = {
      'contest':            contest,
      'predictions':        predictions,
      'owner_flag':         owner_flag,
      'open_flag':          open_flag,
      'cur_user':            cur_user,
      'login_url':          login_url,
      'login_url_linktext': login_url_linktext,
      'logged_in_flag':     logged_in_flag,
      }
    
    path = os.path.join(os.path.dirname(__file__), 'contest.html')
    self.response.out.write(template.render(path, template_values))

class EditPrediction(webapp.RequestHandler):
  def post(self,contest_id):
    try:
      logging.info("EditPrediction/%d" % int(contest_id))
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
    except:
      logging.info("caught some error")

    self.redirect('/contest/'+contest_id)

class FinishContest(webapp.RequestHandler):
  def post(self,contest_id):
    try:
      logging.info("FinishContest/%d" % int(contest_id))
      contest = Contest.get_by_id(long(contest_id))

      contest.final_value = float(self.request.get('final_value'))
      contest.put()

      prediction_query = db.GqlQuery("SELECT * FROM Prediction WHERE contest = :1 ORDER BY value DESC",
                                     contest)
      predictions = prediction_query.fetch(1000) # xxx fetch all?
      min_pred = 100000.0
      for prediction in predictions:
        prediction.winner = False
        prediction.put()
        delta = abs(prediction.value - contest.final_value) 
        if min_pred > delta:
          min_pred = delta
      if contest.final_value >= 0.0:
        for prediction in predictions:
          delta = abs(prediction.value - contest.final_value) 
          if min_pred == delta:
            prediction.winner = True
            prediction.put()
    except:
      logging.info("caught some error")

    self.redirect('/contest/'+contest_id)

class ViewUser(webapp.RequestHandler):
  def get(self,user_id):
    logging.info("ViewUser/%d" % int(user_id))
    the_user = MyUser.get_by_id(long(user_id))
    authorized_to_edit = the_user.user == users.get_current_user()
    prediction_query = db.GqlQuery("SELECT * FROM Prediction WHERE user = :1",
                                   #ORDER BY contest.close_date DESC",
                                   the_user)
    predictions = prediction_query.fetch(100) # xxx multiple pages?
    (logged_in_flag, login_url, login_url_linktext) = get_login_url_info(self)
    cur_user = get_my_current_user()
    template_values = {
      'the_user':           the_user,
      'predictions':        predictions,
      'authorized_to_edit': authorized_to_edit,
      'cur_user':           cur_user,
      'login_url':          login_url,
      'login_url_linktext': login_url_linktext,
      'logged_in_flag':     logged_in_flag,
      }
    path = os.path.join(os.path.dirname(__file__), 'user.html')
    self.response.out.write(template.render(path, template_values))

class UpdateUser(webapp.RequestHandler):
  def post(self,user_id):
     try:
       logging.info("UpdateUser/%d" % int(user_id))
       my_user = MyUser.get_by_id(long(user_id))
       if my_user.user == users.get_current_user():
         my_user.nickname = self.request.get('nickname')
         my_user.put()
         logging.info('updated nickname to %s' % (new_nickname))
     except:
       logging.info("caught some error")
     self.redirect('/user/'+user_id)



# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
application = webapp.WSGIApplication(
  [ ( '/',                    MainPage),       # GET list of contests
    ( '/about',               About),          # GET what is this site about?
    ( '/new_contest',         CreateContest),  # POST a new contest
    (r'/contest/(.*)',        ViewContest),    # GET list predictions
    (r'/new_prediction/(.*)', EditPrediction), # POST prediction
    (r'/finish/(.*)',         FinishContest),  # POST contest end
    (r'/user/(.*)',           ViewUser),       # GET user attributes
    (r'/update_user/(.*)',    UpdateUser),     # POST user attributes
    ],
  debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()

