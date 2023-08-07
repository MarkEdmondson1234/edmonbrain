import logging

logging.basicConfig(level=logging.ERROR)
from qna.streaming import start_streaming_chat

question = "What is the meaning of life?"
vector_name = "edmonbrain"
chat_history = []

# You can then call the function to start the streaming chat
# Call the function and print the content that's yielded
for content in start_streaming_chat(question, vector_name, chat_history):
    print(content)
