from __future__ import annotations

from common.config import config
from common.domain import (
    DataFileReadyEvent,
    DataBatchCompleteEvent,
)
from harvester.app import broker

data_file_ready = broker.publisher(config.topics.data_file_ready, schema=DataFileReadyEvent)

# Published on the same topic — Java listener distinguishes by event_type field:
#   "oraculum.data_file_ready"     → route to FileLoadService
#   "oraculum.data_batch_complete" → route to postProcess
batch_complete = broker.publisher(config.topics.data_file_ready, schema=DataBatchCompleteEvent)
