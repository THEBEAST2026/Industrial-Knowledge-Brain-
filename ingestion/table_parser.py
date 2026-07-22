import pandas as pd
import camelot
from schemas import Chunk
import hashlib

def parse_table_pdf(filepath: str, doc_type: str = "worklog") -> list[Chunk]:
    tables = camelot.read_pdf(filepath, pages="all", flavor="lattice")
    chunks = []
    for t_idx, table in enumerate(tables):
        df = table.df
        headers = df.iloc[0].tolist()
        for row_idx, row in df.iloc[1:].iterrows():
            row_text = ", ".join(f"{h}: {v}" for h, v in zip(headers, row))
            chunk_id = hashlib.md5(f"{filepath}-{t_idx}-{row_idx}".encode()).hexdigest()[:12]
            chunks.append(Chunk(
                chunk_id=chunk_id, source_doc=filepath, doc_type=doc_type,
                content=row_text, row_index=int(row_idx)
            ))
    return chunks

def parse_csv_xlsx(filepath: str, doc_type: str = "worklog") -> list[Chunk]:
    df = pd.read_excel(filepath) if filepath.endswith(("xlsx","xls")) else pd.read_csv(filepath)
    chunks = []
    for row_idx, row in df.iterrows():
        row_text = ", ".join(f"{col}: {row[col]}" for col in df.columns)
        chunk_id = hashlib.md5(f"{filepath}-{row_idx}".encode()).hexdigest()[:12]
        chunks.append(Chunk(
            chunk_id=chunk_id, source_doc=filepath, doc_type=doc_type,
            content=row_text, row_index=int(row_idx)
        ))
    return chunks