"""Side-effect imports: each module attaches a `@broker.subscriber`.

Add a new line here whenever a new subscriber lands. The import itself
is sufficient; the decorator registers with the broker on first
evaluation.
"""

from harvester.subscribers import request  # noqa: F401
