from langchain.document_loaders.unstructured import UnstructuredFileLoader
from langchain.document_loaders.unstructured import UnstructuredAPIFileLoader
from langchain.document_loaders import UnstructuredURLLoader
#from langchain.document_loaders import GoogleDriveLoader
from qna.googledrive_patch import GoogleDriveLoader
from googleapiclient.errors import HttpError

import logging
import pathlib
import os
import shutil
from urllib.parse import urlparse, unquote

# utility functions
def convert_to_txt(file_path):
    file_dir, file_name = os.path.split(file_path)
    file_base, file_ext = os.path.splitext(file_name)
    txt_file = os.path.join(file_dir, f"{file_base}.txt")
    shutil.copyfile(file_path, txt_file)
    return txt_file


from pydantic import BaseModel, Field
from typing import Optional

class MyGoogleDriveLoader(GoogleDriveLoader):
    url: Optional[str] = Field(None)

    def __init__(self, url, *args, **kwargs):
        super().__init__(*args, **kwargs, file_ids=['dummy']) # Pass dummy value
        self.url = url

    def _extract_id(self, url):
        parsed_url = urlparse(unquote(url))
        path_parts = parsed_url.path.split('/')
        
        # Iterate over the parts
        for part in path_parts:
            # IDs are typically alphanumeric and at least a few characters long
            # So let's say that to be an ID, a part has to be at least 15 characters long
            if all(char.isalnum() or char in ['_', '-'] for char in part) and len(part) >= 15:
                return part
        
        # Return None if no ID was found
        return None

    def load_from_url(self, url: str):
        id = self._extract_id(url)

        from googleapiclient.discovery import build

        # Identify type of URL
        try:
            service = build("drive", "v3", credentials=self._load_credentials())
            file = service.files().get(fileId=id).execute()
        except HttpError as err:
            logging.error(f"Error loading file {file}: {str(err)}")
            raise

        mime_type = file["mimeType"]

        if "folder" in mime_type:
            # If it's a folder, load documents from the folder
            return self._load_documents_from_folder(id)
        else:
            # If it's not a folder, treat it as a single file
            if mime_type == "application/vnd.google-apps.document":
                return [self._load_document_from_id(id)]
            elif mime_type == "application/vnd.google-apps.spreadsheet":
                return self._load_sheet_from_id(id)
            elif mime_type == "application/pdf":
                return [self._load_file_from_id(id)]
            else:
                return []


def read_gdrive_to_document(url: str, metadata: dict = None):

    logging.info(f"Reading gdrive doc from {url}")

    loader = MyGoogleDriveLoader(url=url)
    docs = loader.load_from_url(url)
    
    if docs is None or len(docs) == 0:
        return None
    
    if metadata is not None:
        for doc in docs:
            doc.metadata.update(metadata)
    
    logging.info(f"GoogleDriveLoader read {len(docs)} doc(s) from {url}")

    return docs

def read_url_to_document(url: str, metadata: dict = None):
    
    loader = UnstructuredURLLoader(urls=[url])
    docs = loader.load()
    if metadata is not None:
        for doc in docs:
            doc.metadata.update(metadata)
    
    logging.info(f"UnstructuredURLLoader docs: {docs}")
    
    return docs

def read_file_to_document(gs_file: pathlib.Path, split=False, metadata: dict = None):
    
    try:
        logging.info(f"Sending {gs_file} to UnstructuredAPIFileLoader")
        loader = UnstructuredAPIFileLoader(gs_file, mode="elements", api_key="FAKE_API_KEY")
        
        if split:
            # only supported for some file types
            docs = loader.load_and_split()
        else:
            docs = loader.load()
            logging.info(f"Loaded docs for {gs_file} from UnstructuredAPIFileLoader")
    except ValueError as e:
        logging.info(f"Error for {gs_file} from UnstructuredAPIFileLoader: {str(e)}")
        if "file type is not supported in partition" in str(e):
            logging.info("trying locally via .txt conversion")
            txt_file = None
            try:
                # Convert the file to .txt and try again
                txt_file = convert_to_txt(gs_file)
                loader = UnstructuredFileLoader(txt_file, mode="elements")
                if split:
                    docs = loader.load_and_split()
                else:
                    docs = loader.load()

            except Exception as inner_e:
                raise Exception("An error occurred during txt conversion or loading.") from inner_e

            finally:
                # Ensure cleanup happens if txt_file was created
                if txt_file is not None and os.path.exists(txt_file):
                    os.remove(txt_file)

    for doc in docs:
        #doc.metadata["file_sha1"] = file_sha1
        logging.info(f"doc_content: {doc.page_content[:30]}")
        if metadata is not None:
            doc.metadata.update(metadata)
    
    logging.info(f"gs_file:{gs_file} read into {len(docs)} docs")

    return docs