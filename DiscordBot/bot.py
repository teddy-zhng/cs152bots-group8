"""
This file contains the main Discord bot implementation for handling user reports and moderation.
"""
# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from enum import Enum
from report import Report, get_priority_static
from report_queue import SubmittedReport, PriorityReportQueue
import pdb
from moderate import ModeratorReview
from LLM import LLM_reports as llm

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']


MOD_TODO_START = "---------------------------\nTODO"
MODERATE_KEYWORD = "moderate"

NUM_QUEUE_LEVELS = 3

CLASSIFIER_URL = "https://discord-classifier-432480940956.us-central1.run.app/classify"
GCP_SERVICE_ACCOUNT_TOKEN_FILE = "gcp_key.json" # key that allows our discord bot to run the classifier
credentials = service_account.IDTokenCredentials.from_service_account_file(
    GCP_SERVICE_ACCOUNT_TOKEN_FILE,
    target_audience=CLASSIFIER_URL
)

class ConversationState(Enum):
    NOFLOW = 0
    REPORTING = 1
    MODERATING = 2
    

class ModBot(discord.Client):
    # INITIALIZATION STAGE
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.moderations = {}
        self.report_id_counter = 0
        # should equal the number of distinct priorities defined in Report.get_priority
        self.report_queue = PriorityReportQueue(NUM_QUEUE_LEVELS, ["Imminent physical/mental harm", "Imminent financial/property harm", "Non-imminent"])
        self.conversationState = 0

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel
    
    # ENTRY POINT: ROUTE MESSAGES TO APPROPRIATE HANDLER
    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    # ROUTING FOR DMS
    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            reply += "Use the `moderate` command to begin the moderation process.\n"
            await message.channel.send(reply)
            return
        
        if message.content.startswith(Report.START_KEYWORD) or self.conversationState == ConversationState.REPORTING:
            self.conversationState = ConversationState.REPORTING
            await self.handle_report(message)
        elif message.content.startswith(MODERATE_KEYWORD) or self.conversationState == ConversationState.MODERATING: 
            self.conversationState = ConversationState.MODERATING
            await self.handle_moderation(message)

    # DMs that were reports
    async def handle_report(self, message):

        author_id = message.author.id
        responses = []

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # If we are starting a report
        responses = await self.reports[author_id].handle_message(message)

        ## report.py updates state, and below, we route our response based on that state

        if self.reports[author_id].is_awaiting_message():
            for r in responses:
                await message.channel.send(r)

        if self.reports[author_id].is_awaiting_reason():
            for r in responses:
                await message.channel.send(r)

        if self.reports[author_id].is_awaiting_misinformation_type():
            for r in responses:
                await message.channel.send(r)

        if self.reports[author_id].is_awaiting_political_misinformation_type():
            for r in responses:
                await message.channel.send(r)
        
        if self.reports[author_id].is_awaiting_healthl_misinformation_type():
            for r in responses:
                await message.channel.send(r)

        if self.reports[author_id].is_awaiting_harmful_content_status():
            for r in responses:
                await message.channel.send(r)

        if self.reports[author_id].is_awaiting_filter_action():
            for r in responses:
                await message.channel.send(r)

        # for future reference
        # if self.reports[author_id].harm_identified():
        #     reply = responses[0]
        #     harm = responses[1]
        #     if harm:
        #         # TODO escalate (or simulate it)
        #         print("Escalating report")
        #     await message.channel.send(reply)

        # if self.reports[author_id].block_step():
        #     reply = responses[0]
        #     block = responses[1]
        #     if block:
        #         # TODO block user (or simulate it)
        #         print("Blocking user")
        #     await message.channel.send(reply)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].is_report_complete():

            for r in responses:
                await message.channel.send(r)

            if not self.reports[author_id].is_cancelled():

                reported_author = self.reports[author_id].get_reported_author()
                reported_content = self.reports[author_id].get_reported_content() 
                report_type = self.reports[author_id].get_report_type() 
                misinfo_type = self.reports[author_id].get_misinfo_type()
                misinfo_subtype = self.reports[author_id].get_misinfo_subtype()
                imminent = self.reports[author_id].get_imminent()
                priority = self.reports[author_id].get_priority()
                id = self.report_id_counter
                self.report_id_counter += 1
                reported_message = self.reports[author_id].get_reported_message()

                # Put the report in the mod channel
                message_guild_id = self.reports[author_id].get_message_guild_id()
                mod_channel = self.mod_channels[message_guild_id]
                # todo are we worried about code injection via author name or content? 
                report_info_msg = "Report ID: " + str(id) + "\n"
                report_info_msg += "User " + message.author.name + " reported user " + str(reported_author) + "'s message.\n"
                # report_info_msg += "Here is the message: \n```" + str(reported_content) + "\n```" 
                report_info_msg += "Category: " + str(report_type) + " > " + str(misinfo_type) + " > " + str(misinfo_subtype) + "\n"
                if imminent not in ["Non-imminent", "No", None]:
                    print (imminent)
                    report_info_msg += "URGENT: Imminent " + imminent + " harm reported."
                
                # put the report on the queue itself
                submitted_report = SubmittedReport(id, reported_message, reported_author, reported_content, report_type, misinfo_type, misinfo_subtype, imminent, message_guild_id, priority)
                self.report_queue.enqueue(submitted_report)

                await mod_channel.send(report_info_msg)

            # remove
            self.reports.pop(author_id)
            self.conversationState = ConversationState.NOFLOW
    
    # DMs that were moderation requests
    async def handle_moderation(self, message):

        author_id = message.author.id

        if author_id not in self.moderations and self.report_queue.is_empty():
            await message.channel.send("No pending reports.")
            self.conversationState = ConversationState.NOFLOW
            return
        
        if author_id not in self.moderations:
            try:
                next_report = self.report_queue.dequeue()
            except IndexError:
                await message.channel.send("No pending reports.")
                self.conversationState = ConversationState.NOFLOW
                return
            review = ModeratorReview()
            review.original_report = next_report
            review.original_priority = next_report.priority
            review.report_type = next_report.report_type
            review.misinfo_type = next_report.misinfo_type
            review.misinfo_subtype = next_report.subtype
            review.imminent = next_report.imminent
            review.reported_author_metadata = f"User: {next_report.author}"
            review.reported_content_metadata = f"Msg: \"{next_report.content}\""
            review.message_guild_id = next_report.message_guild_id
            review.reported_message = next_report.reported_message
            if next_report.llm_recommendation:
                review.llm_recommendation = next_report.llm_recommendation
            else:
                report_details = {
                    'message_content': next_report.content,
                    'report_type': next_report.report_type,
                    'misinfo_type': next_report.misinfo_type,
                    'misinfo_subtype': next_report.subtype,
                    'imminent': next_report.imminent,
                }
                review.llm_recommendation = llm.call_recommendation_separate(report_details)
            self.moderations[author_id] = review
            preview = self.report_queue.display_one(next_report, showContent=False)
            if preview:
                await message.channel.send(f"```{preview}```")

        review = self.moderations[author_id]

        responses = await review.handle_message(message)
        for r in responses:
            await message.channel.send(r)

        if review.is_review_complete():

            if self.moderations[author_id].action_taken in ["Allowed", "Removed"]:
                # Put the verdict in the mod channel
                mod_channel = self.mod_channels[self.moderations[author_id].message_guild_id]
                # todo are we worried about code injection via author name or content? 
                mod_info_msg = "Report ID: " + str(id) + "\n"
                mod_info_msg += "has been moderated.\n"
                mod_info_msg += "Verdict: " + self.moderations[author_id].action_taken + ".\n"
                await mod_channel.send(mod_info_msg)
                if self.moderations[author_id].action_taken == "Removed":
                    await review.reported_message.add_reaction("❌")

            elif self.moderations[author_id].action_taken in ["Skipped", "Escalated"]:
                original_report = self.moderations[author_id].original_report
                self.report_queue.enqueue(original_report)

                
            self.moderations.pop(author_id, None)
            self.conversationState = ConversationState.NOFLOW

    # ROUTING FOR CHANNEL MESSAGES
    async def handle_channel_message(self, message):
        if not message.channel.name in [f'group-{self.group_num}', f'group-{self.group_num}-mod']:
            return

        # moderator commands
        if message.channel.name == f'group-{self.group_num}-mod':
            await self.handle_mod_tools(message)

        else:
            await self.auto_review(message) # classifies and then sends to llm for mod
    
    # mod channel messages: tools for moderators 
    async def handle_mod_tools(self, message):
        if message.content == "report summary":
            await message.channel.send(self.report_queue.summary())
        elif message.content.startswith("report display"):
            if "showcontent" in message.content:
                await message.channel.send(self.report_queue.display(showContent=True))
            else:
                await message.channel.send(self.report_queue.display())
        return

    # user channel messages: auto-review / flagging process
    async def auto_review(self, message):
        # ----- teddy: for milestone 3, we send every msg to classifier/llm -----------------------
        mod_channel = self.mod_channels[message.guild.id]
        classification, confidence = await self.classify_msg(message, mod_channel)
        if classification == -1 or confidence == -1:
            return # nothing happens on error
        
        print("message classified")
        
        # classified, now proceed with LLM filling out the report info
        if classification == "Misinformation":
            print("message classified as misinformation, sending to LLM")
            report_details = {
                'message_content': message.content,
                'classifier_label': classification,
                'confidence_score': confidence,

                # other fieds to be filled out by the LLM:
                # 'report_type' : str,
                # 'misinfo_type' : str,
                # 'misinfo_subtype': str,
                # 'imminent' : str,
                # 'LLM_recommendation' : str
            }
            report_details = llm.LLM_report(report_details) # report function is in LLM/ module
            print("report details: ", report_details)

            # make a report
            id = self.report_id_counter
            self.report_id_counter += 1
            reported_message = message
            reported_author = message.author.id 
            reported_content = message.content
            report_type = "Misinformation"
            misinfo_type = report_details['misinfo_type']
            misinfo_subtype = report_details['misinfo_subtype']
            imminent = report_details['imminent']
            message_guild_id = message.guild.id
            priority = get_priority_static(imminent)
            llm_recommendation = report_details['LLM_recommendation']
            
            # put it in the mod channel
            mod_channel = self.mod_channels[message_guild_id]
            # todo are we worried about code injection via author name or content? 
            report_info_msg = "Report ID: " + str(id) + "\n"
            report_info_msg += "[Auto-Mod] reported user " + str(reported_author) + "'s message.\n"
            # report_info_msg += "Here is the message: \n```" + str(reported_content) + "\n```" 
            report_info_msg += "Category: " + str(report_type) + " > " + str(misinfo_type) + " > " + str(misinfo_subtype) + "\n"
            if imminent not in ["Non-imminent", "No", None]:
                print(imminent)
                report_info_msg += "URGENT: Imminent " + imminent + " harm reported."
            
            # put the report on the queue itself
            submitted_report = SubmittedReport(id, reported_message, reported_author, reported_content, report_type, misinfo_type, misinfo_subtype, imminent, message_guild_id, priority, llm_recommendation)
            self.report_queue.enqueue(submitted_report)

            await mod_channel.send(report_info_msg)
            print("LLM done, Report created and sent to mod channel")
        
        else: 
            print("message classified as not misinformation, no action taken")

    # classifier step of auto-review
    async def classify_msg(self, message, mod_channel):
        credentials.refresh(Request())
        token = credentials.token
        headers = {
            "Authorization": f"Bearer {token}"
        }
        payload = {"message": message.content}
        try:
            response = requests.post(CLASSIFIER_URL, headers=headers, json=payload)
            result = response.json()

            classification = result.get("classification")
            confidence = result.get("confidence_score")

            # lets not spam the mod channel, this can be included in the report itself later if we want to add that
            # await mod_channel.send(
            #     f"Classification: {classification}, Confidence: {confidence:.2f} for message:\n```\n" + message.content + "\n```\nposted by user " + str(message.author)
            # )
            return classification, confidence

        except Exception as e:
            await mod_channel.send("Error classifying message: " + message.content)
            print(e)
            return -1, -1

    # LLM step of auto-review is an external function so we dont' have  afunction for it here


client = ModBot()
client.run(discord_token)
