import json
import logging

from kafka import KafkaConsumer
from sqlmodel import Session
from pydantic import ValidationError

from common.config import config
from common.domain.ticker import Ticker
from analyst.db import engine, upsert_ticker

logger = logging.getLogger(__name__)


class AnalystConsumer:
    def __init__(self) -> None:
        self.consumer = KafkaConsumer(
            config.topics.ticker,
            bootstrap_servers=config.kafka_brokers,
            group_id=config.analyst_consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # We commit manually after processing
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

    def consume(self) -> None:
        logger.info(f"Starting analyst consumer on topics: {config.topics.ticker}")

        for message in self.consumer:
            logger.debug(f"Received message: {message.value}")
            try:
                # Parse as Pydantic model
                ticker = Ticker.model_validate(message.value)

                # Upsert into DB
                with Session(engine) as session:
                    upsert_ticker(session, ticker)

                # Commit offset after successful db write
                self.consumer.commit()
                logger.info(f"Successfully processed and stored ticker {ticker.symbol}")

            except ValidationError as e:
                logger.error(f"Validation error for message {message.value}: {e}")
                # We commit anyway to not get stuck on bad messages
                self.consumer.commit()
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                # In a real system, you might not want to commit here or send to a DLQ
                # For now, we don't commit to retry, but be careful of infinite loops


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    consumer = AnalystConsumer()
    consumer.consume()
