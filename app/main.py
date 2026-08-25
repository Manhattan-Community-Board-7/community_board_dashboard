import json
import csv
import random
from PersisterClass import PersisterS3,PersisterGlobalVariables
from VoterClass import Voter
from VoteClass import Vote
from VoteOptionsEnum import VoteOptions
from twilio.twiml.messaging_response import MessagingResponse
from VoteLoggingClass import LocalVoteLoggingClass, S3VoteLoggingClass
import shelly_door
import door_log

INSTRUCTIONS_MESSAGE = ' Welcome to Community Board text message voting. text yes to vote yes, no to vote no, abstain to vote abstain, cause to vote cause. '
INVALID_INPUT_MESSAGE = 'Your vote was NOT RECORDED, your message was invalid. The only valid inputs are yes, no, abstain, cause with no caps'
NOT_VOTING_MESSAGE = 'Not currently open for voting'
NOT_VALID_NUMBER_MESSAGE = 'We dont have a record of your number, tell the board office your name and this number'


# S3 Persister
persister = PersisterS3()
#persister.load_members(community_board='7') # ONly run the first time

# Local Persister
#persister= PersisterGlobalVariables()
#persister.load_members(community_board='7') 


# Local Vote Logger
#votelogger = LocalVoteLoggingClass()

# S3 Vote Logger
votelogger = S3VoteLoggingClass()

def get_vote_from_string(incoming_message, community_board):
    vote_type = persister.get_vote_type(community_board)

    if vote_type == "ELECTION":
        candidates = persister.get_election_candidates(community_board)
        for candidate in candidates:
            if incoming_message.lower() == candidate.lower():
                return candidate # Return the original casing of the candidate name
        return None # No matching candidate found
    else: # RESOLUTION or default
        # Keep the existing logic for yes/no/abstain/cause
        incoming_message_lower = incoming_message.lower()
        if 'cause' in incoming_message_lower:
            return VoteOptions.CAUSE
        elif 'abstain' in incoming_message_lower:
            return VoteOptions.ABSTAIN
        elif 'yes' in incoming_message_lower:
            return VoteOptions.YES
        elif 'no' in incoming_message_lower:
            return VoteOptions.NO
        else:
            return None

def summarize_votes(community_board):
    vote_type = persister.get_vote_type(community_board)

    if vote_type == "ELECTION":
        candidates = persister.get_election_candidates(community_board)
        vote_summary = {candidate: [] for candidate in candidates}
        # Optionally, add an 'Other' category for unexpected votes, though get_vote_from_string should prevent this.
        # vote_summary['Other'] = []
    else: # RESOLUTION or default
        vote_summary = {
           VoteOptions.YES:[],
           VoteOptions.NO:[],
           VoteOptions.ABSTAIN:[],
           VoteOptions.CAUSE:[]
        }

    vote_log = persister.get_vote_log(community_board)
    for voter_number in vote_log:
        vote_cast = vote_log[voter_number].voters_vote
        # Ensure the vote_cast key exists in vote_summary, especially if not using an 'Other' category for elections.
        if vote_cast in vote_summary:
            vote_summary[vote_cast].append(vote_log[voter_number].toJSON())
        else:
            # Handle unexpected votes if necessary, e.g., log a warning or add to an 'Other' category
            # For now, we'll assume get_vote_from_string prevents this for elections.
            # If it's a RESOLUTION vote and vote_cast is somehow not in the enum, this is an issue.
            print(f"Warning: Unexpected vote '{vote_cast}' by {voter_number} for vote type {vote_type}")


    return vote_summary

