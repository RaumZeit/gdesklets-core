import gtk
import gobject
import sys
import logging
logging.basicConfig(level=logging.DEBUG)

gtk.gdk.threads_init()

import Config
import WidgetList
import SideMenu
import MenuBar
import StatusBar
import PrefsDialog
import control

import __builtin__

try:
    __builtin__._()
except:
    logging.info('No locale function defined. Using a dummy lambda.')    
    __builtin__._ = lambda s:s


class SlickShell(object):

    def __init__(self):
        self.__config = Config.Config()
        self.__assembly = control.Assembly.Assembly()
        self.__assembly.add_observer(self.assembly_event)
        
        self.__website_integration = self.__config.get('website_integration')
        self.__assembly.set_website_integration(self.__website_integration)
        self.__expand_tabs = self.__config.get('expand_tabs_by_default')
        self.__prefs_dialog = None
        self.__selected_widget = None
        
        self.__window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.__construct_action_groups()
        self.__window.set_title( _("gDesklets Shell NG") )
        self.__window.connect("delete_event", self.close_window_event)
        w = self.__config.get('width') or 400
        h = self.__config.get('height') or 400
        self.__window.set_default_size(int(w),int(h))
        
        # one vertical box to hold toolbars, and other boxes (not homogenous, 2px spacing)
        self.__top_box = gtk.VBox(False, 2)
        self.__window.add(self.__top_box)
        self.__status_bar = StatusBar.StatusBar()
        self.__top_box.pack_end(self.__status_bar, False, False, 0)
        self.__menubar = MenuBar.MenuBar(self)
        self.__top_box.pack_start(self.__menubar, False, False, 0)
        
        self.__status_bar.set_msg(_('Loading'))
        self.__status_bar.pulse()
        
        # the pane for the WidgetList and the newsview. will be filled
        # once the assembly has finished loading
        self.__hpaned = gtk.HPaned()
        self.__sidemenu = SideMenu.SideMenu(self)
        self.__hpaned.add2(self.__sidemenu)
        self.__top_box.pack_start(self.__hpaned)
        self.__desklet_list = None
        
        self.__hpaned.add2(gtk.Label('Loading'))
        
        self.__window.connect('check-resize', self.__size_changed_cb)
        self.__window.show_all()
        
        # start the assembly
        self.__assembly.start()
        gtk.main()
        
        
    def __construct_action_groups(self):
        ''' Actions are constructed here so that they are easily accessible by the
            other components '''
        accel_group = gtk.AccelGroup()
        self.__window.add_accel_group(accel_group)
        self.__action_groups = {}
        self.__action_groups['global'] = gtk.ActionGroup("global")
        
        aquit = gtk.Action('quit', None, None, gtk.STOCK_QUIT)
        aquit.connect('activate', self.close_window_event)
        self.__action_groups['global'].add_action_with_accel(aquit, None)
        aquit.set_accel_group(accel_group)
        aquit.connect_accelerator()
        
        self.__action_groups['global'].add_actions([
                    ('update', gtk.STOCK_REFRESH, _('Update'), None, 
                        _('Update the widget list'), self.update_event ),
                    ('about', gtk.STOCK_ABOUT, _('About'), None, _('About gDesklets'), 
                        self.show_about),
                    ('prefs', gtk.STOCK_PREFERENCES, _('Preferences'), None, _('Set application preferences'), 
                        self.show_prefs),
                    ])
        
        self.__action_groups['widget'] = gtk.ActionGroup("widget")
        self.__action_groups['widget'].add_actions([
                    ('install', gtk.STOCK_ADD, 'Install', None, 
                        _('Install the selected widget'), self.install_event), 
                    ('remove', gtk.STOCK_DELETE, _('Remove'), None, 
                        _('Remove the selected widget'), self.remove_event ),
                    ('activate', gtk.STOCK_MEDIA_PLAY, _('Activate'), None, 
                        _('Activate the selected widget'), self.activate_event), 
                    ])
    
        self.__action_groups['widget'].get_action("install").set_sensitive(False)
        self.__action_groups['widget'].get_action("remove").set_sensitive(False)
        self.__action_groups['widget'].get_action("activate").set_sensitive(False)
        
        
    
    def refresh_view(self, event):
        ''' Refresh the view after installation, etc. '''
        desklet_object = self.__selected_widget
        if desklet_object.local_path is not None:
            self.__action_groups.get_action("remove").set_sensitive(True)
            self.__action_groups.get_action("install").set_sensitive(False)
            self.__tree_model.set_value(self.__selected_widget_iter, 3, True)
            # see if this is a desklet or a control and show the activate button
            try: 
                preview = desklet_object.preview
                self.__action_groups.get_action("activate").set_sensitive(True)
            except:
                self.__action_groups.get_action("activate").set_sensitive(False)
                
        else:
            self.__action_groups.get_action("remove").set_sensitive(False)
            self.__action_groups.get_action("install").set_sensitive(False)
            self.__action_groups.get_action("activate").set_sensitive(False)
            self.__tree_model.set_value(self.__selected_widget_iter, 3, False)
            
        if desklet_object.remote_domain is not None:
            self.__action_groups.get_action("install").set_sensitive(True)
        else:
            self.__action_groups.get_action("install").set_sensitive(False)
    
    
    def get_assembly(self): return self.__assembly

    
    
    def get_action_group(self, name): return self.__action_groups[name]



    def close_window_event(self, event, data=None):
        self.__status_bar.stop_pulse()
        print "calling gtk main quit"
        gtk.main_quit()
        # sys.exit()
        

    
    def assembly_event(self, type, param):
        ''' Called by the assembly when something funky happens like the fetching is 
            complete, something is installed or removed, etc.. '''
        logging.info("Assembly event has occured: %s - %s" % (type, param))
        
        if type == 'INSTALLED' or type == 'REMOVED': 
            self.refresh_view(param)
            
        elif type == 'FETCH':
            # print "fetch event", param
            # self.__statusbar.pop(0)
            # All is done: construct the view
            if param == 'All done':
                if self.__desklet_list == None:
                    self.__desklet_list = WidgetList.WidgetList(self)
                    # self.__news_view = NewsView.NewsView(self)
                    self.__hpaned.add1(self.__desklet_list)
                    self.__window.show_all()
                else: 
                    self.__desklet_list.populate_treemodel()
                
                if self.__expand_tabs: 
                        self.__desklet_list.expand_all()
                        
                self.__status_bar.stop_pulse()
                self.__status_bar.set_msg(_('Ready'))
        
    def install_event(self, event):
        logging.info("install" + self.__selected_widget.name)
        self.__selected_widget.install_newest_version()
    
    
    
    def remove_event(self, event):
        logging.info("remove" + self.__selected_widget.name)
        self.__selected_widget.remove()
        
        
    
    def activate_event(self, event):
        logging.info("activate event " + self.__selected_widget.name)
        self.__selected_widget.activate_all()
     
        
        
    def deactivate_event(self, event):
        logging.info("deactivate" + self.__selected_widget.name)
        self.__selected_widget.deactivate()
    
    
    def desklet_selected_event(self, desklet):
        # print desklet.remote_domain, "---", desklet.local_path
        if desklet.remote_domain is not None:
            self.__action_groups['widget'].get_action('install').set_sensitive(True)
        if desklet.local_path is not None:
            self.__action_groups['widget'].get_action('activate').set_sensitive(True)
            self.__action_groups['widget'].get_action('remove').set_sensitive(True)
        else:
            self.__action_groups['widget'].get_action('install').set_sensitive(False)
            self.__action_groups['widget'].get_action('remove').set_sensitive(False)
            self.__action_groups['widget'].get_action('activate').set_sensitive(False)
            
        self.__selected_widget = desklet
        self.__sidemenu.show_desklet(desklet)
    
        
    def update_event(self, event):
        logging.info( "Shell: updating..." )
        self.__assembly.refresh(self.__website_integration)
        self.__desklet_list.refresh()
        self.__sidemenu.reset()
        
    
    def set_website_integration(self, val): 
        self.__website_integration = val
        self.__assembly.set_website_integration(val)
        self.__config.set('website_integration', int(val))
        
    
    def set_expand_tabs(self, val): 
        self.__expand_tabs = int(val)
        self.__config.set('expand_tabs_by_default', int(val))
        if val: self.__desklet_list.expand_all()
        else: self.__desklet_list.collapse_all()
    
        
    def show_about(self, event):
        logging.info("showing the about window")
        ab = gtk.AboutDialog()
        ab.show_all()
  
  
    def show_prefs(self, event):
        logging.info("showing the preferences window")
        self.__prefs_dialog = PrefsDialog.PrefsDialog(self, self.__config)
        
    
    def install_from_http(self, url):
        self.__status_bar.set_msg(_('Installing desklet'))
        self.__status_bar.pulse()
        self.__assembly.install_http(url)
    
    
    def __size_changed_cb(self, container):
        w, h = self.__window.get_size()
        self.__config.set('width', w)
        self.__config.set('height', h)
        