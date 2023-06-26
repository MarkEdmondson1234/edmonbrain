import sys, os, requests
import tempfile

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

# app.py
from flask import Flask, render_template, request, jsonify
import logging
import bot_help
import gchat_help

app = Flask(__name__)
app.config['TRAP_HTTP_EXCEPTIONS'] = True

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/reindex', methods=['GET'])
def reindex():
    return render_template('reindex.html')

@app.route('/process_files', methods=['POST'])
def process_files():
    bucket_name = os.getenv('GCS_BUCKET', None)
    logging.info(f"bucket: {bucket_name}")

    uploaded_files = request.files.getlist('files')
    with tempfile.TemporaryDirectory() as temp_dir:
        vector_name = "edmonbrain"
        summaries = bot_help.handle_files(uploaded_files, temp_dir, vector_name)
        return jsonify({"summaries": summaries if summaries else ["No files were uploaded"]})

app_chat_history = []

@app.route('/process_input', methods=['POST'])
def process_input():
    # json input
    data = request.get_json()
    logging.info(f'Request data: {data}')

    user_input  = data.get('user_input', '')
    vector_name = 'edmonbrain' # replace with your vector name

    paired_messages = bot_help.extract_chat_history(app_chat_history)

    # ask the bot a question about the documents in the vectorstore
    bot_output = bot_help.send_to_qa(user_input, vector_name, chat_history=paired_messages)

    # append user message to chat history
    app_chat_history.append({'name': 'Human', 'content': user_input})
    
    # append bot message to chat history
    app_chat_history.append({'name': 'AI', 'content': bot_output['answer']})

    logging.info(f"bot_output: {bot_output}")

    return jsonify(bot_help.generate_webapp_output(bot_output))


@app.route('/discord/<vector_name>/message', methods=['POST'])
def discord_message(vector_name):
    data = request.get_json()
    user_input = data['content'].strip()  # Extract user input from the payload

    logging.info(f"discord_message: {data} to {vector_name}")

    chat_history = data.get('chat_history', None)
    paired_messages = bot_help.extract_chat_history(chat_history)

    command_response = bot_help.handle_special_commands(user_input, vector_name, paired_messages)
    if command_response is not None:
        return jsonify(command_response)

    bot_output = bot_help.send_to_qa(user_input, vector_name, chat_history=paired_messages)
    logging.info(f"bot_output: {bot_output}")
    
    discord_output = bot_help.generate_discord_output(bot_output)

    # may be over 4000 char limit for discord but discord bot chunks it up for output
    return jsonify(discord_output)

@app.route('/discord/<vector_name>/files', methods=['POST'])
def discord_files(vector_name):
    data = request.get_json()
    attachments = data.get('attachments', [])
    content = data.get('content', "").strip()
    chat_history = data.get('chat_history', [])

    logging.info(f'discord_files got data: {data}')
    with tempfile.TemporaryDirectory() as temp_dir:
        # Handle file attachments
        bot_output = []
        for attachment in attachments:
            # Download the file and store it temporarily
            file_url = attachment['url']
            file_name = attachment['filename']
            safe_file_name = os.path.join(temp_dir, file_name)
            response = requests.get(file_url)
            
            open(safe_file_name, 'wb').write(response.content)

            gs_file = bot_help.app_to_store(safe_file_name, 
                                            vector_name, 
                                            via_bucket_pubsub=True, 
                                            metadata={'discord_comment': content})
            bot_output.append(f"{file_name} uploaded to {gs_file}")

    # Format the response payload
    response_payload = {
        "summaries": bot_output
    }

    return response_payload, 200


@app.route('/pubsub_to_discord', methods=['POST'])
def pubsub_to_discord():
    if request.method == 'POST':
        data = request.get_json()
        try:
            message_data = bot_help.process_pubsub(data)
        
            if isinstance(message_data, str):
                logging.info(f'message_data is a string: {message_data}')
                the_data = message_data
            elif isinstance(message_data, dict):
                logging.info(f'message_data is a dict: {message_data}')
                # cloud build
                if message_data.get('status', None) is not None:
                    cloud_build_status = message_data.get('status')
                    the_data = {'type': 'cloud_build', 'status': cloud_build_status}
                    if cloud_build_status not in ['SUCCESS','FAILED']:
                        # don't send WORKING as it floods 
                        return cloud_build_status, 200
                elif message_data.get('textPayload', None) is not None:
                    # logging sink
                    the_data = {'type': 'logging_sink', 'textPayload': message_data.get('textPayload')}

            response = bot_help.discord_webhook(the_data)

            if response.status_code != 204:
                logging.info(f'Request to discord returned {response.status_code}, the response is:\n{response.text}')
            
            return 'ok', 200
        
        except Exception as err:
            logging.error(f'pubsub_to_discord error: {str(err)}')
            return 'error', 200

   
# needs to be done via Mailgun API
@app.route('/email', methods=['POST'])
def receive_email():
    # The email data will be in the request.form dictionary.
    # The exact structure of the data depends on how your email
    # service sends it. Check the service's documentation for details.
    email_data = request.form
    print(email_data)

    # Here you can add code to process the email data.

    return '', 200

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)

