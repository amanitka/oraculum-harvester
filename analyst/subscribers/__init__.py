"""Side-effect imports: each module attaches a `@broker.subscriber`.

Add a new line here whenever a new topic subscriber lands. The import
itself is sufficient; the decorator registers with the broker on first
evaluation.
"""

import analyst.subscribers.data_file_ready  # noqa: F401
import analyst.subscribers.analyze_ticker  # noqa: F401
import analyst.subscribers.market  # noqa: F401
import analyst.subscribers.industry  # noqa: F401
import analyst.subscribers.news_subscriber  # noqa: F401
