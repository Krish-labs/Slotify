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

    def is_source_load_distribution(self, file_path: str) -> bool:
        frame = pd.read_excel(file_path, sheet_name=0, header=None, nrows=110)
        for _, row in frame.iterrows():
            values = [str(value).strip() for value in row.iloc[:2].tolist()]
            if values[0].lower().startswith("sr.") and values[1] == "Name of Faculty":
                return True
        return False

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
