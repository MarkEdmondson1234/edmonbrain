import threading
import logging
import json
import re

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
        self.in_code_block = False
        self.in_question_block = False
        self.question_buffer = ""
        logging.info("Starting to stream LLM")

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        logging.debug(f"token: {token}")

        # Check for question start delimiter
        if '€€Question€€' in token:
            self.in_question_block = True
            self.question_buffer = token  # Start capturing the question block content
            return  # Skip processing this token further

        # Check for question end delimiter
        if self.in_question_block:
            self.question_buffer += token  # Continue capturing the question block content

            if '€€End Question€€' in token:
                self.content_buffer.write(self.question_buffer)  # Directly write the entire question block
                self.question_buffer = ""  # Clear the question buffer
                self.in_question_block = False
                return  # Skip processing this token further


        # If not inside a question block, handle normally
        if not self.in_question_block:
            self.buffer += token

            # Toggle the code block flag if the delimiter is encountered
            if '```' in token:
                self.in_code_block = not self.in_code_block

            # Process the buffer if not inside a code block
            if not self.in_code_block and not self.in_question_block:
                self._process_buffer()



    def _process_buffer(self):
        # If the buffer contains the entire question block, write the entire buffer.
        if '€€Question€€' in self.buffer and '€€End Question€€' in self.buffer:
            self.content_buffer.write(self.buffer)
            self.buffer = ""
            return

        # Check for the last occurrence of a newline followed by a numbered list pattern
        matches = list(re.finditer(r'\n(\d+\.\s)', self.buffer))
        if matches:
            # If found, write up to the start of the last match, and leave the rest in the buffer
            last_match = matches[-1]
            start_of_last_match = last_match.start() + 1  # Include the newline in the split
            self.content_buffer.write(self.buffer[:start_of_last_match])
            self.buffer = self.buffer[start_of_last_match:]
        else:
            # If not found, and the buffer ends with one of the specified ending tokens, write the entire buffer
            if any(self.buffer.endswith(t) for t in self.tokens):
                self.content_buffer.write(self.buffer)
                self.buffer = ""

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:

        if self.buffer:
            # Process the remaining buffer content
            self.content_buffer.write(self.buffer)
            self.buffer = "" # Clear the remaining buffer
            logging.info("Flushing reamaining LLM response buffer")

        self.stream_finished.set() # Set the flag to signal that the stream has finished
        logging.info("Streaming LLM response ended successfully")


from langchain.chat_models import ChatOpenAI

import time
import logging

logging.basicConfig(level=logging.INFO)

def start_streaming_chat(question, 
                         vector_name,
                         chat_history=[],
                         message_author=None,
                         wait_time=5,
                         timeout=120): # Timeout in seconds (2 minutes)
    from threading import Thread, Event
    from queue import Queue
    from qna.streaming import ContentBuffer, BufferStreamingStdOutCallbackHandler

    # Initialize the chat
    content_buffer = ContentBuffer()
    chat_callback_handler = BufferStreamingStdOutCallbackHandler(content_buffer=content_buffer, tokens=".!?\n")

    # only openai supports streaming for now
    llm_stream = ChatOpenAI(
        model="gpt-4",
        streaming=True,
        callbacks=[chat_callback_handler],
        temperature=0.3, 
        max_tokens=3000
    )

    result_queue = Queue()
    stop_event = Event()

    # Start the chat in a separate thread
    def start_chat(stop_event, result_queue):
        from qna.question_service import qna
        final_result = qna(question, vector_name, chat_history, stream_llm=llm_stream, message_author=message_author)
        result_queue.put(final_result)

    chat_thread = Thread(target=start_chat, args=(stop_event,result_queue))
    chat_thread.start()

    start = time.time()
    while not chat_callback_handler.stream_finished.is_set() and not stop_event.is_set():
        time.sleep(wait_time) # Wait for x seconds
        logging.info(f"heartbeat - {round(time.time() - start, 2)} seconds")
        content_to_send = content_buffer.read()

        if content_to_send:
            logging.info(f"==\n{content_to_send}")
            yield content_to_send
            content_buffer.clear()
        else:
            logging.info("No content to send")

        elapsed_time = time.time() - start
        if elapsed_time > timeout: # If the elapsed time exceeds the timeout
            logging.warning("Content production has timed out after 2 minutes")
            break
    else:
        logging.info(f"Stream has ended after {round(time.time() - start, 2)} seconds")
        logging.info(f"Sending final full message plus sources...")
        
    
    # if  you need it to stop it elsewhere use 
    # stop_event.set()
    content_to_send = content_buffer.read()
    if content_to_send:
        logging.info(f"==\n{content_to_send}")
        yield content_to_send
        content_buffer.clear()

    # Stop the stream thread
    chat_thread.join()

    # the json object with full response in 'answer' and the 'sources' array
    final_result = result_queue.get()

    # TODO: only discord for now - slack? gchat?

    discord_output = parse_output(final_result)
    discord_output = generate_discord_output(discord_output)

    yield f"###JSON_START###{discord_output}###JSON_END###"

def parse_output(bot_output):
    if 'source_documents' in bot_output:
        bot_output['source_documents'] = [document_to_dict(doc) for doc in bot_output['source_documents']]
    if bot_output.get("answer", None) is None or bot_output.get("answer") == "":
        bot_output['answer'] = "(No text was returned)"
    return bot_output

def document_to_dict(document):
    return {
        "page_content": document.page_content,
        "metadata": document.metadata
    }

def generate_discord_output(bot_output):
    source_documents = []
    if bot_output.get('source_documents', None) is not None:
        source_documents = []
        for doc in bot_output['source_documents']:
            metadata = doc.get("metadata",{})
            filtered_metadata = {}
            if metadata.get("source", None) is not None:
                filtered_metadata["source"] = metadata["source"]
            if metadata.get("type", None) is not None:
                filtered_metadata["type"] = metadata["type"]
            source_doc = {
                'page_content': doc["page_content"],
                'metadata': filtered_metadata
            }
            source_documents.append(source_doc)

    return json.dumps({
        'result': bot_output.get('answer', "No answer available"),
        'source_documents': source_documents
    })