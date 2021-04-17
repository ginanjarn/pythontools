import sublime
import sublime_plugin
from contextlib import contextmanager

SETTINGS_BASENAME = "Pytools.sublime-settings"

# Settings name
F_AUTOCOMPLETE = "autocomplete"
F_DOCUMENTATION = "documentation"
F_DOCUMENT_FORMATTING = "document_formatting"
F_DIAGNOSTIC = "diagnostic"
F_VALIDATE = "validate"
W_ABSOLUTE_IMPORT = "absolute_import"

# menu check state holder
AUTOCOMPLETE = False
DOCUMENTATION = False
DOCUMENT_FORMATTING = False
DIAGNOSTIC = False
VALIDATE = False
ABSOLUTE_IMPORT = False


@contextmanager
def load_settings(save=False):
    sublime_settings = sublime.load_settings(SETTINGS_BASENAME)
    yield sublime_settings

    if save:
        sublime.save_settings(SETTINGS_BASENAME)


def update_menu():
    """update menu check state"""

    global AUTOCOMPLETE
    global DOCUMENTATION
    global DOCUMENT_FORMATTING
    global DIAGNOSTIC
    global VALIDATE
    global ABSOLUTE_IMPORT

    with load_settings(save=False) as settings:
        AUTOCOMPLETE = settings.get(F_AUTOCOMPLETE, True)
        DOCUMENTATION = settings.get(F_DOCUMENTATION, True)
        DOCUMENT_FORMATTING = settings.get(F_DOCUMENT_FORMATTING, True)
        DIAGNOSTIC = settings.get(F_DIAGNOSTIC, True)
        VALIDATE = settings.get(F_VALIDATE, True)
        ABSOLUTE_IMPORT = settings.get(W_ABSOLUTE_IMPORT, True)


def plugin_loaded():
    update_menu()


class PytoolsSetAutocompleteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_AUTOCOMPLETE, True)
            settings.set(F_AUTOCOMPLETE, not value)
            update_menu()

    def is_checked(self):
        return AUTOCOMPLETE


class PytoolsSetDocumentationCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_DOCUMENTATION, True)
            settings.set(F_DOCUMENTATION, not value)
            update_menu()

    def is_checked(self):
        return DOCUMENTATION


class PytoolsSetDocumentformattingCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_DOCUMENT_FORMATTING, True)
            settings.set(F_DOCUMENT_FORMATTING, not value)
            update_menu()

    def is_checked(self):
        return DOCUMENT_FORMATTING


class PytoolsSetDiagnosticCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_DIAGNOSTIC, True)
            settings.set(F_DIAGNOSTIC, not value)
            update_menu()

    def is_checked(self):
        return DIAGNOSTIC


class PytoolsSetValidateCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_VALIDATE, True)
            settings.set(F_VALIDATE, not value)
            update_menu()

    def is_checked(self):
        return VALIDATE


class PytoolsSetAbsoluteimportCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(W_ABSOLUTE_IMPORT, True)
            settings.set(W_ABSOLUTE_IMPORT, not value)
            update_menu()

    def is_checked(self):
        return ABSOLUTE_IMPORT
