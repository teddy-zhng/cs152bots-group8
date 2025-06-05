from google import genai
import re
import os
import time
from openai import OpenAI

# Load API key from a text file
try:
    with open("api_key.txt", "r") as f:
        api_key = f.read().strip()
    os.environ['OPENAI_API_KEY'] = api_key
except FileNotFoundError:
    print("Error: API key file not found. Create 'api_key.txt' with your API key.")
    exit(1)
except Exception as e:
    print(f"Error loading API key: {e}")
    exit(1)

client = OpenAI()

def call_gpt(sys_instruction, content, retries=3, wait_time=60):
    attempt = 0
    while attempt < retries:
        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": sys_instruction},
                    {"role": "user", "content": content}
                ]
            )
            return completion.choices[0].message.content
        except Exception as e:
            attempt += 1
            print(f"Error occurred: {e}. Attempt {attempt} of {retries}. Waiting for {wait_time} seconds before retrying.")
            time.sleep(wait_time)
            if attempt == retries:
                print("Max retries reached. Skipping this request.")
                return None

#  Function to invoke report generation
def LLM_report(report_details):
    """
    Populate report info as if from a user's perspective, and also make a recommendation for moderator.

    Parameters
    ----------
    report_details : dict
        A dictionary containing classification inputs. Expected keys:

        # Provided by the caller:
        - "message_content" (str): The flagged message.
        - "classifier_label" (str): "Misinformation".
        - "confidence_score" (float): Classifier confidence score.

        # Initialized as empty by the caller (will be filled by this function):
        - "report_type" (str or None): "Misinformation" or "other", based on LLM analysis.
        - "misinfo_type" (str or None): e.g., "Political Misinformation", "Health Misinformation".
        - "misinfo_subtype" (str or None): A subtype depending on misinfo_type.
        - "imminent" (str or None): Type of imminent harm, if any (e.g., "physical", "mental").
        - "LLM_recommendation" (str or None): Recommended action (e.g., "Remove Content").

    Returns
    -------
    dict
        The updated report_details dictionary with all fields filled by the LLM logic.
    """

    # outline fields for report_details
    report_details['report_type'] = None
    report_details['misinfo_type'] = None
    report_details['misinfo_subtype'] = None
    report_details['imminent'] = None
    # we don't need to do filter since that is only for users who want to block the author
    report_details['LLM_recommendation'] = None

    # Call to classify type of misinformation
    misinfo_type_response = call_misinfo_type(report_details)
    misinfo_type_response = misinfo_type_response[0]

        #================== Decision logic for Misinformation Type Response ==================
    
    # Political Misinfo
    if misinfo_type_response ==  "1" :
        report_details ['misinfo_type'] = "Political Misinformation"

        # Call to classify political misinfo subtype
        pol_misinfo_subtype_response  =  call_pol_misinfo_subtype(report_details)
        pol_misinfo_subtype_response = pol_misinfo_subtype_response[0]

        #=============== Decision logic for Political misinfo subtye response ===============
        if pol_misinfo_subtype_response == "1":
            report_details['misinfo_subtype'] = 'Election/Campaign Misinformation'
        
        elif pol_misinfo_subtype_response == "2":
            report_details['misinfo_subtype'] = 'Government/Civic Services'
        
        elif pol_misinfo_subtype_response == "3":
            report_details['misinfo_subtype'] = 'Manipulated Photos/Video'

        elif pol_misinfo_subtype_response == "4":
            report_details['misinfo_subtype'] = 'Other'
    
    # Health Misinfo
    elif misinfo_type_response == "2" :
        report_details ['misinfo_type'] = "Health Misinformation"

            # Call to classify health misinfo subtype
        health_misinfo_subtype_response = call_health_misinfo_subtype(report_details)
        health_misinfo_subtype_response = health_misinfo_subtype_response[0]

        #=============== Decision logic for Health misinfo subtye response ===============
        if health_misinfo_subtype_response == "1":
            report_details['misinfo_subtype'] = 'Vaccines'
        
        elif health_misinfo_subtype_response == "2":
            report_details['misinfo_subtype'] = 'Cures and Treatments'
            
        elif health_misinfo_subtype_response == "3":
            report_details['misinfo_subtype'] = 'Mental Health'

        elif health_misinfo_subtype_response == "4":
            report_details['misinfo_subtype'] = 'Oher'

    
    elif misinfo_type_response == "3" :
        report_details ['misinfo_type'] = "Other Misinformation"
        report_details['misinfo_subtype'] = 'Other'


        # Initiate userflow for Harmful content
        imminent_response = call_imminent(report_details)
        imminent_response = imminent_response[0]

        #================== Decision logic for Imminent Harm Response ==================

        if imminent_response == "2":
            report_details['imminent'] = 'physical'

        elif imminent_response == "3":
            report_details['imminent'] = 'mental'
        
        elif imminent_response == "4":
            report_details['imminent'] = 'financial or property'

        """
        Discussion : Not sure if to factor in the filter flag since this is detected automatically and  
        not specific to a particular user's feed
        """
        
        # Initiate userflow for LLM Recommendation 
        recommendation_response = call_recommedation(report_details)
        report_details['LLM_recommendation'] = recommendation_response

    # TODO: exception for when LLM returns invalid format or empty response!

    return report_details


