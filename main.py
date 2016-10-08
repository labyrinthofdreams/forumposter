import codecs
import ConfigParser
import csv
import datetime
import os
import sched
import sys
import time
import bs4
import jinja2
import requests
from PIL import Image

config = ConfigParser.RawConfigParser()
config.read('config.ini')

USERNAME = config.get('forum', 'username').strip()
PASSWORD = config.get('forum', 'password').strip()
THREADID = config.get('forum', 'threadid').strip()
BASEURL = config.get('forum', 'forumurl').strip()
IMAGEDIR = config.get('general', 'imagedir').strip()

CSV_PATH = config.get('general', 'csvpath').strip()

NUM_POSTS = config.getint('general', 'numposts')
POST_DELAY = config.getint('general', 'delay')

if BASEURL[-1] != '/':
    sys.exit('URL must end with / character')

post_scheduler = sched.scheduler(time.time, time.sleep)
session = requests.Session()
tpl_env = jinja2.Environment(loader=jinja2.FileSystemLoader(u'templates'))

def number_format(number):
    """Formats numbers with thousands separators"""
    return u'{:,}'.format(number)

# Register function as jinja2 template filter
tpl_env.filters['number_format'] = number_format

def unicode_csv_reader(unicode_csv_data, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]

def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')

def calculate_size(oldw, oldh, towidth):
    if int(oldw) == 500:
        return (oldw, oldh)
    new_width = int(towidth)
    new_height = int((float(oldh) / oldw) * new_width)
    return (new_width, new_height)

def find_images(imgdir, entries):
    """Finds matching images for given entries in given directory. Matching is done by comparing IMDb IDs"""
    # Get images from current directory
    images = [{'name':os.path.splitext(f)[0], 'ext':os.path.splitext(f)[1]} for f in os.listdir(imgdir) if os.path.isfile(os.path.join(imgdir, f))]
    for e in entries:
        e['hasimage'] = any(img['name'] == e['imdbid'] for img in images)
        if e['hasimage']:
            foundimg = filter(lambda im: im['name'] == e['imdbid'], images)[0]
            e['imgname'] = foundimg['name'] + foundimg['ext']
            e['imgpath'] = os.path.join(imgdir, e['imgname'])
            # Get image size as well
            img = Image.open(e['imgpath'])
            e['imgsize'] = calculate_size(img.size[0], img.size[1], 500)
        else:
            e['imgsize'] = (0,0)

def load_entries(filename):
    entries = []
    with codecs.open(filename, 'rb', 'iso-8859-1') as f:
        try:
            lines = f.readlines()
            rows = []
            for row in unicode_csv_reader(lines):
                rows.append(row)
            header = rows.pop(0)
            for row in rows:
                entries.append(dict(zip(header, row)))
        except csv.Error as e:
            raise Exception(u'file {0}, line {1}: {2}'.format(filename, reader.line_num, e))
    return entries

def write_to_log(message):
    with codecs.open('out.txt', 'ab', 'utf-8') as f:
        f.write(message)
        f.write('\n')

def start_post_scheduler(delay, entries, num_posts):
    idx = 0
    num_entries = len(entries)
    def post_next(sc, delay, entries, num_posts, idx):
        if len(entries) == 0:
            return
        posts = entries[0:num_posts]
        composed = compose_post(posts)
        composed = ''.join(composed)
        composed = composed.encode('iso-8859-1')
        print composed
        try:
            submit_post(composed, THREADID)
            idx += len(posts)
            out = u'--- {0} [{1}/{2}] ---\n'.format(datetime.datetime.today().strftime(u'%H:%M:%S'), idx, num_entries)
            print out
            write_to_log(out)
            write_to_log(composed.decode('iso-8859-1'))
            next_entries = entries[num_posts:]
            if len(next_entries) == 0:
                return
            else:
                sc.enter(delay, 1, post_next, (sc, delay, next_entries, num_posts, idx))
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout) as e:
            # DNS failure, refused connections, HTTP Errors and Timeouts...
            # Try again in 5 minutes
            err_msg = '--- Request error ---\n{0}\n\nTrying again in 5 minutes.\n'.format(str(e))
            print err_msg
            write_to_log(err_msg)
            sc.enter(5*60, 1, post_next, (sc, delay, entries, num_posts, idx))
        except Exception as e:
            # Other exceptions will just quit the program
            import sys
            type_, value_, traceback_ = sys.exc_info()
            import traceback
            print traceback.format_tb(traceback_)
            print 'error'
            print e
            return
    post_scheduler.enter(0, 1, post_next, (post_scheduler, delay, entries, num_posts, idx))
    post_scheduler.run()

