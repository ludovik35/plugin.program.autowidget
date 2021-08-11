import xbmc
import xbmcgui

import os
import random
import time
import threading

from resources.lib import manage
from resources.lib.common import cache
from resources.lib.common import settings
from resources.lib.common import utils

_addon_data = utils.translate_path(settings.get_addon_info("profile"))

skin_string_pattern = "autowidget-{}-{}"
_properties = ["context.autowidget"]

_thread = None


class RefreshService(xbmc.Monitor):
    def __init__(self):
        """Starts all of the actions of AutoWidget's service."""
        super(RefreshService, self).__init__()
        utils.log("+++++ STARTING AUTOWIDGET SERVICE +++++", "info")

        self.player = Player()
        utils.ensure_addon_data()
        self._update_properties()
        self._clean_widgets()
        self._update_widgets()
        # Shutting down. Close thread
        if _thread is not None:
            _thread.stop()

    def onSettingsChanged(self):
        self._update_properties()

    def _update_properties(self):
        for property in _properties:
            setting = settings.get_setting(property)
            utils.log("{}: {}".format(property, setting))
            if setting is not None:
                utils.set_property(property, setting)
                utils.log("Property {0} set".format(property))
            else:
                utils.clear_property(property)
                utils.log("Property {0} cleared".format(property))

        self._reload_settings()

    def _reload_settings(self):
        self.refresh_enabled = settings.get_setting_int("service.refresh_enabled")
        self.refresh_duration = settings.get_setting_float("service.refresh_duration")
        self.refresh_notification = settings.get_setting_int(
            "service.refresh_notification"
        )
        self.refresh_sound = settings.get_setting_bool("service.refresh_sound")

        utils.update_container(True)

    def _clean_widgets(self):
        for widget_def in manage.find_defined_widgets():
            if not manage.clean(widget_def["id"]):
                utils.log("Resetting {}".format(widget_def["id"]))
                update_path(widget_def["id"], "reset")

    def tick(self, step, max, abort_check=lambda: False):
        "yield every Step secords until you get to Max or abort_check returns True"
        i = 0
        while i < max and not abort_check():
            if self.waitForAbort(step):
                break
            i += step
            yield i

    def _update_widgets(self):
        self._refresh(True)

        while not self.abortRequested():
            for _ in self.tick(step=1, max=60 * 15):
                # TODO: somehow delay till all other plugins loaded?
                updated = False
                unrefreshed_widgets = set()
                queue = list(cache.next_cache_queue())

                class Progress(object):
                    dialog = None
                    service = self
                    done = set()

                    def __call__(self, groupname, path):
                        if self.dialog is None:
                            self.dialog = xbmcgui.DialogProgressBG()
                            self.dialog.create("AutoWidget", utils.get_string(30141))
                        if not self.service.player.isPlayingVideo():
                            percent = (
                                len(self.done)
                                / float(len(queue) + len(self.done) + 1)
                                * 100
                            )
                            self.dialog.update(
                                int(percent), "AutoWidget", message=groupname
                            )
                        self.done.add(path)

                progress = Progress()

                while queue:
                    path, cache_data, widget_id = queue.pop(0)
                    hash = cache.path2hash(path)
                    utils.log("Dequeued cache update: {}".format(hash[:5]), "notice")

                    affected_widgets = set(cache.cache_and_update(
                        path, widget_id, cache_data, notify=progress
                    ))
                    if affected_widgets:
                        updated = True
                    unrefreshed_widgets = unrefreshed_widgets.union(
                        affected_widgets
                    )
                    # # wait 5s or for the skin to reload the widget
                    # # this should reduce churn at startup where widgets take too long too long show up
                    # before_update = time.time() # TODO: have .access file so we can put above update
                    # while _ in self.tick(1, 10, lambda: cache.last_read(hash) > before_update):
                    #     pass
                    # utils.log("paused queue until read {:.2} for {}".format(cache.last_read(hash)-before_update, hash[:5]), 'info')
                    if self.abortRequested():
                        break
                    queue = list(cache.next_cache_queue())
                for widget_id in unrefreshed_widgets:
                    widget_def = manage.get_widget_by_id(widget_id)
                    if not widget_def:
                        continue
                    _update_strings(widget_def)
                if (
                    os.path.exists(os.path.join(_addon_data, "refresh.time"))
                    and utils.get_active_window() == "home"
                ):
                    utils.update_container(True)
                if progress.dialog is not None:
                    progress.dialog.update(100)
                    progress.dialog.close()
                if (
                    updated
                    and self.refresh_enabled == 1
                    and not self.player.isPlayingVideo()
                ):
                    dialog = xbmcgui.Dialog()
                    dialog.notification(
                        u"AutoWidget", utils.get_string(30142), sound=False
                    )

            if self.abortRequested():
                break

            if not self._refresh():
                continue

    def _refresh(self, startup=False):
        if self.refresh_enabled in [0, 1] and manage.find_defined_widgets():
            notification = False
            if self.refresh_enabled == 1:
                if self.player.isPlayingVideo():
                    utils.log(
                        "+++++ PLAYBACK DETECTED, SKIPPING AUTOWIDGET REFRESH +++++",
                        "info",
                    )
                    return
            else:
                if self.refresh_notification == 0:
                    notification = True
                elif self.refresh_notification == 1:
                    if not self.player.isPlayingVideo():
                        notification = True

            utils.log("+++++ REFRESHING AUTOWIDGETS +++++", "info")
            refresh_paths(notify=notification and not startup)
        else:
            utils.log("+++++ AUTOWIDGET REFRESHING NOT ENABLED +++++", "info")


