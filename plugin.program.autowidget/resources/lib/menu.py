import xbmc
import xbmcgui

import random
import re
import time
import uuid

import six

from resources.lib import manage
from resources.lib import refresh
from resources.lib.common import directory
from resources.lib.common import utils

add = utils.get_art('add.png')
alert = utils.get_art('alert.png')
back = utils.get_art('back.png')
folder = utils.get_art('folder.png')
folder_shortcut = utils.get_art('folder-shortcut.png')
folder_sync = utils.get_art('folder-sync.png')
folder_next = utils.get_art('folder-next.png')
folder_merged = utils.get_art('folder-dots.png')
merge = utils.get_art('merge.png')
next = utils.get_art('next.png')
next_page = utils.get_art('next_page.png')
refresh_art = utils.get_art('refresh.png')
remove = utils.get_art('remove.png')
share = utils.get_art('share.png')
shuffle = utils.get_art('shuffle.png')
sync = utils.get_art('sync.png')
tools = utils.get_art('tools.png')
unpack = utils.get_art('unpack.png')


def root_menu():
    directory.add_menu_item(title=32007,
                            params={'mode': 'group'},
                            art=folder,
                            isFolder=True)
    directory.add_menu_item(title=32074,
                            params={'mode': 'widget'},
                            art=folder,
                            isFolder=True)
    directory.add_menu_item(title=32008,
                            params={'mode': 'tools'},
                            art=tools,
                            isFolder=True)
                            
    return True, 'AutoWidget'
                            
                            
def my_groups_menu():
    groups = manage.find_defined_groups()
    if len(groups) > 0:
        for group in groups:
            _id = uuid.uuid4()
            group_name = group['label']
            group_id = group['id']
            group_type = group['type']
            
            cm = [(utils.get_string(32061),
                  ('RunPlugin('
                   'plugin://plugin.program.autowidget/'
                   '?mode=manage'
                   '&action=edit'
                   '&group={})').format(group_id))]
            
            directory.add_menu_item(title=group_name,
                                    params={'mode': 'group',
                                            'group': group_id,
                                            'target': group_type,
                                            'id': six.text_type(_id)},
                                    info=group.get('info'),
                                    art=group.get('art') or (folder_shortcut
                                                             if group_type == 'shortcut'
                                                             else folder_sync),
                                    cm=cm,
                                    isFolder=True)
    else:
        directory.add_menu_item(title=32068,
                                art=alert,
                                isFolder=False,
                                props={'specialsort': 'bottom'})
                                
    return True, utils.get_string(32007)
    
    
def group_menu(group_id, target, _id):
    _window = utils.get_active_window()
    
    group = manage.get_group_by_id(group_id)
    if not group:
        utils.log('\"{}\" is missing, please repoint the widget to fix it.'
                  .format(group_id),
                  level=xbmc.LOGERROR)
        return False, 'AutoWidget'
    
    group_name = group['label']
    
    paths = manage.find_defined_paths(group_id)
    if len(paths) > 0:
        cm = []
        art = folder_shortcut if target == 'shortcut' else folder_sync
        
        for idx, path in enumerate(paths):
            if _window == 'media':
                cm = _create_context_items(group_id, path['id'], idx, len(paths))
            
            directory.add_menu_item(title=path['label'],
                                    params={'mode': 'path',
                                            'action': 'call',
                                            'group': group_id,
                                            'path': path['id']},
                                    info=path.get('info'),
                                    art=path.get('art') or art,
                                    cm=cm,
                                    isFolder=False)
                                    
        if target == 'widget' and _window != 'home':
            directory.add_separator(title=32010, char='/', sort='bottom')

            path_param = '$INFO[Window(10000).Property(autowidget-{}-action)]'.format(_id)

            directory.add_menu_item(title=utils.get_string(32028)
                                          .format(group_name),
                                    params={'mode': 'path',
                                            'action': 'random',
                                            'group': group_id,
                                            'id': six.text_type(_id),
                                            'path': path_param},
                                    art=shuffle,
                                    isFolder=True,
                                    props={'specialsort': 'bottom'})
            directory.add_menu_item(title=utils.get_string(32076)
                                          .format(group_name),
                                    params={'mode': 'path',
                                            'action': 'next',
                                            'group': group_id,
                                            'id': six.text_type(_id),
                                            'path': path_param},
                                    art=next,
                                    isFolder=True,
                                    props={'specialsort': 'bottom'})
            directory.add_menu_item(title=utils.get_string(32089)
                                          .format(group_name),
                                    params={'mode': 'path',
                                            'action': 'merged',
                                            'group': group_id,
                                            'id': six.text_type(_id)},
                                    art=merge,
                                    isFolder=True,
                                    props={'specialsort': 'bottom'})
    else:
        directory.add_menu_item(title=32032,
                                art=alert,
                                isFolder=False,
                                props={'specialsort': 'bottom'})
    
    return True, group_name
    
    
