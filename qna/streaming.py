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
        logging.info("Starting to stream LLM")

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        logging.debug(f"token: {token}")
        self.buffer += token

        # Check if the last token ended with a numbered list pattern, and if so, don't break on the following period
        if re.search(r'\d+\.\s', token) and any(token.endswith(t) for t in self.tokens):
            return

        # If the token ends with one of the specified ending tokens, write the buffer to the content buffer
        if any(token.endswith(t) for t in self.tokens):
            self.content_buffer.write(self.buffer)
            self.buffer = ""

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.content_buffer.write(self.buffer)  # Write the remaining buffer
        self.stream_finished.set() # Set the flag to signal that the stream has finished
        logging.info("Streaming LLM response ended successfully")


from langchain.chat_models import ChatOpenAI

import time
import logging

logging.basicConfig(level=logging.INFO)

def start_streaming_chat(question, 
                         vector_name,
                         chat_history=[],
                         wait_time=5):
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
        final_result = qna(question, vector_name, chat_history, stream_llm=llm_stream)
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
    else:
        logging.info(f"Stream has ended after {round(time.time() - start, 2)} seconds")
        logging.info(f"Sending final full message plus sources...")
        
    
    # if  you need it to stop it elsewhere use 
    # stop_event.set()

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