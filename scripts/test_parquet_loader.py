import pandas as pd
import numpy as np
import math

df = pd.DataFrame({"a": [1.0, np.nan, math.nan]})
raw_records = df.to_dict(orient="records")
records = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in raw_records]
print(records)
