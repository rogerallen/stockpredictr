#!/usr/bin/env python2.7
#
# Tests for stockpredictr appengine code.

# Basic idea is to save 'golden' versions of the website that have
# been inspected to be correct.

# When you expect the code to not change the output, run tests
# normally & they diff 'current' vs. 'gold'.  No diffs == pass.

# When the website output changes, these changes are 'gilded' by
# putting new pages into the 'lead' directory, inspecting them and
# when they are correct, copying them to the 'gold' directory.

import json
import logging
import md5
import re
import sys
import unittest
import urllib
import urllib2
sys.path.append("../stockpredictr")
from stockpredictr_config import G_LIST_SIZE

# global switch to write gilded files
GILD = False
# global for the sitename.  put in config file someday
SITE = 'http://localhost:8081/'

# FIXME
FUTYEAR = '2015'

# not sure this is necessary
USERAGENT = "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; en-US; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3,gzip(gfe)"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def login_cookie(email,admin_flag):#,cookie_id):
    """ return string in this format
      dev_appserver_login="test@example.com:True:185804764220139124119"
    """
    login_str = email+':'
    login_str += str(admin_flag)+':'
    # found in https://github.com/avsm/py-shelf/blob/master/dev_appserver_login.py
    user_id_digest = md5.new(email.lower()).digest()
    user_id = '1' + ''.join(['%02d' % ord(x) for x in user_id_digest])[:20]
    login_str += user_id #cookie_id
    cookie_str = 'dev_appserver_login="'+login_str+'"'
    return cookie_str

def user_cookie(index=None,admin_flag=False):
    istr=""
    if index:
        istr=str(index)
    return login_cookie('test'+istr+'@example.com',admin_flag)#,COOKIE_ID)

def admin_cookie(index=None):
    return user_cookie(index,True)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_comparison(url, gold_file_name, values=None, headers={}):
    """Common routine to open a url and return the lines from both the
    fetched web page and the golden comparison file.  If the global
    GILD is set, then the page is saved as the golden comparison.
    """
    if values:
        data = urllib.urlencode(values)
    else:
        data = None
    request  = urllib2.Request(url,data=data,headers=headers)
    response = urllib2.urlopen(request)
    the_page = response.read()
    if GILD:
        gold_page = open('lead/'+gold_file_name,'w')
        print >>gold_page, the_page,
        gold_page.close()
        return ([],[])
    else:
        gold_page = open('gold/'+gold_file_name).read()
        the_page_lines = the_page.split('\n')
        gold_page_lines = gold_page.split('\n')
        return (the_page_lines, gold_page_lines)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def fetch_url(url, values=None, headers={}):
    """Common routine to open a url and return the lines from the page..
    """
    if values:
        data = urllib.urlencode(values)
    else:
        data = None
    request  = urllib2.Request(url,data=data,headers=headers)
    response = urllib2.urlopen(request)
    the_page = response.read()
    return the_page

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def page_name(where,tag=''):
    """given the output of self.id() e.g. __main__.TestBasics.test000RootNoLogin,
    create a good webpage name.  tag is an optional extra argument"""
    name = where + tag + '.html'
    name = name.replace('__main__.TestBasics.test', 'basic_')
    name = name.replace('__main__.TestLong.test',   'long_')
    return name

