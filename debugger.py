from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage

import time
import logging

logging.basicConfig(level=logging.INFO)

def start_streaming_chat(wait_time=5):
    from threading import Thread
    from qna.streaming import ContentBuffer, BufferStreamingStdOutCallbackHandler

    # Initialize the chat
    content_buffer = ContentBuffer()
    chat_callback_handler = BufferStreamingStdOutCallbackHandler(content_buffer=content_buffer, tokens=".!?\n")

    chat = ChatOpenAI(
        model="gpt-4",
        streaming=True,
        callbacks=[chat_callback_handler],
        temperature=0
    )

    # Start the chat in a separate thread
    def start_chat():
        chat([HumanMessage(content="Can you tell me about particle physics?")])

    chat_thread = Thread(target=start_chat)
    chat_thread.start()

    start = time.time()
    while not chat_callback_handler.stream_finished.is_set():
        time.sleep(wait_time) # Wait for x seconds
        logging.info(f"heartbeat - {round(time.time() - start, 2)} seconds")
        content_to_send = content_buffer.read()

        if content_to_send:
            logging.info(f"==\n{content_to_send}")
            content_buffer.clear()
        else:
            logging.info("No content to send")
    else:
        logging.info(f"Stream has ended after {round(time.time() - start, 2)} seconds")
        
    # Stop the stream thread
    chat_thread.join()

# You can then call the function to start the streaming chat
start_streaming_chat()
