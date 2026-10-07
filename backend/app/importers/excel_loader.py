from pathlib import Path

import pandas as pd


class ExcelLoader:
    def __init__(self):
        pass

    def load_load_distribution(self, file_path: str) -> pd.DataFrame:
        """Load load distribution Excel file"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        df = pd.read_excel(path)
        return df

    def load_timetable(self, file_path: str) -> pd.DataFrame:
        """Load timetable Excel file"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        df = pd.read_excel(path)
        return df

    def load_resources(self, file_path: str) -> pd.DataFrame:
        """Load resources Excel file"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        df = pd.read_excel(path)
        return df

    def load_faculty(self, file_path: str) -> pd.DataFrame:
        """Load faculty Excel file"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        df = pd.read_excel(path)
        return df

    def save_dataframe(self, df: pd.DataFrame, file_path: str):
        """Save DataFrame to Excel"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(path, index=False)
