import os
from interactions import Client, Intents, listen
from interactions import slash_command, SlashContext
from interactions import OptionType, slash_option
import discord
import aiohttp
import asyncio
import json
from dotenv import load_dotenv
import shlex
import discord_helpers as dh

# Initializing the client without a command prefix
client = Client(intents=Intents.DEFAULT)

load_dotenv()
# In-memory storage for vectornames
vectornames = {}

TOKEN = os.getenv('DISCORD_TOKEN', None)  # Get your bot token from the .env file
FLASKURL = os.getenv('FLASK_URL', None)

# Load the config file at the start of your program
config = dh.load_config('config.json')

if TOKEN is None or FLASKURL is None:
    raise ValueError("Must set env vars DISCORD_TOKEN, FLASK_URL in .env")

@slash_command(name="set_vectorname", description="Set a vectorname for this bot/user")
@slash_option(
    name="vectorname",
    description="Vectorname to set",
    required=True,
    opt_type=OptionType.STRING
)
async def set_vectorname(ctx: SlashContext, vectorname: str):

    vectornames[ctx.author.id] = vectorname
    await ctx.send(f"Vectorname set to: {vectorname}")

@slash_command(name="see_vectorname", description="See your current vectorname")
async def see_vectorname(ctx: SlashContext):
    if ctx.author.id in vectornames:
        await ctx.send(f"Your current vectorname is: {vectornames[ctx.author.id]}")
    else:
        await ctx.send("You have not set a vectorname yet.")

@listen()
async def on_ready():
    print(f'{client.user} has connected to Discord!')

