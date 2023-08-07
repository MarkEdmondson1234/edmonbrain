import os
import discord
import aiohttp
import json
from dotenv import load_dotenv
import shlex

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN', None)  # Get your bot token from the .env file
FLASKURL = os.getenv('FLASK_URL', None)
STREAMURL = os.getenv('STREAM_URL', None)

async def process_streamed_response(response, new_thread):
    json_buffer = ""
    inside_json = False
    async for chunk in response.content.iter_any(1500):
        chunk_content = chunk.decode('utf-8')

        # Handle JSON delimiter across chunk boundaries
        if inside_json:
            json_buffer += chunk_content
            if '###JSON_END###' in chunk_content:
                json_data_str = json_buffer.split('###JSON_END###')[0]
                json_data = json.loads(json_data_str)
                inside_json = False
                json_buffer = ""
                return json_data
        elif '###JSON_START###' in chunk_content and '###JSON_END###' in chunk_content:
            json_data_str = chunk_content.split('###JSON_START###')[1].split('###JSON_END###')[0]
            json_data = json.loads(json_data_str)
            return json_data
        elif '###JSON_START###' in chunk_content:
            json_buffer = chunk_content.split('###JSON_START###')[1]
            inside_json = True
        else:
            # Handle regular chunk content
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

# Load the config file at the start of your program
config = load_config('config.json')

def select_vectorname(message, bot_mention):

    if message.guild is not None:  
        server_name = message.guild.name
        if server_name in config:
            bot_lookup = bot_mention.replace('<','').replace('>','').replace('@','').strip()
            vector_name = config[server_name][bot_lookup]
            print(f'Guild: {server_name} - bot_lookup: {bot_lookup} - vector_name: {vector_name}')
            return vector_name

        raise ValueError(f"Could not find a configured vector for server_name: {server_name}")
    
    raise ValueError(f"Could not find a guild in message: {message}")



if TOKEN is None or FLASKURL is None:
    raise ValueError("Must set env vars DISCORD_TOKEN, FLASK_URL in .env")

intents = discord.Intents.default()
intents.messages = True
intents.dm_messages = True  # Enable DM messages

client = discord.Client(intents=intents)

