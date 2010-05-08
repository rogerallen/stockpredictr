#!/usr/bin/env python
import unittest
import urllib
import urllib2
import sys

# global switch to write gilded files
GILD=False
# global for the sitename
SITE='http://localhost:8080/'
# TODO these may only work for me.  prob should be in config file, not
# checked in
NOADMIN_COOKIE = 'dev_appserver_login="test@example.com:False:185804764220139124118"'
ADMIN_COOKIE = 'dev_appserver_login="test@example.com:True:185804764220139124118"'
USERAGENT = "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; en-US; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3,gzip(gfe)"

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
        gold_page = open(gold_file_name,'w')
        print >>gold_page, the_page,
        gold_page.close()
        return ([],[])
    else:
        gold_page = open(gold_file_name).read()
        the_page_lines = the_page.split('\n')
        gold_page_lines = gold_page.split('\n')
        return (the_page_lines, gold_page_lines)
    
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class TestBasics(unittest.TestCase):

    def test000RootNoLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'gold/basics000.html'
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test001RootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'gold/basics001.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test002RootAddBadStock(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'gold/basics002.html',
            values={'symbol': 'nxxx'},
            headers={'Cookie':NOADMIN_COOKIE}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    def test003RootAddMissingDate(self):
        # TODO - this error is not that great
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'gold/basics003.html',
            values={'symbol':     'test',
                    'year':       '',
                    'month':      '',
                    'day':        '',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':NOADMIN_COOKIE}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    def test004RootAddDateInPast(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'gold/basics004.html',
            values={'symbol':     'test',
                    'year':       '2010',
                    'month':      '5',
                    'day':        '1',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':NOADMIN_COOKIE}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    def test005RootAddPublic(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'gold/basics005.html',
            values={'symbol':     'test',
                    'year':       '2011',
                    'month':      '10',
                    'day':        '10',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':NOADMIN_COOKIE}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
    print "You better have google app engine running."
    print "You need to start from a clear config, too"
    if len(sys.argv) > 1 and 'gild' in sys.argv:
        print "GILD MODE ON"
        GILD=True
        sys.argv.remove('gild')
    unittest.main()