def get_summary(community_board):
    vote_summary = summarize_votes(community_board)
    vote_type = persister.get_vote_type(community_board)
    pre_amble = '------------------ \nVote Summary for '+persister.get_current_vote_name(community_board) + '\n'

    results = 'Voting Summary:\n'
    log = '----Raw Log ----- \n'

    if vote_type == "ELECTION":
        candidates = persister.get_election_candidates(community_board)
        for candidate in candidates:
            results += f"{len(vote_summary.get(candidate, []))} votes for {candidate}\n"
        # Optional: Add 'Other' to summary if used
        # if 'Other' in vote_summary and len(vote_summary['Other']) > 0:
        #     results += f"{len(vote_summary['Other'])} other votes\n"

        for candidate_name in candidates:
            if candidate_name in vote_summary: # Check if candidate received votes
                for voted_option_results in vote_summary[candidate_name]:
                    log += f"{voted_option_results['voter']} voted for {candidate_name}\n"
        # Optional: Log 'Other' votes
        # if 'Other' in vote_summary:
        #     for voted_option_results in vote_summary['Other']:
        #         log += f"{voted_option_results['voter']} cast an un tallied vote\n"

    else: # RESOLUTION or default
        results += (str(len(vote_summary.get(VoteOptions.YES,[])))+' yes votes \n' +
                    str(len(vote_summary.get(VoteOptions.NO,[])))+' no votes \n' +
                    str(len(vote_summary.get(VoteOptions.ABSTAIN,[])))+' abstain votes \n' +
                    str(len(vote_summary.get(VoteOptions.CAUSE,[])))+' abstaining for cause votes \n')
        for voted_option in VoteOptions:
            if voted_option in vote_summary: # Check if this option received votes
                for voted_option_results in vote_summary[voted_option]:
                    log += voted_option_results['voter']+" voted "+ voted_option.value +' \n'

    return pre_amble+results+log

def check_if_instructions(incoming_msg):
    if 'instructions' in incoming_msg or 'Instructions' in incoming_msg:
        return True

def create_response_msg(text_to_send):
    r = MessagingResponse()
    r.message(text_to_send)
    return str(r)

def extract_name_and_vote(text):
    parts = text.split('-')
    if len(parts) == 2:
        name, vote = parts
        return name, vote
    else:
        return None, None
    
def search_for_number_for_name(name_to_query,community_board):
    members = persister.get_members()
    for voter in members.items():
        if name_to_query.lower_case() in voter[1].name.lower_case():
            return voter[0]
    return None

def parse_incoming_text(incoming_number,incoming_msg,community_board):
    votelogger.log_raw_vote_to_file(incoming_number,incoming_msg,persister.get_current_vote_name(community_board),community_board)

    members = persister.get_members(community_board)
    if incoming_number not in members.keys():
        return create_response_msg(NOT_VALID_NUMBER_MESSAGE+' '+incoming_number)

    voting_member:Voter = members[incoming_number] or None

    if shelly_door.is_door_command(incoming_msg):
        if shelly_door.trigger_door():
            return create_response_msg(shelly_door.DOOR_TRIGGERED_MESSAGE)
        else:
            return create_response_msg(shelly_door.DOOR_ERROR_MESSAGE)

    if not persister.get_currently_in_a_voting_session(community_board):
        return create_response_msg(NOT_VOTING_MESSAGE)
    if check_if_instructions(incoming_msg):
        return create_response_msg(INSTRUCTIONS_MESSAGE)
    vote_cast = get_vote_from_string(incoming_msg, community_board) # pass community_board
    if vote_cast == None:
        current_vote_type = persister.get_vote_type(community_board)
        if current_vote_type == "ELECTION":
            candidates = persister.get_election_candidates(community_board)
            candidate_names = ", ".join(candidates) if candidates else "No candidates listed"
            election_error_message = (
                f"Your vote was NOT RECORDED, your message was invalid. "
                f"For this election, you must enter one of the candidate names. "
                f"The available candidates are: {candidate_names}."
            )
            return create_response_msg(election_error_message)
        else:
            return create_response_msg(INVALID_INPUT_MESSAGE)
    

    persister.add_to_vote_log(key=voting_member.sms_number,value=Vote(voting_member,vote_cast),community_board=community_board)

    r = MessagingResponse()
    vote_type = persister.get_vote_type(community_board)
    if vote_type == "ELECTION":
        # For elections, vote_cast is a string (candidate name)
        r.message(f'Your vote has been recorded, you voted for {str(vote_cast)} for election {persister.get_current_vote_name(community_board)}')
    else:
        # For resolutions, vote_cast is a VoteOptions enum
        r.message(f'Your vote has been recorded, you voted {vote_cast.value} for resolution {persister.get_current_vote_name(community_board)}')
    return str(r)

def true_if_members_list_zero(community_board):
    members = persister.get_members(community_board)
    return len(members) == 0

#### API SECTION ###

def api_get_door_log(community_board):
    entries = door_log.get_door_log(community_board)
    members = persister.get_members(community_board)
    result = []
    for entry in entries:
        voter = members.get(entry['from'])
        result.append({
            'name': voter.name if voter else 'Unknown',
            'timestamp': entry['timestamp'],
        })
    return result