def active_widgets_menu():
    widgets = manage.find_defined_widgets()
    
    if len(widgets) > 0:
        for widget_def in widgets:
            _id = widget_def.get('id', '')
            action = widget_def.get('action', '')
            group = widget_def.get('group', '')
            path = widget_def.get('path', '')
            updated = widget_def.get('updated', '')
            
            path_def = manage.get_path_by_id(path, group)
            group_def = manage.get_group_by_id(group)
            
            title = ''
            if path_def and group_def:
                try:
                    path_def['label'] = path_def['label'].encode('utf-8')
                    group_def['label'] = group_def['label'].encode('utf-8')
                except:
                    pass
            
                title = '{} - {}'.format(path_def['label'], group_def['label'])
            elif group_def:
                title = group_def.get('label')

            art = {}
            params = {}
            if not action:
                art = folder_shortcut
                params = {'mode': 'group',
                          'group': group,
                          'target': 'shortcut',
                          'id': six.text_type(_id)}
                title = utils.get_string(32030).format(title)
            elif action in ['random', 'next', 'merged']:
                if action == 'random':
                    art = folder_sync
                elif action == 'next':
                    art = folder_next
                elif action == 'merged':
                    art = folder_merged
                
                params = {'mode': 'group',
                          'group': group,
                          'target': 'widget',
                          'id': six.text_type(_id)}
                
            cm = [(utils.get_string(32069), ('RunPlugin('
                                            'plugin://plugin.program.autowidget/'
                                            '?mode=refresh'
                                            '&target={})').format(_id)),
                  (utils.get_string(32070), ('RunPlugin('
                                            'plugin://plugin.program.autowidget/'
                                            '?mode=manage'
                                            '&action=edit_widget'
                                            '&target={})').format(_id))]
            
            if not group_def:
                title = '{} - [COLOR firebrick]{}[/COLOR]'.format(_id, utils.get_string(32071))
                
            directory.add_menu_item(title=title,
                                    art=art,
                                    params=params,
                                    cm=cm[1:] if not action else cm,
                                    isFolder=True)
    else:
        directory.add_menu_item(title=32072,
                                art=alert,
                                isFolder=False,
                                props={'specialsort': 'bottom'})

    return True, utils.get_string(32074)
    
    
def tools_menu():
    directory.add_menu_item(title=32006,
                            params={'mode': 'force'},
                            art=refresh_art,
                            info={'plot': utils.get_string(32020)},
                            isFolder=False)
    directory.add_menu_item(title=32064,
                            params={'mode': 'wipe'},
                            art=remove,
                            isFolder=False)
                            
    return True, utils.get_string(32008)
    
    