def _update_strings(widget_def):
    refresh = skin_string_pattern.format(widget_def["id"], "refresh")
    utils.set_property(refresh, "{}".format(time.time()))
    utils.log(
        "Refreshing widget {} to display {}".format(
            widget_def["id"], widget_def["path"]
        ),
        "debug",
    )


def update_path(widget_id, target, path=None):
    widget_def = manage.get_widget_by_id(widget_id)
    if not widget_def:
        return

    stack = widget_def.get("stack", [])

    if target == "next" and path:
        utils.log("Next Page selected from {}".format(widget_id), "debug")
        path_def = manage.get_path_by_id(widget_def["path"], widget_def["group"])
        if isinstance(path_def, dict):
            widget_def["label"] = path_def["label"]

        stack.append(path)
        widget_def["stack"] = stack
    elif target == "back" and widget_def.get("stack"):
        utils.log("Previous Page selected from {}".format(widget_id), "debug")
        widget_def["stack"] = widget_def["stack"][:-1]
    elif target == "reset":
        if len(stack) > 0:
            # simple compatibility with pre-3.3.0 widgets
            if isinstance(stack[0], dict):
                widget_def["path"] = stack[0].get("id", "")

            widget_def["stack"] = []

    manage.save_path_details(widget_def)
    _update_strings(widget_def)
    utils.update_container(True)
    back_to_top(target)


def back_to_top(target):
    if target != "next":
        return
    actions = ["back", "firstpage", "right"]
    for action in actions:
        utils.call_builtin("Action({})".format(action), 100)


def refresh(widget_id, widget_def=None, paths=None, force=False, single=False):
    if not widget_def:
        widget_def = manage.get_widget_by_id(widget_id)

    if widget_def["action"] in ["static", "merged"]:
        return paths

    current_time = time.time()
    updated_at = widget_def.get("updated", 0)

    default_refresh = settings.get_setting_float("service.refresh_duration")
    refresh_duration = float(widget_def.get("refresh", default_refresh))

    if updated_at <= current_time - (3600 * refresh_duration) or force:
        group_id = widget_def["group"]
        action = widget_def.get("action")
        current = int(widget_def.get("current", 0))
        widget_def["stack"] = []

        if not paths:
            cycle_paths = widget_def.get("cycle_paths")
            if cycle_paths is None:
                cycle_paths = [p.get("id") for p in manage.find_defined_paths(group_id)]
                widget_def["cycle_paths"] = cycle_paths

            paths = [p for p in cycle_paths]

        if action:
            if len(paths) > 0:
                next = 0
                if action == "next":
                    next = (current + 1) % len(paths)

                elif action == "random":
                    random.shuffle(paths)
                    next = random.randrange(len(paths))

                widget_def["current"] = next
                path_id = paths[next]
                paths.remove(paths[next])

                widget_def["path"] = path_id
                if widget_def["path"]:
                    path_label = manage.get_path_by_id(path_id, group_id).get(
                        "label", ""
                    )
                    widget_def["label"] = path_label
                    widget_def["updated"] = 0 if force else current_time

                    manage.save_path_details(widget_def)
                    _update_strings(widget_def)

        if single:
            utils.update_container(True)

    return paths


def refresh_paths(notify=False, force=False):
    if notify:
        dialog = xbmcgui.Dialog()
        dialog.notification(
            "AutoWidget",
            utils.get_string(30020),
            sound=settings.get_setting_bool("service.refresh_sound"),
        )
        del dialog

    for group_def in manage.find_defined_groups():
        paths = []

        widgets = manage.find_defined_widgets(group_def["id"])
        for widget_def in widgets:
            paths = refresh(
                widget_def["id"], widget_def=widget_def, paths=paths, force=force
            )

    utils.update_container(True)

    return True, "AutoWidget"


def get_files_list(path, label=None, widget_id=None, background=True):
    hash = cache.path2hash(path)
    _, files, _ = cache.cache_expiry(path, widget_id, background=background)
    if files is None:
        # Should only happen now when background is False
        utils.log("Blocking cache path read: {}".format(hash[:5]), "info")
        files, changed = cache.cache_files(path, widget_id)

    new_files = []
    if "result" in files:
        files = files.get("result", {}).get("files", [])
    elif "error" in files:
        utils.log("Error processing {}".format(hash), "error")
        error_tile = utils.make_holding_path(
            utils.get_string(30139).format(label), "alert", hash=hash
        )
        files = error_tile.get("result", {}).get("files", [])
        cache_path = os.path.join(_addon_data, "{}.cache".format(hash))
        if os.path.exists(cache_path):
            os.remove(cache_path)
        utils.log("Invalid cache file removed for {}".format(hash))

    if not files:
        utils.log("No items found for {}".format(hash))
        empty_tile = utils.make_holding_path(
            utils.get_string(30140).format(label), "information-outline", hash=hash
        )
        files = empty_tile.get("result", {}).get("files", [])

    for file in files:
        new_file = {k: v for k, v in file.items() if v is not None}

        if "art" in new_file:
            for art in new_file["art"]:
                new_file["art"][art] = utils.clean_artwork_url(file["art"][art])
        if "cast" in new_file:
            for idx, cast in enumerate(new_file["cast"]):
                new_file["cast"][idx]["thumbnail"] = utils.clean_artwork_url(
                    cast.get("thumbnail", "")
                )
        new_files.append(new_file)

    return new_files, hash