def api_get_results(community_board):
    from enum import Enum
    custom_encoder = lambda obj: obj.value if isinstance(obj, Enum) else obj #TODO , shouldnt this be apart of the class
    summary = summarize_votes(community_board)
    converted_summary = {custom_encoder(key): value for key, value in summary.items()}

    # Get all members and vote log
    all_members_dict = persister.get_members(community_board)
    vote_log_dict = persister.get_vote_log(community_board)
    
    # Determine who hasn't voted
    voted_sms_numbers = set(vote_log_dict.keys())
    not_voted_names = []
    if all_members_dict: # Check if all_members_dict is not None and not empty
        for sms_number, voter_object in all_members_dict.items():
            if sms_number not in voted_sms_numbers:
                not_voted_names.append(voter_object.name)
            
    converted_summary["not_voted"] = not_voted_names

    response = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(converted_summary)
    }
    return response


def api_testing(number_sms,vote_to_send,community_board):
    return parse_incoming_text(number_sms, vote_to_send,community_board)

def api_start_voting(title, community_board, vote_type="RESOLUTION", candidates=None):
    persister.set_current_vote_name(title,community_board)
    persister.set_vote_type(vote_type, community_board)
    if vote_type == "ELECTION" and candidates:
        persister.set_election_candidates(candidates, community_board)
    elif vote_type == "RESOLUTION":
        persister.set_election_candidates([], community_board)
    persister.set_currently_in_a_voting_session(True,community_board)

def api_stop_voting(community_board):
    votelogger.log_vote_summary_to_file(current_vote_name=persister.get_current_vote_name(community_board),summary=get_summary(community_board),community_board=community_board)
    persister.set_current_vote_name('',community_board)
    persister.set_currently_in_a_voting_session(False,community_board)
    persister.clear_vote_log(community_board)
    # Reset vote type and clear candidates
    persister.set_vote_type("RESOLUTION", community_board)
    persister.set_election_candidates([], community_board)

def api_is_voting_started(community_board):
    vote_type = persister.get_vote_type(community_board)
    candidates = persister.get_election_candidates(community_board)
    response_body = {
        "isVotingStarted": persister.get_currently_in_a_voting_session(community_board),
        "currentVoteName": persister.get_current_vote_name(community_board),
        "voteType": vote_type,
        "electionCandidates": candidates if vote_type == "ELECTION" else []
    }
    response = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*" # Added for consistency with other API endpoints
        },
        "body": json.dumps(response_body) # Ensure body is json string
    }
    return response

def api_export_votes(date, community_board):
    try:
        # Convert YYYY-MM-DD to YYYY_MM_DD format for file name prefix
        formatted_date = date.replace('-', '_')
        prefix = f'summaryvotelog/{community_board}/{formatted_date}'
        
        try:
            # List all keys starting with the given prefix.
            # Note: Adjust this to the appropriate method for your persister.
            keys = persister.list_objects(prefix=prefix)
            
            if not keys:
                return {
                    "statusCode": 404,
                    "headers": {
                        "Content-Type": "application/json",
                    },
                    "body": {'error': f'No vote summary found for {date}'}
                }
            
            aggregated_content = ""
            # Loop through each file key, get its content, and concatenate it.
            for key in keys:
                file_content = persister.get_object(key=key)
                aggregated_content += file_content + "\n"
            
            # Optionally, you could trim the trailing newline here.
            aggregated_content = aggregated_content.strip()
            print(aggregated_content)
            return aggregated_content
        
        except Exception as inner_exception:
            print(f"Error fetching files: {str(inner_exception)}")
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {'error': f'No vote summary found for {date}'}
            }
            
    except Exception as e:
        print(f"Error in api_export_votes: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
            },
            "body": {'error': 'Internal server error'}
        }

def api_get_members(community_board):
    members = persister.get_members(community_board)
    # Convert the members dictionary to a serializable format
    serialized_members = {}
    for number, voter in members.items():
        serialized_members[number] = {
            "name": voter.name,
            "sms_number": voter.sms_number
        }
    
    response = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(serialized_members)
    }
    return response

def api_set_members(members_data,community_board):
    try:
        # Convert the incoming JSON data back to Voter objects
        new_members = {}
        for number, member_info in members_data.items():
            new_members[number] = Voter(
                name=member_info['name'],
                sms_number=number
            )
        
        # Update the members in the persister
        persister.set_members(new_members,community_board)
        
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"message": "Members updated successfully"})
        }
    except Exception as e:
        response = {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }
    
    return response

