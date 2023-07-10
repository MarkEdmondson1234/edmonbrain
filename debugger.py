import qna.question_service as qs
import webapp.bot_help as bot_help

user_input = "Testing "
vector_name = "edmonbrain_vertex"
chat_history=None
#chat_history = [{'name': 'AI', 'content': 'Based on the context provided, there is no information regarding two flavors of English that you ask about. Therefore, I cannot provide a specific answer. However, common variations of English that people often inquire about include British English and American English.', 'embeds': []}]
paired_messages = bot_help.extract_chat_history(chat_history)
print(f"Paired messages:{paired_messages}")
bot_output = qs.qna(user_input, vector_name, chat_history=paired_messages)

print(bot_output['answer'])
