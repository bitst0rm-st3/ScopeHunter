"""
Scope Hunter
Licensed under MIT
Copyright (c) 2012 Isaac Muse <isaacmuse@gmail.com>
"""

import sublime
import sublime_plugin
from time import time, sleep
import _thread as thread
from ScopeHunter.lib.color_scheme_matcher import ColorSchemeMatcher

pref_settings = {}
scheme_matcher = None
scheme_matcher_simulated = None
sh_settings = {}
css = None


def log(msg):
    print("ScopeHunter: %s" % msg)


def underline(regions):
    """
    Convert to empty regions
    """

    new_regions = []
    for region in regions:
        start = region.begin()
        end = region.end()
        while start < end:
            new_regions.append(sublime.Region(start))
            start += 1
    return new_regions


class ScopeThreadManager(object):
    @classmethod
    def load(cls):
        cls.wait_time = 0.12
        cls.time = time()
        cls.modified = False
        cls.ignore_all = False
        cls.instant_scoper = False

    @classmethod
    def is_enabled(cls, view):
        return not view.settings().get("is_widget") and not cls.ignore_all

ScopeThreadManager.load()


class ScopeGlobals(object):
    bfr = None
    pt = None

    @classmethod
    def clear(cls):
        cls.bfr = None
        cls.pt = None


class ScopeHunterInsertCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.insert(edit, ScopeGlobals.pt, ScopeGlobals.bfr)


