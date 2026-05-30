import pandas as pd
import logging

logger = logging.getLogger('etl')

class ExcelExtractor:
    def extract(self, path: str) -> pd.DataFrame:
        logger.info(f"ExcelExtractor: leyendo {path}")
        df = pd.read_excel(path, engine='openpyxl')
        logger.info(f"  → {len(df)} filas, {len(df.columns)} columnas")
        return df

class CSVExtractor:
    def extract(self, path: str) -> pd.DataFrame:
        logger.info(f"CSVExtractor: leyendo {path}")
        try:
            df = pd.read_csv(path, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding='latin-1')
        logger.info(f"  → {len(df)} filas, {len(df.columns)} columnas")
        return df