def compose_post(entries):
    tpl = tpl_env.get_template(u'forumpost.html')
    return tpl.render(entries=entries)

def submit_post(message, threadid):
    # Check for errors in the submission (http, timeout, etc)
    def get_param_safe(html, name):
        try:
            return html.find('input', attrs={'name':name})['value']
        except:
            return ''

    url = BASEURL + 'topic/{0}/1'.format(threadid)
    response = session.get(url)
    parsed_html = bs4.BeautifulSoup(response.text, 'html.parser')
    params = {'mode': get_param_safe(parsed_html, 'mode'),
              'type': get_param_safe(parsed_html, 'type'),
              'f': get_param_safe(parsed_html, 'f'),
              't': get_param_safe(parsed_html, 't'),
              'sig': get_param_safe(parsed_html, 'sig'),
              'emo': get_param_safe(parsed_html, 'emo'),
              'merge_posts': get_param_safe(parsed_html, 'merge_posts'),
              'x': '25',
              'sd': '1',
              'xc': get_param_safe(parsed_html, 'xc'),
              'ast': get_param_safe(parsed_html, 'ast'),
              'task': get_param_safe(parsed_html, 'task'),
              'r': get_param_safe(parsed_html, 'r'),
              'r2': get_param_safe(parsed_html, 'r2'),
              'qhash': get_param_safe(parsed_html, 'qhash'),
              'p': get_param_safe(parsed_html, 'p'),
              'post': message
              }
    headers = {u'content-type': u'application/x-www-form-urlencoded'}
    try:
        posturl = BASEURL + 'post/'
        response = session.post(posturl, data=params, headers=headers, cookies=session.cookies)
        if response.status_code != requests.codes.ok:
            raise response.raise_for_status()
        elif len(response.cookies) == 0:
            pass
            #raise Exception(u'Post failed. Not logged in!')
    except:
        raise

def login(username, password):
    if username is None or password is None:
        raise Exception(u'Username and password must be set')
    args = {u'uname': username,
            u'pw': password,
            u'cookie_on': u'1',
            u'tm': datetime.datetime.today().strftime(u'4/4/2014 3:%M:%S PM')
            }
    print args
    headers = {u'content-type': u'application/x-www-form-urlencoded'}
    url = BASEURL + u'login/log_in/'
    resp = session.post(url, data=args, headers=headers, allow_redirects=False)
    print resp.cookies
    write_to_log(resp.text)
    if resp.status_code != requests.codes.ok:
        pass
        #raise resp.raise_for_status()
    elif len(resp.cookies) == 0:
        raise Exception(u'Login failed. Invalid username and/or password')

if __name__ == '__main__':
    try:
        login(USERNAME, PASSWORD)
        entries = load_entries(CSV_PATH)
        entries.reverse()
        if IMAGEDIR:
            find_images(IMAGEDIR, entries)
        # Verify that we're not accidentally posting the first entry
        print '=' * 80
        print compose_post([entries[0]])
        print '=' * 80
        answer = raw_input('Is this the first entry you want to post? [y/n]: ')
        if answer.lower() == 'y':
            start_post_scheduler(POST_DELAY, entries, NUM_POSTS)
    except Exception, e:
        import traceback
        traceback.format_exc()
        print str(e)