def is_duplicate(title, titles):
    if not settings.get_setting_bool("widgets.hide_duplicates"):
        return False

    prefer_eps = settings.get_setting_bool("widgets.prefer_episodes")
    if title["type"] == "movie":
        return (title["label"], title["imdbnumber"]) in [
            (t["label"], t["imdbnumber"]) for t in titles
        ]
    elif (title["type"] == "tvshow" and prefer_eps) or (
        title["type"] == "episode" and not prefer_eps
    ):
        return title["showtitle"] in [t["showtitle"] for t in titles]
    else:
        return False


# Get info on whats playing and use it to update the right widgets when playback stopped
class Player(xbmc.Player):
    def __init__(self):
        super(Player, self).__init__()
        self.publish = None
        self.totalTime = -1
        self.playingTime = 0
        self.info = {}

    def playing_type(self):
        """
        @return: [music|movie|episode|stream|liveTV|recordedTV|PVRradio|unknown]
        """
        # TODO: taken from callbacks plugin. have as a dependcy instead?
        substrings = ["-trailer", "http://"]
        isMovie = False
        if self.isPlayingAudio():
            return "music"
        else:
            if xbmc.getCondVisibility("VideoPlayer.Content(movies)"):
                isMovie = True
        try:
            filename = self.getPlayingFile()
        except RuntimeError:
            filename = ""
        if filename != "":
            if filename[0:3] == "pvr":
                if xbmc.getCondVisibility("Pvr.IsPlayingTv"):
                    return "liveTV"
                elif xbmc.getCondVisibility("Pvr.IsPlayingRecording"):
                    return "recordedTV"
                elif xbmc.getCondVisibility("Pvr.IsPlayingRadio"):
                    return "PVRradio"
                else:
                    for string in substrings:
                        if string in filename:
                            isMovie = False
                            break
        if isMovie:
            return "movie"
        elif xbmc.getCondVisibility("VideoPlayer.Content(episodes)"):
            # Check for tv show title and season to make sure it's really an episode
            if (
                xbmc.getInfoLabel("VideoPlayer.Season") != ""
                and xbmc.getInfoLabel("VideoPlayer.TVShowTitle") != ""
            ):
                return "episode"
        elif xbmc.getCondVisibility("Player.IsInternetStream"):
            return "stream"
        else:
            return "unknown"

    def onPlayBackStarted(self):
        # self.getInfo()
        try:
            self.totalTime = self.getTotalTime()
        except RuntimeError:
            self.totalTime = -1
        finally:
            if self.totalTime == 0:
                self.totalTime = -1
        # self.recordPlay()
        self.type = self.playing_type()

        def update_playback_time(self=self):
            while self.isPlaying():
                self.playingTime = self.getTime()
                time.sleep(1)

        threading.Thread(target=update_playback_time).start()

    def onPlayBackEnded(self):
        # import ptvsd; ptvsd.enable_attach(address=('127.0.0.1', 5678)); ptvsd.wait_for_attach()
        utils.log("AutoWidget onPlayBackEnded callback", "notice")

        # Once a playback ends.
        # Work out which cached paths are most likely to change based on playback history

        # Record playback in a history db so we can potentially use this for future predictions.
        try:
            tt = self.totalTime
            tp = self.playingTime
            pp = int(100 * tp / tt)
        except RuntimeError:
            pp = -1
        except OverflowError:
            pp = -1
        self.totalTime = -1.0
        self.playingTime = 0.0
        self.info = {}
        cache.save_playback_history(self.type, pp)
        utils.log("recorded playback of {}% {}".format(pp, self.type), "notice")

        # wait for a bit so scrobing can happen
        time.sleep(5)
        for hash, path in cache.widgets_changed_by_watching(self.type):
            # Queue them for refresh
            cache.push_cache_queue(path)
            utils.log("Queued cache update: {}".format(hash[:5]), "notice")
        utils.update_container(reload=True)

    def onPlayBackStopped(self):
        self.onPlayBackEnded()

    def onPlayBackSeek(self, time, seekOffset):
        self.playingTime = time

    def onPlayBackPaused(self):
        pass

    def onPlayBackResumed(self):
        pass

    def onPlayBackSeekChapter(self, chapter):
        pass

    def onPlayBackSpeedChanged(self, speed):
        pass

    def onQueueNextItem(self):
        pass