# ======================================================================
json_re = re.compile("\s+json\s=\s+(.*)\s;")
class TestBasics(unittest.TestCase):
    def checkEqual(self,the_page_lines,gold_page_lines):
        for i in range(len(max(the_page_lines,gold_page_lines))):
            gold_re_match = re.match(json_re,gold_page_lines[i])
            page_re_match = re.match(json_re,the_page_lines[i])
            if gold_re_match:
                gold_json_string = gold_re_match.group(1)
                if page_re_match is None:
                    self.assertEqual(the_page_lines[i],gold_page_lines[i])
                else:
                    page_json_string = page_re_match.group(1)
                    page_json = json.loads(page_json_string)
                    gold_json = json.loads(gold_json_string)
                    self.assertEqual(page_json,gold_json)
            else:
                self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test000RootNoLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
           SITE,
           page_name(self.id())
           )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test001RootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test002RootAddContestBadStock(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol': 'fail'},
            headers={'Cookie':user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test003RootAddContestMissingDate(self):
        # TODO - this error is not that great
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       '',
                    'month':      '',
                    'day':        '',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test004RootAddContestDateInPast(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       '2010',
                    'month':      '5',
                    'day':        '1',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test005RootAddContestPublic(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       FUTYEAR,
                    'month':      '9',
                    'day':        '1',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test006RootAddContestPrivate(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       FUTYEAR,
                    'month':      '9',
                    'day':        '2',
                    'private':    '1',
                    'passphrase': 'password'
                    },
            headers={'Cookie':user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test007AddContestNoLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       FUTYEAR,
                    'month':      '9',
                    'day':        '1',
                    'private':    '',
                    'passphrase': ''
                    },
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test008RootAddContestOnWeekend(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       FUTYEAR,
                    'month':      '2',
                    'day':        '7',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test010AboutNoLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'about',
            page_name(self.id()),
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test01zRootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test020UserWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test021BadUserUrl(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1a3x',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test022UserWithOtherLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test022aUserNoLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1',
            page_name(self.id()),
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test023UserWithOtherLoginTryChangeNickname(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1',
            page_name(self.id()),
            values={'nickname': 'must fail'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)  #FIXME
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test024UserChangeNickname(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1',
            page_name(self.id()),
            values={'nickname': 'mr test'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test025BadUserUrlChangeNickaname(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1a3x',
            page_name(self.id()),
            values={'nickname': 'duh'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test02zRootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test030ContestBadUrl(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/1w2',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test0301ContestNoUser(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test031ContestMakePrediction(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            values={'prediction':'12'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test032ContestMakePrediction2(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            values={'prediction':'13'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie(2)
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test033ContestMakeBadPrediction(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            values={'prediction':'1xz3'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie(2)
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test0330ContestMakeNoUserPrediction(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            values={'prediction':'13'},
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test033zRootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test034ContestFinish(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            values={'final_value':'12.0625'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test034zRootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test035ContestFinishPoorly(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            values={'final_value':'1x2.0z625'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test036ContestReopen(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            values={'final_value':'-2'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test036zRootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test037ContestPrivateNotAllowed(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/22',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test038ContestPrivateGiveBadPassphrase(self):
        logging.info("test038ContestPrivateGiveBadPassphrase")
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/22',
            page_name(self.id()),
            values={'passphrase':'blahblah'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test038aContestPrivateNoUser(self):
        logging.info("test038aContestPrivateNoUser")
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/22',
            page_name(self.id()),
            values={'passphrase':'password'},
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test039ContestPrivateGiveGoodPassphrase(self):
        logging.info("test039ContestPrivateGiveGoodPassphrase")
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/22',
            page_name(self.id()),
            values={'passphrase':'password'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test03aContestPrivateMakePrediction(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/22',
            page_name(self.id()),
            values={'prediction':'13'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie(2)
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test03bContestPrivateChangePrediction(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/22',
            page_name(self.id()),
            values={'prediction':'12.5'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie(2)
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test03cContestCheckStockPrices(self):
        for (i,v) in enumerate(['13.0001','1','11.1','12.52','13.99999999999999']):
            fetch_url(
                SITE+'contest/21',
                values={'prediction':v},
                headers={'Cookie': user_cookie(i+2)})
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            values={'prediction':'13'},
            headers={'Cookie': user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test03dContestExactlyOnePageOfPredictions(self):
        num_pred = G_LIST_SIZE
        for (i,v) in enumerate(range(num_pred)):
            fetch_url(
                SITE+'contest/21',
                values={'prediction': 10.0+v/10.0 },
                headers={'Cookie':    user_cookie(i) })
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id()),
            headers={'Cookie': user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test03zRootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test040MissingUrl(self):
        # no page output
        self.assertRaises(urllib2.HTTPError,
                          get_comparison,
                          SITE+'gobbledygook',
                          page_name(self.id()),
                          None,
                          {'User-Agent': USERAGENT,
                           'Cookie':user_cookie()
                           }
                          )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test050FinishContestsFail(self):
        # no page output
        self.assertRaises(urllib2.HTTPError,
                          get_comparison,
                          SITE+'admin/finish_any',
                          page_name(self.id()),
                          None,
                          {'User-Agent': USERAGENT,
                           'Cookie':user_cookie()
                           }
                          )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test051FinishContests(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'admin/finish_any',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':admin_cookie()
                     }
            )
        # this makes comparison easier
        the_page_lines += ['']
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test05zRootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test060ContestsBadIndex(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=x3',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class TestLong(unittest.TestCase):
    def checkEqual(self,the_page_lines,gold_page_lines):
        for i in range(len(max(the_page_lines,gold_page_lines))):
            gold_re_match = re.match(json_re,gold_page_lines[i])
            page_re_match = re.match(json_re,the_page_lines[i])
            if gold_re_match:
                gold_json_string = gold_re_match.group(1)
                if page_re_match is None:
                    self.assertEqual(the_page_lines[i],gold_page_lines[i])
                else:
                    page_json_string = page_re_match.group(1)
                    page_json = json.loads(page_json_string)
                    gold_json = json.loads(gold_json_string)
                    self.assertEqual(page_json,gold_json)
            else:
                self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # extra long test
    def test000AddLotsOfTests(self):
        print  >>sys.stderr, "\ntest long:",
        # add a gob of contests
        for month in [ '10', '11', '12' ]:
            for day in range(30):
                fetch_url(
                    SITE,
                    values={'symbol':     'test',
                            'year':       FUTYEAR,
                            'month':      month,
                            'day':        str(day),
                            'private':    '',
                            'passphrase': ''
                            },
                    headers={'Cookie':user_cookie()}
                    )
        # see only 25 on homepage
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id(),'A'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=0',
            page_name(self.id(),'B'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=25',
            page_name(self.id(),'C'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=50',
            page_name(self.id(),'D'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=75',
            page_name(self.id(),'E'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        self.checkEqual(the_page_lines, gold_page_lines)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test001ContestAddLotsOfPredictions(self):
        for (i,v) in enumerate(range(55)):
            fetch_url(
                SITE+'contest/21',
                values={'prediction': 10.0+v/10.0 },
                headers={'Cookie':    user_cookie(i) })
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21',
            page_name(self.id(),'A'),
            headers={'Cookie': user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21?i=25',
            page_name(self.id(),'B'),
            headers={'Cookie': user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)

        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/21?i=50',
            page_name(self.id(),'C'),
            headers={'Cookie': user_cookie()}
            )
        self.checkEqual(the_page_lines, gold_page_lines)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
    print "Expecting clear-config app-engine already active..."
    if len(sys.argv) > 1 and 'gild' in sys.argv:
        print "GILD MODE ON.  Writing files to the 'lead' directory."
        GILD=True
        sys.argv.remove('gild')
    unittest.main()