class GetSelectionScope(object):
    def get_scope(self, pt):
        if self.rowcol or self.points or self.highlight_extent:
            pts = self.view.extract_scope(pt)
            row1, col1 = self.view.rowcol(pts.begin())
            row2, col2 = self.view.rowcol(pts.end())
            # Scale back the extent by one for true points included
            if pts.size() < self.highlight_max_size:
                self.extents.append(sublime.Region(pts.begin(), pts.end()))

            if self.points or self.rowcol:
                extents = []
                if self.points:
                    extents.append("(%d, %d)" % (pts.begin(), pts.end()))
                if self.rowcol:
                    extents.append("(line: %d char: %d, line: %d char: %d)" % (row1 + 1, col1 + 1, row2 + 1, col2 + 1))
                self.scope_bfr.append("%-30s %s" % ("Scope Extents:", ('\n' + (" " * 31)).join(extents)))

                if self.show_popup:
                    self.scope_bfr_tool.append("<h1>Scope Extent</h1><p>")
                    if self.points:
                        self.scope_bfr_tool.append("(%d, %d)" % (pts.begin(), pts.end()))
                        if self.rowcol:
                            self.scope_bfr_tool.append("<br>")
                    if self.rowcol:
                        self.scope_bfr_tool.append("(<b>Line:</b> %d <b>Char:</b> %d, <b>Line:</b> %d <b>Char:</b> %d)" % (row1 + 1, col1 + 1, row2 + 1, col2 + 1))
                    self.scope_bfr_tool.append("</p>")
        scope = self.view.scope_name(pt)

        if self.clipboard:
            self.clips.append(scope)

        if self.first and self.show_statusbar:
            self.status = scope
            self.first = False

        self.scope_bfr.append("%-30s %s" % ("Scope:", self.view.scope_name(pt).strip().replace(" ", "\n" + (" " * 31))))
        if self.show_popup:
            self.scope_bfr_tool.append("<h1>Scope:</h1><p>%s</p>" % self.view.scope_name(pt).strip())

        if self.show_selectors and scheme_matcher is not None and scheme_matcher_simulated is not None:
            try:
                color_sim, style_sim, bgcolor_sim, color_selector_sim, bg_selector_sim, style_selectors_sim = scheme_matcher.guess_color(self.view, pt, scope)
                color, style, bgcolor, color_selector, bg_selector, style_selectors = scheme_matcher.guess_color(self.view, pt, scope)
                self.scheme_file = scheme_matcher.color_scheme
                self.syntax_file = self.view.settings().get('syntax')
                self.scope_bfr.append("%-30s %s" % ("Scheme File:", self.scheme_file))
                self.scope_bfr.append("%-30s %s" % ("Syntax File:", self.syntax_file))
                self.scope_bfr.append("%-30s %s" % ("foreground:", color))
                self.scope_bfr.append("%-30s %s" % ("foreground (simulated trans):", color_sim))
                self.scope_bfr.append("%-30s %s" % ("foreground selector:", color_selector))
                self.scope_bfr.append("%-30s %s" % ("background:", bgcolor))
                self.scope_bfr.append("%-30s %s" % ("background (simulated trans):", bgcolor_sim))
                self.scope_bfr.append("%-30s %s" % ("background selector:", bg_selector))
                self.scope_bfr.append("%-30s %s" % ("style:", style))
                if style_selectors["bold"] != "":
                    self.scope_bfr.append("%-30s %s" % ("bold selector:", style_selectors["bold"]))
                if style_selectors["italic"] != "":
                    self.scope_bfr.append("%-30s %s" % ("italic selector:", style_selectors["italic"]))

                if self.show_popup:
                    self.scope_bfr_tool.append('<h1>%s</h1><p><a href="scheme">%s</a></p>' % ("Scheme File", self.scheme_file))
                    self.scope_bfr_tool.append('<h1>%s</h1><p><a href="syntax">%s</a></p>' % ("Syntax File", self.syntax_file))
                    self.scope_bfr_tool.append('<h1>%s</h1><p>' % "Color and Style")
                    self.scope_bfr_tool.append('<b>foreground:</b> %s<br><b>foreground (simulated trans):</b> %s<br>' % (color, color_sim))
                    self.scope_bfr_tool.append('<b>foreground selector:</b> %s<br>' % color_selector)
                    self.scope_bfr_tool.append('<b>background:</b> %s<br><b>background (simulated trans):</b> %s<br>' % (bgcolor, bgcolor_sim))
                    self.scope_bfr_tool.append('<b>background selector:</b> %s<br>' % bg_selector)
                    self.scope_bfr_tool.append('<b>style:</b> %s' % style)
                    if style_selectors["bold"] != "":
                        self.scope_bfr_tool.append('<br><b>bold selector:</b> %s' % style_selectors["bold"])
                    if style_selectors["italic"] != "":
                        self.scope_bfr_tool.append('<br><b>italic selector:</b> %s' % style_selectors["italic"])

            except Exception as e:
                log("Evaluating theme failed!  Ignoring theme related info.\n%s" % str(e))
                self.show_selectors = False

        # Divider
        self.scope_bfr.append("")

    def on_navigate(self, href):
        if href == 'copy':
            sublime.set_clipboard('\n'.join(self.scope_bfr))
            self.view.hide_popup()
        elif href == 'scheme' and self.scheme_file is not None:
            window = self.view.window()
            window.run_command(
                'open_file',
                {"file": "${packages}/%s" % self.scheme_file.replace('\\', '/').replace('Packages/', '', 1)}
            )
        elif href == 'syntax' and self.syntax_file is not None:
            window = self.view.window()
            window.run_command(
                'open_file',
                {"file": "${packages}/%s" % self.syntax_file.replace('\\', '/').replace('Packages/', '', 1)}
            )

    def run(self, v):
        global css

        self.view = v
        self.window = self.view.window()
        view = self.window.get_output_panel('scope_viewer')
        self.scope_bfr = []
        self.scope_bfr_tool = ['<style>%s</style>' % (css if css is not None else '')]
        self.clips = []
        self.status = ""
        self.scheme_file = None
        self.syntax_file = None
        self.show_statusbar = bool(sh_settings.get("show_statusbar", False))
        self.show_panel = bool(sh_settings.get("show_panel", False))
        if int(sublime.version()) >= 3070:
            self.show_popup = bool(sh_settings.get("show_popup", False))
        else:
            self.show_popup = False
        self.clipboard = bool(sh_settings.get("clipboard", False))
        self.multiselect = bool(sh_settings.get("multiselect", False))
        self.rowcol = bool(sh_settings.get("extent_line_char", False))
        self.points = bool(sh_settings.get("extent_points", False))
        self.console_log = bool(sh_settings.get("console_log", False))
        self.highlight_extent = bool(sh_settings.get("highlight_extent", False))
        self.highlight_scope = sh_settings.get("highlight_scope", 'invalid')
        self.highlight_style = sh_settings.get("highlight_style", 'underline')
        self.highlight_max_size = int(sh_settings.get("highlight_max_size", 100))
        self.show_selectors = bool(sh_settings.get("show_color_scheme_info", False))
        self.first = True
        self.extents = []

        # Get scope info for each selection wanted
        if len(self.view.sel()):
            if self.multiselect:
                for sel in self.view.sel():
                    self.get_scope(sel.b)
            else:
                self.get_scope(self.view.sel()[0].b)

        # Copy scopes to clipboard
        if self.clipboard:
            sublime.set_clipboard('\n'.join(self.clips))

        # Display in status bar
        if self.show_statusbar:
            sublime.status_message(self.status)

        # Show panel
        if self.show_panel:
            ScopeGlobals.bfr = '\n'.join(self.scope_bfr)
            ScopeGlobals.pt = 0
            view.run_command('scope_hunter_insert')
            ScopeGlobals.clear()
            self.window.run_command("show_panel", {"panel": "output.scope_viewer"})

        if self.show_popup:
            self.view.show_popup(''.join(self.scope_bfr_tool) + '<br><br><a href="copy">Copy to Clipboard</a>', location=-1, max_width=600, on_navigate=self.on_navigate)

        if self.console_log:
            print('\n'.join(["Scope Hunter"] + self.scope_bfr))

        if self.highlight_extent:
            highlight_style = 0
            if self.highlight_style == 'underline':
                # Use underline if explicity requested,
                # or if doing a find only when under a selection only (only underline can be seen through a selection)
                self.extents = underline(self.extents)
                highlight_style = sublime.DRAW_EMPTY_AS_OVERWRITE
            elif self.highlight_style == 'outline':
                highlight_style = sublime.DRAW_OUTLINED
            self.view.add_regions(
                'scope_hunter',
                self.extents,
                self.highlight_scope,
                '',
                highlight_style
            )


