import logging

logging.basicConfig(level=logging.INFO)
from qna.streaming import start_streaming_chat

question = "How many days is it since 1978-07-20 if today is 18th August 2023"
vector_name = "edmonbrain_agent"
chat_history = []

# You can then call the function to start the streaming chat
# Call the function and print the content that's yielded
for content in start_streaming_chat(question, vector_name, chat_history):
    print("Final return: " + content)
