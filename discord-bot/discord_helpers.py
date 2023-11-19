import json
import os
import discord

def select_vectorname(message, bot_mention, vectornames, config):
    user_id = message.author.id

    # First, check if the user has set a vectorname using the slash command
    if user_id in vectornames:
        return vectornames[user_id]

    # If not, fall back to the config file
    if message.guild is not None:  
        server_name = message.guild.name
        if server_name in config:
            bot_lookup = bot_mention.replace('<','').replace('>','').replace('@','').strip()
            vector_name = config[server_name].get(bot_lookup)
            if vector_name:
                print(f'Guild: {server_name} - bot_lookup: {bot_lookup} - vector_name: {vector_name}')
                # Set this as the default vectorname for the user
                vectornames[user_id] = vector_name
                return vector_name

        raise ValueError(f"Could not find a configured vector for server_name: {server_name}")
    
    raise ValueError(f"Could not find a guild in message: {message}")


async def process_streamed_response(response, new_thread, thinking_message):
    json_buffer = ""
    inside_json = False
    inside_question = False
    question_buffer = ""
    first = True
    print("Start streaming response:")

    async for chunk in response.content.iter_any():
        chunk_content = chunk.decode('utf-8')

        print("Stream: " + str(chunk_content))

        # Update the "Thinking..." message on the first chunk
        if first:
            await thinking_message.edit(content="**Response:**")
            first=False

        # Handling question blocks
        if '€€Question€€' in chunk_content:
            inside_question = True

        if inside_question:
            question_buffer += chunk_content
            if '€€End Question€€' in question_buffer:
                end_index = question_buffer.find('€€End Question€€') + len('€€End Question€€')
                await chunk_send(new_thread, question_buffer[:end_index])
                inside_question = False

                chunk_content = question_buffer[end_index:]
                question_buffer = ""
            continue  # Skip further processing for this chunk

        # Check for both START and END delimiters in the chunk
        if '###JSON_START###' in chunk_content and '###JSON_END###' in chunk_content:
            content_before_json = chunk_content.split('###JSON_START###')[0]
            json_data_str = chunk_content.split('###JSON_START###')[1].split('###JSON_END###')[0]
            
            # Return or process the content before the JSON delimiter
            if content_before_json:
                await chunk_send(new_thread, content_before_json)

            try:
                json_data = json.loads(json_data_str)
                return json_data
            except Exception as err:
                print(f"Could not parse JSON data: {str(err)}")
                return []

        # Handle the START delimiter (without the END delimiter in the chunk)
        elif '###JSON_START###' in chunk_content:
            print("Found JSON_START")
            content_before_json = chunk_content.split('###JSON_START###')[0]
            
            # Return or process the content before the JSON delimiter
            if content_before_json:
                await chunk_send(new_thread, content_before_json)

            print("Streaming JSON starting...")
            json_buffer = chunk_content.split('###JSON_START###')[1]
            inside_json = True

        # Handle JSON content continuation
        elif inside_json:
            json_buffer += chunk_content
            if '###JSON_END###' in chunk_content:
                print("Found JSON_END")
                json_data_str = json_buffer.split('###JSON_END###')[0]
                json_data = json.loads(json_data_str)
                inside_json = False
                json_buffer = ""
                return json_data
        else:
            # Handle regular chunk content
            print("Streaming...")
            await chunk_send(new_thread, chunk_content)

    return None


def load_config(filename):
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # Join the script directory with the filename
    config_path = os.path.join(script_dir, filename)

    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def load_config_key(keys):
    value = load_config('config.json')
    for key in keys:
        value = value.get(key, None)
        if value is None:
            return False
    return value

async def chunk_send(channel, message):
    chunks = [message[i:i+1500] for i in range(0, len(message), 1500)]
    for chunk in chunks:
        if len(chunk) > 0:
            await channel.send(chunk)

async def make_chat_history(new_thread, bot_mention, client_user):
    history = []
    async for msg in new_thread.history(limit=30):
        if msg.content.startswith(f"*Reply to {bot_mention}"):
            continue
        if msg.content.startswith("*Use !help"):
            continue
        if msg.content.startswith("**source**:"):
            continue
        if msg.content.startswith("**url**:"):
            continue
        if msg.content.startswith("*Response:*"):
            continue
        if msg.content.startswith("Deleting source:"):
            continue
        history.append(msg)

    print(f"client_user: {client_user}") # Debug print
    # Reverse the messages to maintain the order of conversation
    chat_history = []
    last_author = None
    group_content = ""
    group_embeds = []
    for msg in reversed(history):
        print(f"msg.author: {msg.author}, msg.author.bot: {msg.author.bot}") # Debug print
        if msg.author == client_user:
            author = "AI"
        elif msg.author.bot:
            author = str(msg.author)  # This will use the bot's username
        else:
            author = "Human"
        clean_content = msg.content.replace(bot_mention, '').strip()
        embeds = [embed.to_dict() for embed in msg.embeds]

        print(f'-msg-: {clean_content[:10]}')
        
        if last_author is not None and last_author != author:
            chat_history.append({"name": last_author, "content": group_content.strip(), "embeds": group_embeds})
            group_content = ""
            group_embeds = []
        
        group_content += " " + clean_content
        group_embeds.extend(embeds)
        last_author = author

    if group_content:  # Don't forget the last group!
        chat_history.append({"name": last_author, "content": group_content.strip(), "embeds": group_embeds})

    #print(f"chat_history: {chat_history}")

    return chat_history




async def make_new_thread(message, clean_content):
    # Check if the message was sent in a thread or a private message
    if isinstance(message.channel, (discord.Thread, discord.DMChannel)):
        new_thread = message.channel
    else:
        if len(clean_content) < 5:
            thread_name = "Baaa--zzz"
        else:
            thread_name = f"Baa-zzz - {clean_content[:40]}"
        # If it's not a thread, create a new one
        new_thread = await message.channel.create_thread(
            name=thread_name, 
            message=message)

    return new_thread