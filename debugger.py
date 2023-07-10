import qna.question_service as qs
from qna.app import extract_chat_history

user_input = "What vegetables do I like?"
vector_name = "edmonbrain"
chat_history=None
chat_history = [{'name': 'AI', 'content': 'Here are four ripe green tomatoes', 'embeds': []},
                 {'name': 'Human', 'content': 'I love tomatoes, thanks!'},
                 {'name': 'AI', 'content': 'Here are four potatoes', 'embeds': []},
                 {'name': 'Human', 'content': 'I hate potatoes, ugh!'}]
paired_messages = extract_chat_history(chat_history)
print(f"Paired messages:{paired_messages}")
bot_output = qs.qna(user_input, vector_name, chat_history=paired_messages)

print(bot_output['answer'])
