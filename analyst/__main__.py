import logging
from analyst.consumer import AnalystConsumer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    consumer = AnalystConsumer()
    try:
        consumer.consume()
    except KeyboardInterrupt:
        logging.info("Shutting down consumer...")