# this function does not allow the LLM to reject the classification, since at this point we are just emulating a user report.
# later the LLM is given a chance to suggest to the moderator that the content is not harmful
def call_report_type(report_details):
    # Step 1: Initial classification - Misinformation or Other
    print("====Step 1: Initial classification - Misinformation or Other===")
    print(f"Message: {report_details['message_content']}")

    system_instruction = f"""
     You are a trust & safety expert content moderator for a social media platform who has been assigned to generate a user
     report for a post that has been flagged by the platform's classifier.
                         """

    content = f""" 

    Message Content : {report_details['message_content']},

    Initial Classification from the Automated Post Classifier:
    - Label : {report_details['classifier_label']},
    - Confidence : {report_details['confidence_score']},

    Validate the classifier's decision by selecting a category:
    1. Misinformation
    2. Other inappropriate or abusive content

    Respond with ONLY the number (1-2).
    """
    
    return call_gpt(system_instruction, content)


def call_misinfo_type (report_details):
    # Step 2: Type of Misinformation
    print("====Step 2: Misinformation type ===")
    
    system_instruction = f"""
    You are a misinformation trust & safety expert content moderator for a social media platform who has been assigned to analyze content reported
    as misinformation.
                        """
    
    content = f"""
     Message Content: {report_details['message_content']}
     Please select the type of misinformation:
        1. Political Misinformation
        2. Health Misinformation
        3. Other Misinformation
        
    Respond with ONLY the number (1-3).
                """
    
    return call_gpt(system_instruction, content)


def call_pol_misinfo_subtype(report_details):
    # Step 3a. Type of Political Misinformation
    print("====Step 3a. Type of Political Misinformation ===")

    system_instruction = f"""
    You are a political trust & safety expert content moderator for a social media platform who has been assigned to analyze content reported
    as political misinformation.
                         """
    
    content = f"""
    Message Content: {report_details['message_content']}
    Classify the type of political  misinformation which the message falls under :
        1. Election/Campaign Misinformation
        2. Government/Civic Services
        3. Manipulated Photos/Video
        4. Other political misinformation
    
    Respond with ONLY the number (1-4).
              """

    return call_gpt(system_instruction, content)


def call_health_misinfo_subtype(report_details):
    # Step 3b. Type of Health Misinformation
    print("====Step 3b. Type of Health Misinformation ===")

    system_instruction = f"""
    You are a health trust & safety expert content moderator for a social media platform who has been assigned to analyze content reported
    as health misinformation.
                         """
    
    content = f"""
    Message Content: {report_details}
    Classify the type of health  misinformation which the message falls under :
        1. Vaccines
        2. Cures and Treatments
        3. Mental Health
        4. Other health misinformation
            
    Respond with ONLY the number (1-4).
               """
    
    return call_gpt(system_instruction,content)


def call_imminent(report_details):
    # Step 4: Imminent Harm 
    print("====Step 4: Imminent Harm===")

    system_instruction = f"""
    You are a trust & safety expert content moderator for a social media platform who has been assigned to analyze content reported
    and assess potential harm of the reported content.
                         """
    
    content = f"""
    Message Content: {report_details['message_content']}
    Could this content likely cause imminent harm to people or public safety?
        1. No
        2. Yes, physical harm
        3. Yes, mental harm
        4. Yes, financial or property harm
        
    Respond with ONLY the number (1-4).
              """
    
    return call_gpt(system_instruction, content)


# this function is from the moderator POV, where the LLM now sees the whole report and recommends an action
def call_recommedation(report_details):
    # Step 5: Recommendation
    print("====Step 5: Recommendation===")

    system_instruction = f"""
    You are a trust & safety expert content moderator for a social media platform. You have been assigned to assist a human moderator in making a decision
    about reported content. Here is the information you have about the report:
                         """
    # TODO put in policy language above!
    
    content = f"""
    Message Content: {report_details['message_content']}
    Classification : {report_details['classifier_label']}
    Confidence Score : {report_details['confidence_score']}
    Report Type: {report_details['report_type']}
    Misinformation Type: {report_details['misinfo_type']}
    Misinformation Subtype: {report_details['misinfo_subtype']}
    Imminent Harm: {report_details['imminent']}



    Based on the message content, potential harm label and confidence score, which of the following do you recommend :
        1. Allow Content, it is not harmful or inappropriate. It should be allowed to remain on the platform, and you (the LLM) believe that the classifier's decision is incorrect.
        2. Remove Content, it should not be allowed to remain on the platform
        3. Escalate to a human moderator

        Respond with ONLY one of these phrases: 'Allow Content', 'Remove Content', or 'Escalate to a human moderator' and in less than 80 words, 
        justify your recommendation. Adhere strictly to the word limit of 80. 
              """

    return call_gpt(system_instruction,content)
# Recommendation based on filter, imminent harm, 