find_scopes = GetSelectionScope().run


class GetSelectionScopeCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        ScopeThreadManager.modified = True

    def is_enabled(self):
        return ScopeThreadManager.is_enabled(self.view)


class ToggleSelectionScopeCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        ScopeThreadManager.instant_scoper = False if ScopeThreadManager.instant_scoper else True
        if ScopeThreadManager.instant_scoper:
            ScopeThreadManager.modified = True
            ScopeThreadManager.time = time()
        else:
            win = sublime.active_window()
            if win is not None:
                view = win.active_view()
                if (
                    view is not None and
                    ScopeThreadManager.is_enabled(view) and
                    bool(sh_settings.get("highlight_extent", False)) and
                    len(view.get_regions("scope_hunter"))
                ):
                    view.erase_regions("scope_hunter")


class SelectionScopeListener(sublime_plugin.EventListener):
    def clear_regions(self, view):
        if self.enabled and bool(sh_settings.get("highlight_extent", False)) and len(view.get_regions("scope_hunter")):
            view.erase_regions("scope_hunter")

    def on_selection_modified(self, view):
        self.enabled = ScopeThreadManager.is_enabled(view)
        if not ScopeThreadManager.instant_scoper or not self.enabled:
            # clean up dirty highlights
            self.clear_regions(view)
        else:
            ScopeThreadManager.modified = True
            ScopeThreadManager.time = time()


def sh_run():
    """
    Kick off scoper
    """

    # Ignore selection inside the routine
    ScopeThreadManager.modified = False
    ScopeThreadManager.ignore_all = True
    window = sublime.active_window()
    view = None if window is None else window.active_view()
    if view is not None:
        find_scopes(view)
    ScopeThreadManager.ignore_all = False
    ScopeThreadManager.time = time()


def sh_loop():
    """
    Start thread that will ensure scope hunting happens after a barage of events
    Initial hunt is instant, but subsequent events in close succession will
    be ignored and then accounted for with one match by this thread
    """

    while True:
        if not ScopeThreadManager.ignore_all:
            if ScopeThreadManager.modified is True and time() - ScopeThreadManager.time > ScopeThreadManager.wait_time:
                sublime.set_timeout(lambda: sh_run(), 0)
        sleep(0.5)


def init_css():
    global sh_settings
    global css
    global scheme_matcher

    css_file = sh_settings.get('css_file', None)
    if css_file is None:
        if scheme_matcher.is_dark_theme:
            css_file = 'Packages/' + sh_settings.get('dark_css_override', 'Packages/ScopeHunter/css/dark.css')
        else:
            css_file = 'Packages/' + sh_settings.get('light_css_override', 'Packages/ScopeHunter/css/light.css')
    else:
        css_file = 'Packages/' + css_file

    try:
        css = sublime.load_resource(css_file).replace('\r', '\n')
    except:
        css = None
    sh_settings.clear_on_change('reload')
    sh_settings.add_on_change('reload', init_css)


def init_color_scheme():
    global pref_settings
    global scheme_matcher
    global scheme_matcher_simulated
    pref_settings = sublime.load_settings('Preferences.sublime-settings')
    scheme_file = pref_settings.get('color_scheme')
    try:
        scheme_matcher_simulated = ColorSchemeMatcher(scheme_file, strip_trans=True)
        scheme_matcher = ColorSchemeMatcher(scheme_file)
    except Exception as e:
        scheme_matcher_simulated = None
        scheme_matcher = None
        log("Theme parsing failed!  Ingoring theme related info.\n%s" % str(e))
    pref_settings.clear_on_change('reload')
    pref_settings.add_on_change('reload', init_color_scheme)
    init_css()


def plugin_loaded():
    global sh_settings
    sh_settings = sublime.load_settings('scope_hunter.sublime-settings')

    init_color_scheme()

    if 'running_sh_loop' not in globals():
        global running_sh_loop
        running_sh_loop = True
        thread.start_new_thread(sh_loop, ())
