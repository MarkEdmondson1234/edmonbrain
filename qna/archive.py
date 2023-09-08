from qna.pubsub_manager import PubSubManager

import datetime

def archive_qa(bot_output, vector_name):
    pubsub_manager = PubSubManager(vector_name, pubsub_topic=f"qna_archive_{vector_name}")
    the_data = {"bot_output": bot_output,
                "vector_name": vector_name,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    
    pubsub_manager.publish_message(the_data)