# Imports dataclass, which helps us create classes for storing data
from dataclasses import dataclass

# Imports a LangChain tool that splits long text into smaller chunks.
from langchain_text_splitters import RecursiveCharacterTextSplitter

# imports pageText class from parser.py 
from app.services.parser import PageText


# This class store three things for each chunk
# so Each chunk has these 3 things
@dataclass
class ChunkData:
    chunk_index: int  # The chunk's position in the overall list, starting from 0.
    page: int  # The original PDF page number the chunk came from.
    content: str # The actual text inside the chunk.

# This function takes the extracted PDF pages and splits their text into  chunks.
def chunk_pages(
    pages: list[PageText], # A list containing the page numbers and extracted text from the PDF as PageText objects
    chunk_size: int = 1000, # Each chunk can contain up to 1,000 characters by default.
    chunk_overlap: int = 150, # Neighboring chunks can share 150 characters to preserve context
) -> list[ChunkData]:

    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,

        # It first tries to split at paragraph breaks, then line breaks, then sentence boundaries, then spaces. If necessary, it splits at individual characters.
        separators=["\n\n", "\n", ". ", " ", ""], # Tells the splitter which boundaries to try first when dividing text.
    )

    # empty list that will store the generated ChunkData objects.
    chunks: list[ChunkData] = []
    index = 0

    # Goes through each PageText object in the pages list, one page at a time.
    for page in pages:
        # Takes the text from the current page and splits it into smaller chunks.
        for piece in splitter.split_text(page.text):
            # removes unnecessary whitespace from the beginning and end of the chunk.
            piece = piece.strip()
            # if chunk is not empty, store the chunk
            if piece:
                # creates a chunk object with chunk index, The orginal pdf page number, The chunks text and add to list
                chunks.append(ChunkData(chunk_index=index, page=page.page, content=piece))
                index += 1

    # return list of chunks 
    return chunks