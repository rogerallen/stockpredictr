#!/usr/bin/env python
import unittest
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

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_comparison(url, gold_file_name, cookie=None):
    """Common routine to open a url and return the lines from both the
    fetched web page and the golden comparison file.  If the global
    GILD is set, then the page is saved as the golden comparison.
    """
    if cookie:
        headers = { 'Cookie': cookie }
    else:
        headers = {}
    request  = urllib2.Request(url,headers=headers)
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

    def testRootNoLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'gold/basics000.html'
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def testRootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'gold/basics001.html',NOADMIN_COOKIE
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
    print "You better have google app engine running."
    print "You need to clear the cache, too"
    if len(sys.argv) > 1 and 'gild' in sys.argv:
        print "GILD MODE ON"
        GILD=True
        sys.argv.remove('gild')
    unittest.main()
