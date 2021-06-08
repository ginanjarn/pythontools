"""Plugin adapter

This module used to adapt function that unavailabe in sublime text 3

"""

import sublime


try:
    from sublime import CompletionItem

    kind_map = {
        "instance": sublime.KIND_VARIABLE,
        "statement": sublime.KIND_VARIABLE,
        "param": sublime.KIND_VARIABLE,
        "property": sublime.KIND_VARIABLE,
        "function": sublime.KIND_FUNCTION,
        "class": sublime.KIND_TYPE,
        "module": sublime.KIND_NAMESPACE,
        "keyword": sublime.KIND_KEYWORD,
    }

    def convert_kind(kind):
        return kind_map.get(kind, sublime.KIND_AMBIGUOUS)

    class CompletionItem(CompletionItem):
        def __init__(
            self,
            trigger,
            annotation="",
            completion="",
            completion_format=0,
            kind=0,
            details="",
        ):

            super().__init__(
                trigger,
                annotation=annotation,
                completion=completion,
                completion_format=completion_format,
                kind=convert_kind(kind),
                details=details,
            )


except ImportError:

    class CompletionItem(list):
        __slots__ = [
            "trigger",
            "annotation",
            "completion",
            "completion_format",
            "kind",
            "details",
            "flags",
        ]

        def __init__(
            self,
            trigger,
            annotation="",
            completion="",
            completion_format=0,
            kind=0,
            details="",
        ):

            self.trigger = trigger
            self.annotation = annotation
            self.completion = completion
            self.completion_format = completion_format
            self.kind = kind
            self.details = details
            self.flags = 0

            super().__init__(
                ("{trigger}\t{kind}".format(trigger=trigger, kind=kind), completion,)
            )

        def __repr__(self):
            return (
                "CompletionItem(%s, annotation=%s, completion=%s, completion_format=%s, kind=%s, details=%s)"
                % (
                    repr(self.trigger),
                    repr(self.annotation),
                    repr(self.completion),
                    repr(self.completion_format),
                    repr(self.kind),
                    repr(self.details),
                )
            )
