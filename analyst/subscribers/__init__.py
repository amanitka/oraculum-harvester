"""Side-effect imports: each module attaches a `@broker.subscriber`.

Add a new line here whenever a new topic subscriber lands. The import
itself is sufficient; the decorator registers with the broker on first
evaluation.
"""

import analyst.subscribers.data_file_ready  # noqa: F401