def _initialize(group_def, action, _id, save=True):
    duration = utils.get_setting_float('service.refresh_duration')
    
    paths = group_def['paths']
    rand_idx = random.randrange(len(paths))
    init_path = paths[0]['id'] if action == 'next' else paths[rand_idx]['id']
    
    params = {'action': action,
              'id': _id,
              'group': group_def['id'],
              'refresh': duration,
              'path': init_path}
    if save:
        details = manage.save_path_details(params)
        refresh.refresh(_id)
        return details
    else:
        return params
    
def show_path(group_id, path_id, _id, titles=[], num=1):
    hide_watched = utils.get_setting_bool('widgets.hide_watched')
    show_next = utils.get_setting_int('widgets.show_next')
    paged_widgets = utils.get_setting_bool('widgets.paged')
    
    widget_def = manage.get_widget_by_id(_id)
    path_def = manage.get_path_by_id(path_id, group_id=group_id)
    if not widget_def:
        return True, 'AutoWidget'
        
    if not path_def:
        if widget_def:
            path_def = manage.get_path_by_id(widget_def['path'],
                                             group_id=widget_def['group'])
        path = path_id
    else:
        path = path_def['file']['file']
    
    if path_def:
        path_label = path_def.get('label', 'AutoWidget')
    else:
        path_label = widget_def.get('label', '')
    
    stack = widget_def.get('stack', [])
    if stack:
        title = utils.get_string(32110).format(len(stack))
        directory.add_menu_item(title=title,
                                params={'mode': 'path',
                                        'action': 'update',
                                        'id': _id,
                                        'path': stack[-1],
                                        'target': 'back'},
                                art=back,
                                isFolder=num > 1,
                                props={'specialsort': 'top',
                                       'autoLabel': path_label})
    
    files = utils.get_files_list(path, titles)
    for file in files:
        properties = {'autoLabel': path_label}

        import json
        utils.log(json.dumps(file['art']), xbmc.LOGNOTICE)
        if 'customproperties' in file:
            for prop in file['customproperties']:
                properties[prop] = file['customproperties'][prop]
        
        next_item = re.sub('[^\w \xC0-\xFF]', '', file['label'].lower()).strip() in ['next', 'next page']
        prev_item = re.sub('[^\w \xC0-\xFF]', '', file['label'].lower()).strip() in ['previous', 'previous page', 'back']
        
        if (prev_item and stack) or (next_item and show_next == 0):
            continue
        elif next_item and show_next > 0:
            label = utils.get_string(32111)
            properties['specialsort'] = 'bottom'
            
            if num > 1:
                if show_next == 1:
                    continue
                    
                label = '{} - {}'.format(label,
                                                   path_label)
            
            directory.add_menu_item(title=label,
                                    params={'mode': 'path',
                                            'action': 'update',
                                            'id': _id,
                                            'path': file['file'],
                                            'target': 'next'} if num == 1 and paged_widgets else None,
                                    path=file['file'] if (num > 1 or paged_widgets) or (num == 1 and not paged_widgets) else None,
                                    art=next_page,
                                    info=file,
                                    isFolder=num > 1 or not paged_widgets,
                                    props=properties)
        else:
            if hide_watched and file.get('playcount', 0) > 0:
                continue
        
            directory.add_menu_item(title=file['label'],
                                    path=file['file'],
                                    art=file['art'],
                                    info=file,
                                    isFolder=file['filetype'] == 'directory',
                                    props=properties)
            
            titles.append(file.get('title'))
         
    return titles, path_label
    
    
