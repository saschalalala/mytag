#!/usr/bin/env python
#-*- coding: utf-8 -*-

""" mytag: Python music tagger and file organiser
    ----------------Authors----------------
    Lachlan de Waard <lachlan.00@gmail.com>
    ----------------Licence----------------
    GNU General Public License version 3

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import os
import shutil
import threading
import ConfigParser
import sys

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from xdg.BaseDirectory import xdg_config_dirs

# python-eyeD3 required for editing and loading tags
try:
    import eyeD3
    TAG_SUPPORT = True
except ImportError:
    TAG_SUPPORT = False

# quit if using python3
if sys.version[0] == 3:
    raise Exception('not python3 compatible, please use python 2.x')


MEDIA_TYPES = ['.m4a', '.flac', '.ogg', '.mp2', '.mp3', '.wav', '.spx']
YR_SPLIT = ['-', '/', '\\']
MUSIC_TAGS = ['%artist%', '%albumartist%', '%album%', '%year%',
                 '%title%', '%disc%', '%track%', '%genre%', '%comment%']
CONFIG = xdg_config_dirs[0] + '/mytag.conf'
ICON_DIR = '/usr/share/icons/gnome/'


class WorkerThread(threading.Thread):
    """ run a separate thread to the ui """
    def __init__(self, notify_window):
        """Init Worker Thread Class."""
        super(WorkerThread, self).__init__()
        self._notify_window = notify_window
        self._want_abort = 0
        self._stop = threading.Event()
        self.setDaemon(True)
        self.returntext = None
        self.source = None
        self.files = None
        self.destin = None
        self.destinformat = None
        self.backupdir = None
        self.stoponerrors = None
        self.movemedia = None
        self.stop = None
        self.start()
        return None

    def run(self, *args):
        """ run file organisation in a background thread """
        self.returntext = True
        self.source = None
        self.files = None
        self.destin = None
        self.destinformat = None
        self.stoponerrors = None
        self.movemedia = None
        if args:
            if args[0]:
                self.source = args[0]
            if args[1]:
                self.files = args[1]
            if args[2]:
                self.destin = args[2]
            if args[3]:
                self.destinformat = args[3].lower()
            if args[4]:
                if args[4] == 'True':
                    self.stoponerrors = True
                else:
                    self.stoponerrors = False
            if args[5]:
                if args[5] == 'True':
                    self.movemedia = True
                else:
                    self.movemedia = False
            if self.destin:
                self.backupdir = os.path.normpath(self.destin + '/BACKUP/')
            self.foldersearch(self.source)
        return self.returntext

    def foldersearch(self, folder):
        """ Start searching the source folder looking for music  """
        self.stop = False
        try:
            tmpsort = os.listdir(folder)
            tmpsort.sort(key=lambda y: y.lower())
        except OSError:
            self.returntext = folder
            return False
        except TypeError:
            print folder
            self.returntext = folder
            return False
        # search for files and folders in the current dir
        for items in tmpsort:
            while Gtk.events_pending():
                Gtk.main_iteration()
            if not self.stop:
                try:
                    path = os.path.normpath((folder).decode('utf-8') + u'/' +
                                            (items).decode('utf-8'))
                except UnicodeEncodeError:
                    path = os.path.normpath(folder + '/' + items)
                if os.path.isdir(path) and os.listdir(path) == []:
                    tmp_dir = path
                    # remove empty folders and search backwards for more
                    while os.listdir(tmp_dir) == []:
                        os.rmdir(tmp_dir)
                        tmp_dir = os.path.split(tmp_dir)[0]
                if os.path.isdir(path) and (self.backupdir !=
                                                os.path.dirname(path)):
                    # remove '.mediaartlocal' folders
                    if os.path.basename(path) == '.mediaartlocal':
                        for items in os.listdir(path):
                            os.remove(os.path.join(path + u'/' + items))
                        os.rmdir(path)
                    else:
                        # search subfolder for media
                        self.foldersearch(path)
                elif os.path.isfile(path) and (path[(path.rfind('.')):] in
                                                MEDIA_TYPES):
                    # organise media file
                    self.organisefiles(path)
        return

    def organisefiles(self, files):
        """ sort media when found """
        # set output path and fill variables with the tag value
        currentdestin = os.path.normpath(self.destin + u'/' + self.destinformat)
        currentdestin = self.fill_string(files, currentdestin)
        stringtest = False
        for tags in MUSIC_TAGS:
            # if a tag variable is found in the output do not continue
            if tags in currentdestin:
                stringtest = True
                if self.stoponerrors:
                    self.returntext = [tags, os.path.dirname(files)]
                    self.stop = True
                return False
        if not files == currentdestin:
            while Gtk.events_pending():
                Gtk.main_iteration()
            # create a backup when conflicts are found
            if os.path.isfile(currentdestin):
                backupdestin = os.path.normpath(self.backupdir + '/' +
                                    self.destinformat)
                backup = self.fill_string(files, backupdestin)
                if os.path.isfile(backup) and not files == backup:
                    count = 0
                    tmp_path = backup
                    while os.path.isfile(backup):
                        backup = tmp_path
                        backup = (tmp_path[:(tmp_path.rfind('.'))] +
                                    str(count) + tmp_path[(
                                    tmp_path.rfind('.')):])
                        count = count + 1
                # update destination to the non-conflicting destination
                currentdestin = backup
            if not os.path.isfile(currentdestin) and not stringtest:
                # create directoy for output file if not found
                if not os.path.isdir(os.path.dirname(currentdestin)):
                    os.makedirs(os.path.dirname(currentdestin))
                # move file and run cleanup
                shutil.move(files, currentdestin)
                self.folder_cleanup(files, currentdestin)
        return

    def folder_cleanup(self, sourcedir, destindir):
        """ remove empty folders and move non-media with your media file """
        if not os.path.isdir(sourcedir):
            sourcedir = os.path.dirname(sourcedir)
        if not os.path.isdir(destindir):
            destindir = os.path.dirname(destindir)
        if not os.listdir(sourcedir) == []:
            tmp_dir = os.listdir(sourcedir)
            tmp_dir.sort(key=lambda y: y.lower())
            found_media = False
            # check for left over media files
            for files in tmp_dir:
                if not os.path.isdir(sourcedir + '/' + files) and not (
                                        destindir == sourcedir):
                    filelist = files[(files.rfind('.')):]
                    if filelist in MEDIA_TYPES:
                        found_media = True
            if self.movemedia:
                # move non-media when no other media files are in the folder
                for files in tmp_dir:
                    while Gtk.events_pending():
                        Gtk.main_iteration()
                    filelist = files[(files.rfind('.')):]
                    if not found_media and not os.path.isdir(sourcedir +
                                                               '/' + files):
                        if not filelist in MEDIA_TYPES:
                            mvdest = destindir + '/' + files
                            mvsrc = sourcedir + '/' + files
                            # move non-media files when no more music found.
                            shutil.move(mvsrc, mvdest)
        # Remove empty folders, if you have moved out the last file.
        if os.listdir(sourcedir) == []:
            tmp_dir = sourcedir
            while os.listdir(tmp_dir) == []:
                os.rmdir(tmp_dir)
                tmp_dir = os.path.dirname(tmp_dir)
        return

    def fill_string(self, files, destin):
        """ function to replace the variables with the tags for each file """
        tmp_title = None
        tmp_artist = None
        tmp_album = None
        tmp_albumartist = None
        tmp_genre = None
        tmp_track = None
        tmp_disc = None
        tmp_year = None
        tmp_comment = None
        try:
            item = eyeD3.Tag()
            item.link(files)
            item.setVersion(eyeD3.ID3_V2_4)
            item.setTextEncoding(eyeD3.UTF_8_ENCODING)
        except:
            # Tag error
            item = None
        # pull tag info for the current item
        if item:
            tmp_title = item.getTitle()
            if tmp_title == 'None':
                tmp_title = None
            if tmp_title:
                tmp_title = tmp_title.replace('/', '_')
            tmp_artist = item.getArtist('TPE1')
            if tmp_artist == 'None':
                tmp_artist = None
            if tmp_artist:
                tmp_artist = tmp_artist.replace('/', '_')
            tmp_album = item.getAlbum()
            if tmp_album == 'None':
                tmp_album = None
            if tmp_album:
                tmp_album = tmp_album.replace('/', '_')
            tmp_albumartist = item.getArtist('TPE2')
            if tmp_albumartist == 'None':
                tmp_albumartist = None
            if tmp_albumartist:
                tmp_albumartist = tmp_albumartist.replace('/', '_')
            try:
                tmp_genre = str(item.getGenre())
            except eyeD3.tag.GenreException:
                tmp_genre = None
            if tmp_genre == 'None':
                tmp_genre = None
            if tmp_genre:
                tmp_genre = tmp_genre.replace('/', '_')
                if ')' in tmp_genre:
                    tmp_genre = tmp_genre.split(')')[1]
            tmp_track = str(item.getTrackNum()[0])
            if tmp_track == 'None':
                tmp_track = None
            if tmp_track:
                if '/' in tmp_track:
                    tmp_track = tmp_track.split('/')[0]
                if len(tmp_track) == 1:
                    tmp_track = '0' + str(tmp_track)
                if len(tmp_track) > 2:
                    tmp_track = tmp_track[:2]
            tmp_disc = str(item.getDiscNum()[0])
            if tmp_disc == 'None':
                tmp_disc = None
            if tmp_disc:
                if '/' in tmp_disc:
                    tmp_disc = tmp_disc.split('/')[0]
                if len(tmp_disc) == 2:
                    tmp_disc = tmp_disc[-1]
            tmp_year = item.getYear()
            if tmp_year == 'None':
                tmp_year = None
            tmp_comment = item.getComment()
            if tmp_comment == 'None':
                tmp_comment = None
            if tmp_comment:
                tmp_comment = tmp_comment.replace('/', '_')
            # replace temp strings with actual tags
            if tmp_title:
                destin = destin.replace('%title%', tmp_title)
            if tmp_albumartist:
                destin = destin.replace('%albumartist%', tmp_albumartist)
            else:
                destin = destin.replace('%albumartist%', '%artist%')
            if tmp_artist:
                destin = destin.replace('%artist%', tmp_artist)
            if tmp_album:
                destin = destin.replace('%album%', tmp_album)
            if tmp_genre:
                destin = destin.replace('%genre%', tmp_genre)
            if tmp_track:
                destin = destin.replace('%track%', tmp_track)
            if tmp_disc:
                destin = destin.replace('%disc%', tmp_disc)
            if tmp_year:
                destin = destin.replace('%year%', tmp_year)
            if tmp_comment:
                destin = destin.replace('%comment%', tmp_comment)
            destin = destin + files[(files.rfind('.')):]
            while Gtk.events_pending():
                Gtk.main_iteration()
            return destin
        return


class MYTAG(object):
    """ browse folders and set tags using ui """
    def __init__(self):
        """ start mytag """
        self.builder = Gtk.Builder()
        self.builder.add_from_file("/usr/share/mytag/main.ui")
        self.builder.connect_signals(self)
        if not TAG_SUPPORT:
            self.popwindow = self.builder.get_object("popup_window")
            closeerror = self.builder.get_object("closepop")
            closeerror.connect("clicked", self.closeerror)
            self.popwindow.set_markup('MYTAG ERROR: Please install' +
                                        ' python-eyed3')
            self.popwindow.show()
            Gtk.main()
        else:
            self.worker = None
            if not self.worker:
                self.worker = WorkerThread(self)
            # get config info
            self.checkconfig()
            self.conf = ConfigParser.RawConfigParser()
            self.conf.read(CONFIG)
            self.homefolder = self.conf.get('conf', 'home')
            self.library = self.conf.get('conf', 'defaultlibrary')
            self.libraryformat = self.conf.get('conf', 'outputstyle')
            # backwards compatability for new config options
            try:
                self.stoponerror = self.conf.get('conf', 'stoponerror')
            except ConfigParser.NoOptionError:
                self.stoponerror = 'True'
            try:
                self.movenonmedia = self.conf.get('conf', 'movenonmedia')
            except ConfigParser.NoOptionError:
                self.movenonmedia = 'True'
            self.current_dir = self.homefolder
            self.current_files = None
            self.filelist = None
            # load main window items
            self.window = self.builder.get_object("main_window")
            self.settingsbutton = self.builder.get_object("settingsbutton")
            self.editbutton = self.builder.get_object("editbutton")
            self.backbutton = self.builder.get_object("backbutton")
            self.homebutton = self.builder.get_object("homebutton")
            self.gobutton = self.builder.get_object("gobutton")
            self.organisebutton = self.builder.get_object('organisebutton')
            self.folderlist = self.builder.get_object('folderstore')
            self.folderview = self.builder.get_object("folderview")
            self.fileview = self.builder.get_object("fileview")
            self.contentlist = self.builder.get_object('filestore')
            self.contenttree = self.builder.get_object('fileview')
            self.titlebutton = self.builder.get_object('titlebutton')
            self.artistbutton = self.builder.get_object('artistbutton')
            self.albumbutton = self.builder.get_object('albumbutton')
            self.albumartistbutton = self.builder.get_object('albumart' +
                                                                'istbutton')
            self.genrebutton = self.builder.get_object('genrebutton')
            self.trackbutton = self.builder.get_object('trackbutton')
            self.discbutton = self.builder.get_object('discbutton')
            self.yearbutton = self.builder.get_object('yearbutton')
            self.commentbutton = self.builder.get_object('commentbutton')
            self.titleentry = self.builder.get_object('titleentry')
            self.artistentry = self.builder.get_object('artistentry')
            self.albumentry = self.builder.get_object('albumentry')
            self.albumartistentry = self.builder.get_object('albumart' +
                                                                'istentry')
            self.genreentry = self.builder.get_object('genreentry')
            self.trackentry = self.builder.get_object('trackentry')
            self.discentry = self.builder.get_object('discentry')
            self.yearentry = self.builder.get_object('yearentry')
            self.commententry = self.builder.get_object('commententry')
            self.tagimage = self.builder.get_object('tagimage')
            self.currentdirlabel = self.builder.get_object('currentdirlabel')
            # load config window items
            self.confwindow = self.builder.get_object("config_window")
            self.libraryentry = self.builder.get_object('libraryentry')
            self.styleentry = self.builder.get_object('styleentry')
            self.homeentry = self.builder.get_object('homeentry')
            self.errorcheck = self.builder.get_object('errorcheck')
            self.mediacheck = self.builder.get_object('nonmediacheck')
            self.applybutton = self.builder.get_object("applyconf")
            self.closebutton = self.builder.get_object("closeconf")
            # load popup window items
            self.popwindow = self.builder.get_object("popup_window")
            self.popbutton = self.builder.get_object("closepop")
            self.successwindow = self.builder.get_object("success_window")
            self.successbutton = self.builder.get_object("closesuccess")
            # set tag items
            self.title = None
            self.artist = None
            self.album = None
            self.albumartist = None
            self.genre = None
            self.track = None
            self.disc = None
            self.year = None
            self.comment = None
            self.tracklist = None
            self.trackselection = None
            self.uibuttons = None
            # create lists and connect actions
            self.loadlists()
            self.connectui()
            self.run()

    def connectui(self):
        """ connect all the window wisgets """
        # main window actions
        self.window.connect("destroy", self.quit)
        self.window.connect("key-release-event", self.shortcatch)
        self.folderview.connect("key-press-event", self.keypress)
        self.fileview.connect("key-press-event", self.keypress)
        self.titleentry.connect("key-press-event", self.entrycatch)
        self.artistentry.connect("key-press-event", self.entrycatch)
        self.albumentry.connect("key-press-event", self.entrycatch)
        self.albumartistentry.connect("key-press-event", self.entrycatch)
        self.genreentry.connect("key-press-event", self.entrycatch)
        self.trackentry.connect("key-press-event", self.entrycatch)
        self.discentry.connect("key-press-event", self.entrycatch)
        self.yearentry.connect("key-press-event", self.entrycatch)
        self.commententry.connect("key-press-event", self.entrycatch)
        self.settingsbutton.connect("clicked", self.showconfig)
        self.editbutton.connect("clicked", self.loadselection)
        self.backbutton.connect("clicked", self.goback)
        self.homebutton.connect("clicked", self.gohome)
        self.gobutton.connect("clicked", self.savetags)
        self.organisebutton.connect("clicked", self.organisefolder)
        # config window actions
        self.applybutton.connect("clicked", self.saveconf)
        self.closebutton.connect("clicked", self.closeconf)
        # popup window actions
        self.popbutton.connect("clicked", self.closepop)
        self.successbutton.connect("clicked", self.closesuccess)
        # set up file and folder lists
        cell = Gtk.CellRendererText()
        foldercolumn = Gtk.TreeViewColumn("Select Folder:", cell, text=0)
        filecolumn = Gtk.TreeViewColumn("Select Files", cell, text=0)
        self.folderview.connect("row-activated", self.folderclick)
        self.folderview.append_column(foldercolumn)
        self.folderview.set_model(self.folderlist)
        self.fileview.connect("row-activated", self.loadselection)
        self.contenttree.append_column(filecolumn)
        self.contenttree.set_model(self.contentlist)
        self.tagimage.set_from_file(ICON_DIR + '16x16/emotes/face-plain.png')
        # list default dir on startup
        if not os.path.isdir(self.homefolder):
            os.makedirs(self.homefolder)
        self.listfolder(self.homefolder)
        return

    def run(self):
        """ show the main window and start the main GTK loop """
        self.window.show()
        Gtk.main()

    def loadlists(self):
        """ create/empty all the lists used for tagging """
        self.title = []
        self.artist = []
        self.album = []
        self.albumartist = []
        self.genre = []
        self.track = []
        self.disc = []
        self.year = []
        self.comment = []
        self.tracklist = []
        self.trackselection = [self.title, self.artist, self.album,
                               self.albumartist, self.genre, self.track,
                               self.disc, self.year, self.comment]
        self.uibuttons = [[self.titlebutton, self.titleentry],
                          [self.artistbutton, self.artistentry],
                          [self.albumbutton, self.albumentry],
                          [self.albumartistbutton, self.albumartistentry],
                          [self.genrebutton, self.genreentry],
                          [self.trackbutton, self.trackentry],
                          [self.discbutton, self.discentry],
                          [self.yearbutton, self.yearentry],
                          [self.commentbutton, self.commententry]]
        return

    def showconfig(self, *args):
        """ fill and show the config window """
        self.homeentry.set_text(self.homefolder)
        self.libraryentry.set_text(self.library)
        self.styleentry.set_text(self.libraryformat)
        if self.stoponerror == 'True':
            self.errorcheck.set_active(True)
        else:
            self.errorcheck.set_active(False)
        if self.movenonmedia == 'True':
            self.mediacheck.set_active(True)
        else:
            self.mediacheck.set_active(False)
        self.confwindow.show()
        return

    def saveconf(self, *args):
        """ save any config changes and update live settings"""
        self.conf.read(CONFIG)
        self.conf.set('conf', 'home', self.homeentry.get_text())
        self.conf.set('conf', 'defaultlibrary', self.libraryentry.get_text())
        self.conf.set('conf', 'outputstyle', self.styleentry.get_text())
        if self.errorcheck.get_active():
            self.conf.set('conf', 'stoponerror', 'True')
            self.stoponerror = 'True'
        else:
            self.conf.set('conf', 'stoponerror', 'False')
            self.stoponerror = 'False'
        if self.mediacheck.get_active():
            self.conf.set('conf', 'movenonmedia', 'True')
            self.movenonmedia = 'True'
        else:
            self.conf.set('conf', 'movenonmedia', 'False')
            self.movenonmedia = 'False'
        self.homefolder = self.homeentry.get_text()
        self.library = self.libraryentry.get_text()
        self.libraryformat = self.styleentry.get_text()
        # write to conf file
        conffile = open(CONFIG, "w")
        self.conf.write(conffile)
        conffile.close()
        return

    def checkconfig(self):
        """ create a default config if not available """
        if not os.path.isfile(CONFIG):
            conffile = open(CONFIG, "w")
            conffile.write("[conf]\nhome = " + os.getenv('HOME') +
                       "\ndefaultlibrary = " + os.getenv('HOME') +
                       "\noutputstyle = %albumartist%/(%year%) " +
                       "%album%/%disc%%track% - %title%\n" +
                       "stoponerror = True\nmovenonmedia = True\n")
            conffile.close()
        return

    def closeconf(self, *args):
        """ hide the config window """
        self.confwindow.hide()
        return

    def closeerror(self, *args):
        """ hide the error window """
        self.popwindow.destroy()
        Gtk.main_quit(*args)
        raise Exception('Please install python-eyed3')
        return

    def closepop(self, *args):
        """ hide the error popup window """
        self.popwindow.hide()
        return

    def closesuccess(self, *args):
        """ hide the organise completed window """
        self.successwindow.hide()
        return

    def loadselection(self, *args):
        """ load selected files into tag editor """
        model, fileiter = self.contenttree.get_selection().get_selected_rows()
        self.current_files = []
        for files in fileiter:
            tmp_file = self.current_dir + '/' + model[files][0]
            self.current_files.append(tmp_file)
        self.tagimage.set_from_file(ICON_DIR + '16x16/emotes/face-plain.png')
        self.loadtags(self.current_files)
        return

    def folderclick(self, *args):
        """ traverse folders on double click """
        model, treeiter = self.folderview.get_selection().get_selected()
        if treeiter:
            new_dir = self.current_dir + '/' + model[treeiter][0]
        if os.path.isdir(new_dir):
            self.listfolder(new_dir)
        return

    def gohome(self, *args):
        """ go to the defined home folder """
        self.clearopenfiles()
        self.listfolder(self.homefolder)

    def goback(self, *args):
        """ go back the the previous directory """
        back_dir = os.path.dirname(self.current_dir)
        self.clearopenfiles()
        self.listfolder(back_dir)
        return

    def keypress(self, actor, event):
        """ capture backspace key for folder navigation """
        if event.get_keycode()[1] == 22:
            self.goback()

    def shortcatch(self, actor, event):
        """ capture keys for shortcuts """
        test_mask = (event.state & Gdk.ModifierType.CONTROL_MASK ==
                       Gdk.ModifierType.CONTROL_MASK)
        if event.get_state() and test_mask:
            if event.get_keycode()[1] == 39:
                self.savetags()
            if event.get_keycode()[1] == 46:
                self.loadselection()
            if event.get_keycode()[1] == 56:
                self.goback()
            if event.get_keycode()[1] == 43:
                self.gohome()


    def entrycatch(self, actor, event):
        """ capture key presses to activate checkboxes """
        movement_keys = [22, 23, 36, 37, 50, 62, 64, 65, 66,
                            105, 108, 110, 111, 112, 113,
                            114, 115, 116, 117, 118, 119]
        test_mask = (event.state & Gdk.ModifierType.CONTROL_MASK ==
                       Gdk.ModifierType.CONTROL_MASK)
        # only set active when not using movement keys
        if not event.get_keycode()[1] in movement_keys and not test_mask:
            if actor == self.titleentry:
                if not self.titlebutton.get_active():
                    self.titlebutton.set_active(True)
            if actor == self.artistentry:
                if not self.artistbutton.get_active():
                    self.artistbutton.set_active(True)
            if actor == self.albumentry:
                if not self.albumbutton.get_active():
                    self.albumbutton.set_active(True)
            if actor == self.albumartistentry:
                if not self.albumartistbutton.get_active():
                    self.albumartistbutton.set_active(True)
            if actor == self.genreentry:
                if not self.genrebutton.get_active():
                    self.genrebutton.set_active(True)
            if actor == self.trackentry:
                if not self.trackbutton.get_active():
                    self.trackbutton.set_active(True)
            if actor == self.discentry:
                if not self.discbutton.get_active():
                    self.discbutton.set_active(True)
            if actor == self.yearentry:
                if not self.yearbutton.get_active():
                    self.yearbutton.set_active(True)
            if actor == self.commententry:
                if not self.commentbutton.get_active():
                    self.commentbutton.set_active(True)

    def quit(self, *args):
        """ stop the process thread and close the program"""
        self.worker._Thread__stop()
        self.confwindow.destroy()
        self.window.destroy()
        Gtk.main_quit(*args)
        return False

    def organisefolder(self, *args):
        """ send organise to the workerthread for processing """
        returnstring = self.worker.run(self.current_dir, self.filelist,
                                       self.library, self.libraryformat,
                                       self.stoponerror, self.movenonmedia)
        # notify for different errors
        if type(returnstring) == type(''):
            self.popwindow.set_markup('Error: Opening ' + returnstring)
            self.popwindow.show()
            self.listfolder(self.current_dir)
        if type(returnstring) == type([]):
            self.popwindow.set_markup('Error: ' + returnstring[0] +
                                      ' missing')
            self.popwindow.format_secondary_text(returnstring[1])
            self.popwindow.show()
            self.listfolder(self.current_dir)
        else:
            self.successwindow.show()
            if not os.path.isdir(self.current_dir):
                if os.path.isdir(os.path.dirname(self.current_dir)):
                    self.current_dir = os.path.dirname(self.current_dir)
                    self.listfolder(self.current_dir)
                else:
                    self.gohome()
            else:
                self.listfolder(self.current_dir)
        return True

    def savetags(self, *args):
        """ update the loaded files with new tags """
        count = 0
        tmp_changes = []
        # check for changes
        if self.current_files == tmp_changes:
            return False
        # add changes that are ticked in the UI
        while count < len(self.uibuttons):
            if self.uibuttons[count][0].get_active():
                tmp_changes.append([count, self.uibuttons[count][1].get_text()])
            count = count + 1
        save_fail = False
        # update tags for each file selected
        for files in self.current_files:
            tmp_title = None
            tmp_artist = None
            tmp_album = None
            tmp_albumartist = None
            tmp_genre = None
            tmp_track = None
            tmp_disc = None
            tmp_year = None
            tmp_comment = None
            try:
                item = eyeD3.Tag()
                item.link(files)
                item.setVersion(eyeD3.ID3_V2_4)
                item.setTextEncoding(eyeD3.UTF_8_ENCODING)
            except:
                item = None
                save_fail = True
            if item:
                # get the current tags
                current_title = item.getTitle()
                if current_title == 'None':
                    current_title = None
                current_artist = item.getArtist('TPE1')
                if current_artist == 'None':
                    current_artist = None
                current_album = item.getAlbum()
                if current_album == 'None':
                    current_album = None
                current_albumartist = item.getArtist('TPE2')
                if current_albumartist == 'None':
                    current_albumartist = None
                try:
                    current_genre = str(item.getGenre())
                except eyeD3.tag.GenreException:
                    current_genre = None
                if current_genre == 'None':
                    current_genre = None
                if current_genre:
                    current_genre = current_genre.replace('/', '_')
                    if ')' in current_genre:
                        current_genre = current_genre.split(')')[1]
                current_track = str(item.getTrackNum()[0])
                if '/' in current_track:
                    current_track = current_track.split('/')[0]
                if len(current_track) == 1:
                    current_track = '0' + str(current_track)
                if len(current_track) > 2:
                    current_track = current_track[:2]
                current_disc = str(item.getDiscNum()[0])
                if current_disc == 'None':
                    current_disc = None
                if current_disc:
                    if '/' in current_disc:
                        current_disc = current_disc.split('/')[0]
                    if len(current_disc) == 2:
                        current_disc = current_disc[-1]
                current_year = item.getYear()
                current_comment = item.getComment()
                if current_comment == 'None':
                    current_comment = None
                # get the changes from the UI
                for changes in tmp_changes:
                    if changes[0] == 0:
                        tmp_title = changes[1]
                    if changes[0] == 1:
                        tmp_artist = changes[1]
                    if changes[0] == 2:
                        tmp_album = changes[1]
                    if changes[0] == 3:
                        tmp_albumartist = changes[1]
                    if changes[0] == 4:
                        tmp_genre = changes[1]
                    if changes[0] == 5:
                        tmp_track = changes[1]
                    if changes[0] == 6:
                        tmp_disc = changes[1]
                    if changes[0] == 7:
                        tmp_year = changes[1]
                    if changes[0] == 8:
                        tmp_comment = changes[1]
                # compare and set changes if required
                if tmp_title != None and tmp_title != current_title:
                    item.setTitle(tmp_title)
                if tmp_artist != None and tmp_artist != current_artist:
                    item.setArtist(tmp_artist)
                if tmp_album != None and tmp_album != current_album:
                    item.setAlbum(tmp_album)
                if tmp_albumartist != None and (tmp_albumartist !=
                        current_albumartist):
                    item.setArtist(tmp_albumartist, 'TPE2')
                if tmp_genre != None and tmp_genre != current_genre:
                    item.setGenre(tmp_genre)
                if tmp_track != None and tmp_track != current_track:
                    item.setTrackNum([tmp_track, None])
                if tmp_disc != None and tmp_disc != current_disc:
                    item.setDiscNum([tmp_disc, None])
                if tmp_year != None and tmp_year != current_year:
                    item.setTextFrame('TDRC', tmp_year)
                    item.setTextFrame('TDRL', tmp_year)
                    item.setTextFrame('TYER', tmp_year)
                if tmp_comment != None and tmp_comment != current_comment:
                    item.removeComments()
                    item.addComment(tmp_comment)
                try:
                    # write changes to file
                    item.update(eyeD3.ID3_V2_4)
                except:
                    self.tagimage.set_from_file(ICON_DIR +
                                                '16x16/emotes/face-crying.png')
                    save_fail = True
                    print 'Tag Save Error'
                    print files
                    return False
        # reload new tags after saving files
        self.loadtags(self.current_files)
        if not save_fail:
            self.tagimage.set_from_file(ICON_DIR +
                                        '16x16/emotes/face-laugh.png')
        return

    def loadtags(self, *args):
        """ connect chosen files with tags """
        self.loadlists()
        self.clearopenfiles()
        # pull tags for each music file
        for musicfiles in args[0]:
            tmp_title = None
            tmp_artist = None
            tmp_album = None
            tmp_albumartist = None
            tmp_genre = None
            tmp_track = None
            tmp_disc = None
            tmp_year = None
            tmp_comment = None
            try:
                item = eyeD3.Tag()
                item.link(musicfiles)
                item.setVersion(eyeD3.ID3_V2_4)
                item.setTextEncoding(eyeD3.UTF_8_ENCODING)
            except:
                # Tag error
                item = None
            # pull tag info per item
            if item:
                tmp_title = item.getTitle()
                if tmp_title == 'None':
                    tmp_title = None
                tmp_artist = item.getArtist('TPE1')
                if tmp_artist == 'None':
                    tmp_artist = None
                tmp_album = item.getAlbum()
                if tmp_album == 'None':
                    tmp_album = None
                tmp_albumartist = item.getArtist('TPE2')
                if tmp_albumartist == 'None':
                    tmp_albumartist = None
                try:
                    tmp_genre = str(item.getGenre())
                except eyeD3.tag.GenreException:
                    tmp_genre = None
                if tmp_genre == 'None':
                    tmp_genre = None
                if tmp_genre:
                    tmp_genre = tmp_genre.replace('/', '_')
                    if ')' in tmp_genre:
                        tmp_genre = tmp_genre.split(')')[1]
                tmp_track = str(item.getTrackNum()[0])
                if tmp_track == 'None':
                    tmp_track = None
                if tmp_track:
                    if '/' in tmp_track:
                        tmp_track = tmp_track.split('/')[0]
                    if len(tmp_track) == 1:
                        tmp_track = '0' + str(tmp_track)
                    if len(tmp_track) > 2:
                        tmp_track = tmp_track[:2]
                tmp_disc = str(item.getDiscNum()[0])
                if tmp_disc == 'None':
                    tmp_disc = None
                if tmp_disc:
                    if '/' in tmp_disc:
                        tmp_disc = tmp_disc.split('/')[0]
                    if len(tmp_disc) == 2:
                        tmp_disc = tmp_disc[-1]
                tmp_year = item.getYear()
                if tmp_year == 'None':
                    tmp_year = None
                tmp_comment = item.getComment()
                if tmp_comment == 'None':
                    tmp_comment = None
                # add tags to list
                self.title.append(tmp_title)
                self.artist.append(tmp_artist)
                self.album.append(tmp_album)
                self.albumartist.append(tmp_albumartist)
                self.genre.append(tmp_genre)
                self.track.append(tmp_track)
                self.disc.append(tmp_disc)
                self.year.append(tmp_year)
                self.comment.append(tmp_comment)
        # compare tags
        count = 0
        for types in self.trackselection:
            if types == []:
                return False
            comparison = False
            if len(args[0]) == 1:
                comparison = True
            for item in types[1:]:
                if item == None:
                    comparison = False
                    break
                if item != types[0]:
                    comparison = False
                    break
                comparison = True
            if comparison:
                self.uibuttons[count][0].set_active(True)
                if types[0]:
                    self.uibuttons[count][1].set_text(types[0])
                else:
                    self.uibuttons[count][0].set_active(False)
                    self.uibuttons[count][1].set_text('')
            else:
                self.uibuttons[count][0].set_active(False)
                if not types[0]:
                    self.uibuttons[count][1].set_text('')
                else:
                    self.uibuttons[count][1].set_text('[Multiple]')
            count = count + 1
        return

    def clearopenfiles(self):
        """ clear the tags ui when changing folder """
        count = 0
        while count < len(self.uibuttons):
            self.uibuttons[count][0].set_active(False)
            self.uibuttons[count][1].set_text('')
            count = count + 1
        self.tagimage.set_from_file(ICON_DIR + '16x16/emotes/face-plain.png')
        return

    def listfolder(self, *args):
        """ function to list the folder column """
        self.current_dir = args[0]
        self.current_dir = self.current_dir.replace('//', '/')
        self.currentdirlabel.set_text('Current Folder: ' +
                                      str(os.path.normpath(self.current_dir)))
        if not type(args[0]) == type(''):
            self.current_dir = args[0].get_current_folder()
        try:
            self.filelist = os.listdir(self.current_dir)
            self.filelist.sort(key=lambda y: y.lower())
        except OSError:
            self.gohome()
        # clear list if we have scanned before
        for items in self.folderlist:
            self.folderlist.remove(items.iter)
        # clear combobox before adding entries
        for items in self.folderview:
            self.folderview.remove(items.iter)
        # search the supplied directory for items
        for items in self.filelist:
            test_dir = os.path.isdir(self.current_dir + '/' + items)
            if not items[0] == '.' and test_dir:
                self.folderlist.append([items])
        if len(self.folderlist) == 0:
            self.folderlist.append(['[No more Folders]'])
        self.clearopenfiles()
        self.listfiles()
        return

    def listfiles(self, *args):
        """ function to fill the file list column """
        self.current_files = []
        try:
            files_dir = os.listdir(self.current_dir)
            files_dir.sort(key=lambda y: y.lower())
        except OSError:
            self.gohome()
        # clear list if we have scanned before
        for items in self.contentlist:
            self.contentlist.remove(items.iter)
        # clear combobox before adding entries
        for items in self.contenttree:
            self.contenttree.remove(items.iter)
        # search the supplied directory for items
        for items in files_dir:
            test_file = os.path.isfile(self.current_dir + '/' + items)
            test_ext = items[(items.rfind('.')):] in MEDIA_TYPES
            if not items[0] == '.' and test_file and test_ext:
                self.contentlist.append([items])
        if len(self.contentlist) == 0:
            self.contentlist.append(['[No media files found]'])
        return


if __name__ == "__main__":
    GLib.threads_init()
    MYTAG()
