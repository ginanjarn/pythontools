import sublime
import sublime_plugin
from contextlib import contextmanager
from .core.sublimetext import plugin_settings


# menu check state holder
AUTOCOMPLETE = False
DOCUMENTATION = False
DOCUMENT_FORMATTING = False
DIAGNOSTIC = False
VALIDATE = False
DIAGNOSTIC_PANEL = False


@contextmanager
def load_settings(save=False):
    sublime_settings = sublime.load_settings(plugin_settings.SETTINGS_BASENAME)
    yield sublime_settings

    if save:
        sublime.save_settings(plugin_settings.SETTINGS_BASENAME)


def update_menu():
    """update menu check state"""

    global AUTOCOMPLETE
    global DOCUMENTATION
    global DOCUMENT_FORMATTING
    global DIAGNOSTIC
    global VALIDATE
    global DIAGNOSTIC_PANEL

    with load_settings(save=False) as settings:
        AUTOCOMPLETE = settings.get(plugin_settings.F_AUTOCOMPLETE, True)
        DOCUMENTATION = settings.get(plugin_settings.F_DOCUMENTATION, True)
        DOCUMENT_FORMATTING = settings.get(plugin_settings.F_DOCUMENT_FORMATTING, True)
        DIAGNOSTIC = settings.get(plugin_settings.F_DIAGNOSTIC, True)
        VALIDATE = settings.get(plugin_settings.F_VALIDATE, True)
        DIAGNOSTIC_PANEL = settings.get(plugin_settings.W_DIAGNOSTIC_PANEL, True)


def plugin_loaded():
    update_menu()


class PytoolsSetAutocompleteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(plugin_settings.F_AUTOCOMPLETE, True)
            settings.set(plugin_settings.F_AUTOCOMPLETE, not value)
            update_menu()

    def is_checked(self):
        return AUTOCOMPLETE


class PytoolsSetDocumentationCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(plugin_settings.F_DOCUMENTATION, True)
            settings.set(plugin_settings.F_DOCUMENTATION, not value)
            update_menu()

    def is_checked(self):
        return DOCUMENTATION


class PytoolsSetDocumentformattingCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(plugin_settings.F_DOCUMENT_FORMATTING, True)
            settings.set(plugin_settings.F_DOCUMENT_FORMATTING, not value)
            update_menu()

    def is_checked(self):
        return DOCUMENT_FORMATTING


class PytoolsSetDiagnosticCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(plugin_settings.F_DIAGNOSTIC, True)
            settings.set(plugin_settings.F_DIAGNOSTIC, not value)
            update_menu()

    def is_checked(self):
        return DIAGNOSTIC


class PytoolsSetValidateCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(plugin_settings.F_VALIDATE, True)
            settings.set(plugin_settings.F_VALIDATE, not value)
            update_menu()

    def is_checked(self):
        return VALIDATE


class PytoolsSetDiagnosticpanelCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(plugin_settings.W_DIAGNOSTIC_PANEL, True)
            settings.set(plugin_settings.W_DIAGNOSTIC_PANEL, not value)
            update_menu()

    def is_checked(self):
        return DIAGNOSTIC_PANEL
