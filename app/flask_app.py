from flask import Flask, request, render_template,jsonify
from flask_cors import CORS
from functools import wraps
import os
from main import * 
app = Flask('Voting')
CORS(app)

def require_auth_key(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        auth_key = os.environ.get('API_KEY')
        provided_auth_key = request.headers.get('x-api-key')
        provided_community_board = request.headers.get('x-community-board')
        
        if provided_auth_key != auth_key:
            return jsonify({'message': 'Unauthorized'}), 401

        if provided_community_board is None:
            return jsonify({'message': 'No Community Board'}), 404

        return func(*args, provided_community_board=provided_community_board, **kwargs)

    return decorated_function


@app.route('/exportvotes', methods=['POST'])
@require_auth_key
def export_votes(provided_community_board):
    try:
        data = request.get_json()
        date = data.get('date')
        
        if not date:
            return jsonify({'error': 'Date is required'}), 400

        result = api_export_votes(date,provided_community_board)
        print(result)
        return result
        
    except Exception as e:
        print(f"Error in export_votes: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/incomingtext', methods=['POST'])
def incoming_text():
    provided_auth_key = request.args.get('auth')
    twilio_auth_key = os.environ.get('TWILIO_API_KEY')
    if provided_auth_key != twilio_auth_key:
        return jsonify({'message': 'Unauthorized'}), 401

    community_board = request.args.get('cb', '')
    incoming_msg = request.values['Body']
    incoming_number = request.values['From']
    return parse_incoming_text(incoming_number,incoming_msg,community_board)

@app.route('/results', methods=['GET'])
@require_auth_key
def results(provided_community_board):
    return api_get_results(provided_community_board)

@app.route('/', methods=['GET'])
def index():
   return render_template('./index.html')

@app.route('/manualentry', methods=['POST'])
@require_auth_key
def testing(provided_community_board):
    data = request.get_json()
    number_sms = data['number_sms']
    vote_to_send = data['vote_to_send']
    return api_testing(number_sms,vote_to_send,provided_community_board)
    
@app.route('/startvoting', methods=['POST'])
@require_auth_key
def startvoting(provided_community_board):
    try:
        if true_if_members_list_zero(provided_community_board):
            print('Member list is zero')
            response = {
                'error': 'Internal Server Error',
                'message': 'Member list is zero',
            }
            return jsonify(response), 500 
        data = request.get_json()
        title = data.get('title')
        vote_type = data.get('vote_type', 'RESOLUTION') # Default to RESOLUTION
        candidates = data.get('candidates') # Will be None if not provided

        if not title:
             return jsonify({'message': 'Title is required'}), 400

        if vote_type == "ELECTION" and not (candidates and isinstance(candidates, list) and len(candidates) > 0):
            return jsonify({'message': 'Candidates list must be provided for ELECTION vote type'}), 400

        # api_start_voting from main.py handles candidates being None if vote_type is RESOLUTION
        api_start_voting(title=title, community_board=provided_community_board, vote_type=vote_type, candidates=candidates)
        return jsonify({'message': f'Voting started for {title}'}), 200
    except Exception as e:
        print(e)
        response = {
            'error': 'Internal Server Error',
            'message': 'Couldnt start voting',
        }
        return jsonify(response), 500

@app.route('/stopvoting', methods=['POST'])
@require_auth_key
def stopvoting(provided_community_board):
    try:
        api_stop_voting(provided_community_board)
        return 'OK'  
    except Exception as e:
        response = {
            'error': 'Internal Server Error',
            'message': 'Couldnt stop voting',
        }
        return jsonify(response), 500
    
@app.route('/isvotingstarted', methods=['GET'])
@require_auth_key
def is_voting_started(provided_community_board):
    return json.dumps(api_is_voting_started(provided_community_board))

@app.route('/members', methods=['GET'])
@require_auth_key
def get_members(provided_community_board):
    return json.dumps(api_get_members(provided_community_board))

@app.route('/members', methods=['POST'])
@require_auth_key
def set_members(provided_community_board):
    try:
        data = request.get_json()
        return api_set_members(data,provided_community_board)
    except Exception as e:
        print(f"Error in set_members: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
