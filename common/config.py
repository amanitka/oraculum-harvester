from pathlib import Path
from envyaml import EnvYAML

current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
CONFIG_PATH = root_dir / 'config.yaml'


# Initiate config parser
class Config:

    def __init__(self):
        self._config_file: EnvYAML = EnvYAML(CONFIG_PATH)
        self.simfin_api_key: str = self._config_file.get('simFin.apiKey')


# Initiate config
config: Config = Config()
