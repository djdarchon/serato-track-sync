#!/usr/bin/env python3
import configparser
from threading import Thread
from polling2 import poll
from time import sleep, time
import os, socket, sys

# define global variables
track = ''
sock = None

if getattr(sys, 'frozen', False) and sys.platform == "darwin":
    bundle_dir = os.path.dirname(sys.executable)  # sys._MEIPASS
    config_file = os.path.abspath(os.path.join(bundle_dir, "bin/config.ini"))
else:
    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "bin/config.ini"))

config = configparser.ConfigParser()

class ConfigFile:  # read and write to config.ini
    def __init__(self, cparser, cfile):
        self.cparser = cparser
        self.cfile = cfile

        try:
            self.cparser.read(self.cfile)
            self.cparser.sections()

            self.libpath = config.get('Settings', 'libpath')
            self.url = config.get('Settings', 'url')
            self.file = config.get('Settings', 'file')
            self.interval = config.get('Settings', 'interval')
            self.delay = config.get('Settings', 'delay')
            self.a_pref = config.get('Settings', 'a_pref').replace("|_0", " ")
            self.a_suff = config.get('Settings', 'a_suff').replace("|_0", " ")
            self.s_pref = config.get('Settings', 's_pref').replace("|_0", " ")
            self.s_suff = config.get('Settings', 's_suff').replace("|_0", " ")
            self.interval = float(self.interval)
            self.delay = float(self.delay)
        except configparser.NoOptionError:
            pass

target = None
global_iter = 0

def main():  # track polling process
    global track
    global sock
    global target
    global global_iter
    while True:
        conf = ConfigFile(config, config_file)

        # get poll interval and then poll
        interval = 1
        if conf.file.startswith("udp://"):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            port = conf.file.split(":")[2]
            sock.bind(("0.0.0.0",int(port)))
        new = gettrack(ConfigFile(config, config_file), track)

        if new is not False:
            target = new

        if target is not None:
            writetrack(conf.file, target)

        sleep(1)
        global_iter = global_iter +1

def gettrack(c, t):  # get last played track
    conf = c
    tk = t

    sera_dir = conf.libpath
    hist_dir = os.path.abspath(os.path.join(sera_dir, "History"))
    sess_dir = os.path.abspath(os.path.join(hist_dir, "Sessions"))
    tdat = getlasttrack(sess_dir)
    if tdat is False:
        return False

    # cleanup
    tdat = str(tdat)
    tdat = tdat.replace("['", "").replace("']", "").replace("[]", "").replace("\\n", "").replace("\\t", "") \
        .replace("[\"", "").replace("\"]", "")
    tdat = tdat.strip()

    if tdat == "":
        return False

    t = tdat.split(" - ", 1)

    if t[0] == '.':
        artist = ''
    else:
        artist = c.a_pref + t[0] + c.a_suff

    if t[1] == '.':
        song = ''
    song = c.s_pref + t[1] + c.s_suff

    # handle multiline
    tdat = "artist="+artist+" song="+song

    if tdat != tk:
        return tdat
    else:
        return False


def getsessfile(directory, showlast=True):
    ds = os.path.abspath(os.path.join(directory, ".DS_Store"))

    if os.path.exists(ds):
        os.remove(ds)

    path = directory
    os.chdir(path)
    files = sorted(os.listdir(os.getcwd()), key=os.path.getmtime)
    first = files[0]
    last = files[-1]

    if showlast:
        file = os.path.abspath(os.path.join(directory, last))
    else:
        file = os.path.abspath(os.path.join(directory, first))

    file_mod_age = time() - os.path.getmtime(file)

    if file_mod_age > 10:  # 2592000:
        return False
    else:
        sleep(0.5)
        return file


def getlasttrack(s):  # function to parse out last track from binary session file
    # get latest session file
    sess = getsessfile(s)
    if sess is False:
        return False

    # open and read session file
    while os.access(sess, os.R_OK) is False:
        sleep(0.5)

    with open(sess, "rb") as f:
        raw = f.read()

    # decode and split out last track of session file
    binstr = raw.decode('latin').rsplit('oent')  # split tracks
    byt = binstr[-1]  # last track chunk
    # print(byt)
    # determine if playing
    if (byt.find('\x00\x00\x00-') > 0 or  # ejected or is
            byt.find('\x00\x00\x00\x003') > 0):  # loaded, but not played
        return False

    # parse song
    sx = byt.find('\x00\x00\x00\x00\x06')  # field start

    if sx > 0:  # field end
        sy = byt.find('\x00\x00\x00\x00\x07')
        if sy == -1:
            sy = byt.find('\x00\x00\x00\x00\x08')
        if sy == -1:
            sy = byt.find('\x00\x00\x00\x00\t')
        if sy == -1:
            sy = byt.find('\x00\x00\x00\x00\x0f')

    # parse artist
    ax = byt.find('\x00\x00\x00\x00\x07')  # field start

    if ax > 0:
        ay = byt.find('\x00\x00\x00\x00\x08')  # field end
        if ay == -1:
            ay = byt.find('\x00\x00\x00\x00\t')
        if ay == -1:
            ay = byt.find('\x00\x00\x00\x00\x0f')

    # cleanup and return
    if ax > 0:
        bin_artist = byt[ax + 4:ay].replace('\x00', '')
        str_artist = bin_artist[2:]
    else:
        str_artist = '.'

    if sx > 0:
        bin_song = byt[sx + 4:sy].replace('\x00', '')
        str_song = bin_song[2:]
    else:
        str_song = '.'

    t_info = str(str_artist).strip() + " - " + str(str_song).strip()
    t_info = t_info

    return t_info

iter=0

def writetrack(f, t=""):  # write new track info
    global sock
    global iter
    file = f
    if (file.startswith("udp://")):
        # UDP packet mode
        file = file[6:].split(":")
        t = "seq="+str(iter)+" "+t
        sock.sendto(t.encode('utf-8'), (file[0], int(file[1])))
        iter = iter+1
    else:
        with open(file, "w", encoding='utf-8') as f:
            f.write(t)

main()