@listen()
async def on_message_create(message):

    print("Got message: {}".format(message))

    if message.author == client.user:
        return

    # If the bot isn't mentioned and it's not a DM, return
    if not isinstance(message.channel, discord.DMChannel)  \
       and client.user not in message.mentions:
        return

    print(f"## Processing message by {message.author} read by {client.user} mentioning {message.mentions} ##")
    bot_mention = client.user.mention

    clean_content = message.content.replace(bot_mention, '')

    try:
        VECTORNAME = dh.select_vectorname(message, bot_mention, vectornames, config)
    except ValueError as e:
        print(e)
        new_thread.send(f"""
Hi {message.author}
This Discord is not yet configured to use the bot. \
Need this info: 
- {message.mentions}
""")
        return  # exit the event handler
    
    # set bot and agent flags
    talking_to_bot = False    
    if message.mentions[0].bot == True and message.author.bot == True:
        print("Bot talking to another bot")
        talking_to_bot = True
    
    agent = dh.load_config_key(["_bot_config", VECTORNAME, "agent"])

    
    if agent and talking_to_bot:
        import re
        # Extract question from the message using regex
        pattern = r"€€Question€€\s*(.*?)\s*€€End Question€€"
        match = re.search(pattern, message.content, re.DOTALL)

        # Only respond if the message matches the correct format
        if match:
            clean_content = match.group(1).strip()

            # Now you can proceed with the code to handle the question or send a response back
            # For demonstration, let's just print the question
            print(f"#Agent: Received question: {clean_content}")
            # ... handle the question or send response back ...
        else:
            print("#Agent: Received message not in correct format. Ignoring.")
            return

    new_thread = await dh.make_new_thread(message, clean_content)
    
    chat_history = await dh.make_chat_history(new_thread, bot_mention, client.user)

    # a file is attached
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
                        await dh.chunk_send(new_thread, summary)
                    await thinking_message2.edit(
                        content="Uploaded file(s). Use !deletesource {source_name} to remove it again")
                else:
                    # Edit the thinking message to show an error
                    await thinking_message2.edit(content="Error in processing file(s).")

        # we don't send to message endpoint as well
        return

    if message.content:
        print(f'Got the message: {message.content} from {message.author}')

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
                    await dh.chunk_send(message.channel, f"vectorname={VECTORNAME}")
                    clean_content = words[2]
                else:
                    await dh.chunk_send(message.channel, 
                                     "Hello Master. Use !vectorname <vector_name> 'clean content' to debug")
            else:
                await dh.chunk_send(message.channel,
                                 f"Don't DM me {str(message.author)}, please @me in a channel")
                return

        # Send a thinking message
        if not agent:
            thinking_message = await new_thread.send("Thinking...")

            if len(clean_content) < 10 and not clean_content.startswith("!"):
                print(f"Got a little message not worth sending: {clean_content}")
                await thinking_message.edit(content=f"May I ask you to reply with a bit more context, {str(message.author)}?")

                return
        else:
            print("Agent detected, no thinking message")

        # Forward the message content to your Flask app
        # stream for openai, batch for vertex
        streamer = dh.load_config_key(["_bot_config", VECTORNAME, "stream"])
        
        flask_app_url = f'{FLASKURL}/discord/{VECTORNAME}/message'
        if streamer:
            flask_app_url = f'{FLASKURL}/discord/{VECTORNAME}/stream'
            
        #pythprint(f'Calling {flask_app_url}')
        payload = {
            'user_input': clean_content,
            'chat_history': chat_history,
            'message_author': f"<@{message.author.id}>"
        }

        #print(f'Sending: {payload}')
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(flask_app_url, json=payload) as response:
                    print(f'chat response.status: {response.status}')
                    streamed=False

                    if response.status != 200:
                        # Edit the thinking message to show an error
                        if not agent:
                            await thinking_message.edit(content="Error in processing message.")
                        else:
                            new_thread.send("Error in processing message.")
                        return
                    
                    
                    if response.headers.get('Transfer-Encoding') == 'chunked':
                        # This is a streamed response, process it in chunks
                        async with new_thread.typing():
                            response_data = await dh.process_streamed_response(response, new_thread, thinking_message)
                            streamed=True
                            print("Finished streaming response")
                            print(response_data)
                    else:
                        async with new_thread.typing():
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
                            
                        await dh.chunk_send(new_thread, source_message)
                        source_url = metadata_source.get('url', None)
                        if source_url is not None:
                            url_message = f"**url**: {source_url}"
                            await dh.chunk_send(new_thread, url_message)
                                
                    if agent and talking_to_bot:
                        print(f"Agent sending directly: agent:{agent} talking_to_bot:{talking_to_bot}")
                        await dh.chunk_send(new_thread, reply_content)
                    else:
                        print("Not an agent")
                        #if streamed and thinking_message.content.startswith("Thinking..."):
                        #    print(str(thinking_message.content))
                        #    print(thinking_message)
                        #    print("Something went wrong with streaming, resorting to batch")
                        #    #streamed = False

                        # talking to a human
                        if not streamed:
                            print("Not streamed content")
                            if len(reply_content) > 2000:
                                await thinking_message.edit(content="*Response:*")
                                await dh.chunk_send(new_thread, reply_content)
                            elif len(reply_content) == 0:
                                await thinking_message.edit(content="No response")
                            else:
                                # Edit the thinking message to show the reply
                                await thinking_message.edit(content=reply_content)

                    # Check if the message was sent in a thread or a private message
                    if isinstance(new_thread, discord.Thread) and not agent:
                        await new_thread.send(f"*Reply to {bot_mention} within this thread to continue. Use `!help` for special commands*")
                    elif isinstance(new_thread, discord.DMChannel) and not agent:
                        # Its a DM
                        await new_thread.send(f"*Use `!help` to see special commands*")
                    else:
                        print(f"I couldn't work out the channel type: {new_thread}")
        except asyncio.TimeoutError:
            # Handle the timeout error by sending an error message to the user
            if not agent:
                await thinking_message.edit(content="The request timed out. Please try again later.")
            else:
                new_thread.send("The request timed out. Please try again later.")
            return


client.start(TOKEN)
