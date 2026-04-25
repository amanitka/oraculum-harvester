"""Side-effect imports: each module attaches a `@broker.subscriber`.

Add a new line here whenever a new topic subscriber lands. The import
itself is sufficient; the decorator registers with the broker on first
evaluation.
"""

from analyst.subscribers import balance_sheet  # noqa: F401
from analyst.subscribers import cash_flow_statement  # noqa: F401
from analyst.subscribers import income_statement  # noqa: F401
from analyst.subscribers import share_price  # noqa: F401
from analyst.subscribers import ticker  # noqa: F401
