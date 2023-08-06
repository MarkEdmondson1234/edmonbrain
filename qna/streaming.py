import threading
import logging

from typing import Any, Dict, List, Union
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.schema import LLMResult

logging.basicConfig(level=logging.INFO)

class ContentBuffer:
    def __init__(self):
        self.content = ""
        logging.debug("Content buffer initialized")
    
    def write(self, text: str):
        self.content += text
        logging.debug(f"Written {text} to buffer")
    
    def read(self) -> str:
        logging.debug(f"Read content from buffer")    
        return self.content

    def clear(self):
        logging.debug(f"Clearing content buffer")
        self.content = ""
    

class BufferStreamingStdOutCallbackHandler(StreamingStdOutCallbackHandler):
    def __init__(self, content_buffer: ContentBuffer, tokens: str = ".?!\n", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_buffer = content_buffer

        self.tokens = tokens
        self.buffer = ""
        self.stream_finished = threading.Event()
        logging.info("Starting to stream LLM")

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        logging.debug(f"token: {token}")
        self.buffer += token
        if any(token.endswith(t) for t in self.tokens):
            self.content_buffer.write(self.buffer)
            self.buffer = ""

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.content_buffer.write(self.buffer)  # Write the remaining buffer
        self.stream_finished.set() # Set the flag to signal that the stream has finished
        logging.info("Streaming LLM response ended successfully")


