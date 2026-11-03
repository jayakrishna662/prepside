from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.parser import PageText


@dataclass
class ChunkData:
    chunk_index: int
    page: int
    content: str


def chunk_pages(
    pages: list[PageText],
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[ChunkData]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[ChunkData] = []
    index = 0

    for page in pages:
        for piece in splitter.split_text(page.text):
            piece = piece.strip()
            if piece:
                chunks.append(ChunkData(chunk_index=index, page=page.page, content=piece))
                index += 1

    return chunks