def call_path(group_id, path_id):
    path_def = manage.get_path_by_id(path_id, group_id=group_id)
    if not path_def:
        return
    
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    xbmc.sleep(500)
    final_path = ''
    
    if path_def['target'] == 'shortcut' and path_def['file']['filetype'] == 'file' \
                                        and path_def['content'] != 'addons':
        if path_def['file']['file'] == 'addons://install/':
            final_path = 'InstallFromZip'
        elif path_def['content'] == 'files': 
            final_path = 'RunPlugin({})'.format(path_def['file']['file'])
        elif path_def['file']['file'].startswith('androidapp://sources/apps/'):
            final_path = 'StartAndroidActivity({})'.format(path_def['file']['file']
                                                           .replace('androidapp://sources/apps/', ''))
        elif all(i in path_def['file']['file'] for i in ['(', ')']) and '://' not in path_def['file']['file']:
            final_path = path_def['file']['file']
        else:
            final_path = 'PlayMedia({})'.format(path_def['file']['file'])
    elif path_def['target'] == 'widget' or path_def['file']['filetype'] == 'directory' \
                                        or path_def['content'] == 'addons':
        final_path = 'ActivateWindow({},{},return)'.format(path_def.get('window', 'Videos'),
                                                           path_def['file']['file'])
    elif path_def['target'] == 'settings':
        final_path = 'Addon.OpenSettings({})'.format(path_def['file']['file']
                                                     .replace('plugin://', ''))
        
    if final_path:
        xbmc.executebuiltin(final_path)
        
    return False, path_def['label']


def path_menu(group_id, action, _id, path=None):
    _window = utils.get_active_window()
    
    group_def = manage.get_group_by_id(group_id)
    if not group_def:
        utils.log('\"{}\" is missing, please repoint the widget to fix it.'
                  .format(group_id),
                  level=xbmc.LOGERROR)
        return False, 'AutoWidget'
    
    group_name = group_def.get('label', '')
    paths = group_def.get('paths', [])
    
    widget_def = manage.get_widget_by_id(_id, group_id)
    
    if not widget_def:
        widget_def = _initialize(group_def, action, _id, save=_window not in ['dialog', 'media'])
    
    if len(paths) > 0 and widget_def:
        if _window == 'media':
            rand = random.randrange(len(paths))
            return call_path(group_id, paths[rand]['id'])
        else:
            path_id = path if path else widget_def.get('path', '')
            titles, cat = show_path(group_id, path_id, _id)
            return titles, cat
    else:
        directory.add_menu_item(title=32032,
                                art=alert,
                                isFolder=False)
        return True, group_name
        
    return True, group_name
        
        
def merged_path(group_id, _id):
    _window = utils.get_active_window()
    
    group_def = manage.get_group_by_id(group_id)
    if not group_def:
        utils.log('\"{}\" is missing, please repoint the widget to fix it.'
                  .format(group_id),
                  level=xbmc.LOGERROR)
        return False, 'AutoWidget'
    
    group_name = group_def.get('label', '')
    paths = manage.find_defined_paths(group_id)
    
    widget_def = manage.get_widget_by_id(_id, group_id)
    
    if not widget_def:
        widget_def = _initialize(group_def, 'merged', _id, save=_window not in ['dialog', 'media'])
    
    if len(paths) > 0 and widget_def:
        titles = []

        for path_def in paths:
            titles, cat = show_path(group_id, path_def['id'], _id, num=len(paths))
                    
        return titles, group_name
    else:
        directory.add_menu_item(title=32032,
                                art=alert,
                                isFolder=False)
        return True, group_name


def _create_context_items(group_id, path_id, idx, length):
    cm = [(utils.get_string(32048),
              ('RunPlugin('
               'plugin://plugin.program.autowidget/'
               '?mode=manage'
               '&action=edit'
               '&group={}'
               '&path={})').format(group_id, path_id)),
          (utils.get_string(32026) if idx > 0 else utils.get_string(32113),
              ('RunPlugin('
               'plugin://plugin.program.autowidget/'
               '?mode=manage'
               '&action=shift_path'
               '&target=up'
               '&group={}'
               '&path={})').format(group_id, path_id)),
          (utils.get_string(32027) if idx < length - 1 else utils.get_string(32112),
              ('RunPlugin('
               'plugin://plugin.program.autowidget/'
               '?mode=manage'
               '&action=shift_path'
               '&target=down'
               '&group={}'
               '&path={})').format(group_id, path_id))]

    return cm