async def chunk_send(channel, message):
    chunks = [message[i:i+1500] for i in range(0, len(message), 1500)]
    for chunk in chunks:
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

    # Reverse the messages to maintain the order of conversation
    chat_history = []
    last_author = None
    group_content = ""
    group_embeds = []
    for msg in reversed(history):
        author = "AI" if msg.author == client_user else "Human"
        clean_content = msg.content.replace(bot_mention, '').strip()
        embeds = [embed.to_dict() for embed in msg.embeds]

        print(f'{author}: {clean_content}')
        
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

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # If the bot isn't mentioned and it's not a DM, return
    if not isinstance(message.channel, discord.DMChannel)  \
       and client.user not in message.mentions:
        return

    bot_mention = client.user.mention

    clean_content = message.content.replace(bot_mention, '')

    new_thread = await make_new_thread(message, clean_content)

    chat_history = await make_chat_history(new_thread, bot_mention, client.user)

    try:
        VECTORNAME = select_vectorname(message, bot_mention)
    except ValueError as e:
        print(e)
        new_thread.send(f"""
Hi {message.author}
This Discord is not yet configured to use the bot. \
Need this info: 
- bot_id: {bot_mention}
- guild_id: Your-Guild-Name
""")
        return  # exit the event handler

    if message.attachments:

        max_file_size = 1 * 1024 * 1024  # 10 MB
        for attachment in message.attachments:
            if attachment.size > max_file_size:
                await thinking_message.edit("Sorry, a file is too large to upload via Discord, please use another method such as the bucket, or turn it into a .txt file. Uploaded files need to be smaller than 1MB each.")
                return

        # Send a thinking message
        thinking_message2 = await new_thread.send("Uploading file(s)..")

        # Forward the attachments to Flask app
        flask_app_url = f'{FLASKURL}/discord/{VECTORNAME}/files'
        print(f'Calling {flask_app_url}')
        payload = {
            'attachments': [{'url': attachment.url, 'filename': attachment.filename} for attachment in message.attachments],
            'content': clean_content,
            'chat_history': chat_history
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(flask_app_url, json=payload) as response:
                print(f'file response.status: {response.status}')
                if response.status == 200:
                    response_data = await response.json()
                    print(f'response_data: {response_data}')
                    summaries = response_data.get('summaries', [])
                    for summary in summaries:
                        await chunk_send(new_thread, summary)
                    await thinking_message2.edit(
                        content="Uploaded file(s). Use !deletesource {source_name} to remove it again")
                else:
                    # Edit the thinking message to show an error
                    await thinking_message2.edit(content="Error in processing file(s).")

        # we don't send to message endpoint as well
        return

    if message.content:
        print(f'Got the message: {message.content}')

        debug=False
        if message.content.startswith("!debug"):
            debug = True

        clean_content = message.content.replace(bot_mention, '').strip()

        if VECTORNAME == None:
            # debug mode for me
            print(f'DM from {message.author}')
            if str(message.author) == "MarkeD#2972":
                VECTORNAME="edmonbrain"
                debug=True
                words = shlex.split(str(message.content))
                print(words)
                if words[0] == "!vectorname":
                    VECTORNAME = words[1]
                    await chunk_send(message.channel, f"vectorname={VECTORNAME}")
                    clean_content = words[2]
                else:
                    await chunk_send(message.channel, 
                                     "Hello Master. Use !vectorname <vector_name> 'clean content' to debug")
            else:
                await chunk_send(message.channel,
                                 f"Don't DM me {str(message.author)}, please @me in a channel")
                return

        # Send a thinking message
        thinking_message = await new_thread.send("Thinking...")

        if len(clean_content) < 10 and not clean_content.startswith("!"):
            print(f"Got a little message not worth sending: {clean_content}")
            await thinking_message.edit(content=f"May I ask you to reply with a bit more context?")

            return

        # Forward the message content to your Flask app
        # stream for openai, batch for vertex
        if VECTORNAME.endswith("_vertex"):
            flask_app_url = f'{FLASKURL}/discord/{VECTORNAME}/message'
        else:
            flask_app_url = f'{STREAMURL}/qna/discord/streaming/{VECTORNAME}'
        print(f'Calling {flask_app_url}')
        payload = {
            'content': clean_content,
            'chat_history': chat_history
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(flask_app_url, json=payload) as response:
                print(f'chat response.status: {response.status}')
                if response.status != 200:
                    # Edit the thinking message to show an error
                    await thinking_message.edit(content="Error in processing message.")
                    return
                
                if response.headers.get('Transfer-Encoding') == 'chunked':
                    # This is a streamed response, process it in chunks
                    response_data = await process_streamed_response(response, new_thread)
                    source_docs = response_data.get('source_documents', [])
                    reply_content = ''  # Get the 'result' field from the JSON

                else:
                    response_data = await response.json()  # Get the response data as JSON
                    source_docs = response_data.get('source_documents', [])
                    reply_content = response_data.get('result')  # Get the 'result' field from the JSON

                print(f'response_data: {response_data}')
                # dedupe source docs
                seen = set()
                unique_source_docs = []

                for source in source_docs:
                    metadata_str = json.dumps(source.get('metadata'), sort_keys=True)
                    if metadata_str not in seen:
                        unique_source_docs.append(source)
                        seen.add(metadata_str)

                for source in unique_source_docs:
                    metadata_source = source.get('metadata')
                    source_message = f"**source**: {metadata_source.get('source')}"
                    if metadata_source.get('page_number', None) is not None:
                        source_message += f" page: {metadata_source.get('page_number')}"
                    if metadata_source.get('category', None) is not None:
                        source_message += f" category: {metadata_source.get('category')}"
                    if metadata_source.get('title', None) is not None:
                        source_message += f" title: {metadata_source.get('title')}"
                        
                    await chunk_send(new_thread, source_message)
                    source_url = metadata_source.get('url', None)
                    if source_url is not None:
                        url_message = f"**url**: {source_url}"
                        await chunk_send(new_thread, url_message)

                if len(reply_content) > 2000:
                    await thinking_message.edit(content="*Response:*")
                    await chunk_send(new_thread, reply_content)
                elif len(reply_content) == 0:
                    await thinking_message.edit(content="No response")
                else:
                    # Edit the thinking message to show the reply
                    await thinking_message.edit(content=reply_content)

                # Check if the message was sent in a thread or a private message
                if isinstance(new_thread, discord.Thread):
                    await new_thread.send(f"*Reply to {bot_mention} within this thread to continue. Use `!help` for special commands*")
                elif isinstance(new_thread, discord.DMChannel):
                    # Its a DM
                    await new_thread.send(f"*Use `!help` to see special commands*")
                else:
                    print(f"I couldn't work out the channel type: {new_thread}")

client.run(TOKEN)
