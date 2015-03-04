import re


_KWARG_RE = re.compile("(?:([-\w]+)=)?(.+)")


def parse_args_and_kwargs(parser, bits):
    """
    Parses template tag arguments and keyword arguments

    Returns a tuple ``args, kwargs``.

    Usage::

        @register.tag
        def custom(parser, token):
            return CustomNode(*parse_args_and_kwargs(parser,
                token.split_contents()[1:]))

        class CustomNode(template.Node):
            def __init__(self, args, kwargs):
                self.args = args
                self.kwargs = kwargs

            def render(self, context):
                args, kwargs = resolve_args_and_kwargs(context, self.args,
                    self.kwargs)
                return self._render(context, *args, **kwargs):

            def _render(self, context, ...):
                # The real workhorse
    """
    args = []
    kwargs = {}

    for bit in bits:
        match = _KWARG_RE.match(bit)
        key, value = match.groups()
        value = parser.compile_filter(value)
        if key:
            kwargs[str(key)] = value
        else:
            args.append(value)

    return args, kwargs


def resolve_args_and_kwargs(context, args, kwargs):
    """
    Resolves arguments and keyword arguments parsed by
    ``parse_args_and_kwargs`` using the passed context instance

    See ``parse_args_and_kwargs`` for usage instructions.
    """
    return (
        [v.resolve(context) for v in args],
        {k: v.resolve(context) for k, v in kwargs.items()},
    )
