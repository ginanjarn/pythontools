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


@contextmanager
def load_settings(save=False):
    sublime_settings = sublime.load_settings(SETTINGS_BASENAME)
    yield sublime_settings
    if save:
        sublime.save_settings(SETTINGS_BASENAME)


class PytoolsSetAutocompleteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_AUTOCOMPLETE, True)
            settings.set(F_AUTOCOMPLETE, not value)

    def is_enabled(self):
        return self.view.match_selector(0, "source.python")

    def is_checked(self):
        with load_settings() as settings:
            return settings.get(F_AUTOCOMPLETE, True)


class PytoolsSetDocumentationCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_DOCUMENTATION, True)
            settings.set(F_DOCUMENTATION, not value)

    def is_enabled(self):
        return self.view.match_selector(0, "source.python")

    def is_checked(self):
        with load_settings() as settings:
            return settings.get(F_DOCUMENTATION, True)


class PytoolsSetDocumentformattingCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_DOCUMENT_FORMATTING, True)
            settings.set(F_DOCUMENT_FORMATTING, not value)

    def is_enabled(self):
        return self.view.match_selector(0, "source.python")

    def is_checked(self):
        with load_settings() as settings:
            return settings.get(F_DOCUMENT_FORMATTING, True)


class PytoolsSetDiagnosticCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_DIAGNOSTIC, True)
            settings.set(F_DIAGNOSTIC, not value)

    def is_enabled(self):
        return self.view.match_selector(0, "source.python")

    def is_checked(self):
        with load_settings() as settings:
            return settings.get(F_DIAGNOSTIC, True)


class PytoolsSetValidateCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(F_VALIDATE, True)
            settings.set(F_VALIDATE, not value)

    def is_enabled(self):
        return self.view.match_selector(0, "source.python")

    def is_checked(self):
        with load_settings() as settings:
            return settings.get(F_VALIDATE, True)


class PytoolsSetAbsoluteimportCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        with load_settings(save=True) as settings:
            value = settings.get(W_ABSOLUTE_IMPORT, True)
            settings.set(W_ABSOLUTE_IMPORT, not value)

    def is_enabled(self):
        return self.view.match_selector(0, "source.python")

    def is_checked(self):
        with load_settings() as settings:
            return settings.get(W_ABSOLUTE_IMPORT, True)
