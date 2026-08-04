import json
from main import *
import base64
from urllib.parse import parse_qs

import os
import boto3

s3 = boto3.client('s3')
API_KEY = os.environ.get('API_KEY')
TWILIO_API_KEY = os.environ.get('TWILIO_API_KEY')

def json_response(body, status=200):
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(body),
    }

def lambda_handler(event, context):
    print(str(event))
    http_method = event['requestContext']['http']['method']
    path = event['rawPath']
    if path.startswith('/default/'):
        path = path[len('/default'):]

    if path in ('/', '/webresults'):
        return get_html_page()

    if path.startswith('/static/'):
        return get_static_file(path)

    if path == '/incomingtext' and 'auth=' + TWILIO_API_KEY in event['rawQueryString']:
        body = event['body']
        decoded_body = base64.b64decode(body).decode('utf-8')
        query_params = parse_qs(decoded_body)
        query_string_params = parse_qs(event['rawQueryString'])
        community_board = query_string_params.get('cb', [''])[0]
        incoming_msg = query_params.get('Body', [''])[0]
        incoming_number = query_params.get('From', [''])[0]
        return {
            'body': str(parse_incoming_text(incoming_number, incoming_msg, community_board)),
            'statusCode': 200,
            'headers': {'Content-Type': 'application/xml'},
        }

    if 'headers' in event and 'x-api-key' in event['headers'] and event['headers']['x-api-key'] == API_KEY:
        community_board = event['headers']['x-community-board']
        if http_method == 'POST':
            if path == '/startvoting':
                if true_if_members_list_zero(community_board):
                    return json_response({'error': 'Internal Server Error', 'message': 'Member list is zero'}, 500)
                body = event['body']
                data = json.loads(body)
                title = data.get('title', None)
                vote_type = data.get('vote_type', 'RESOLUTION')
                candidates = data.get('candidates', None)
                if vote_type == "ELECTION" and not candidates:
                    return json_response({'error': 'Bad Request', 'message': 'Candidates are required for ELECTION vote_type'}, 400)
                api_start_voting(title=title, community_board=community_board, vote_type=vote_type, candidates=candidates)
                return json_response('OK')
            elif path == '/exportvotes':
                body = json.loads(event['body'])
                date = body.get('date')
                return api_export_votes(date, community_board)
            elif path == '/manualentry':
                body = event['body']
                data = json.loads(body)
                number_sms = data['number_sms']
                vote_to_send = data['vote_to_send']
                return api_testing(number_sms, vote_to_send, community_board)
            elif path == '/stopvoting':
                api_stop_voting(community_board)
                return json_response('OK')
            elif path == '/members':
                body = json.loads(event['body']) if event.get('body') else {}
                return api_set_members(body, community_board)
        elif http_method == 'GET':
            if path == '/results':
                return api_get_results(community_board)
            elif path == '/isvotingstarted':
                return json_response(api_is_voting_started(community_board))
            elif path == '/members':
                return json_response(api_get_members(community_board))
        else:
            return json_response('Method not allowed', 405)
    else:
        return json_response('Unauthorized', 401)


def get_html_page():
    html_file_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    with open(html_file_path, 'r') as html_file:
        html_content = html_file.read()
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/html'},
        'body': html_content,
    }

STATIC_CONTENT_TYPES = {
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.webp': 'image/webp',
}

# Extensions that are binary, not text - API Gateway/Lambda need these
# base64-encoded with isBase64Encoded set, or the bytes get corrupted trying
# to decode/re-encode them as UTF-8 text.
BINARY_STATIC_EXTENSIONS = {'.webp'}

def get_static_file(path):
    # path looks like '/static/style.css'; keep it confined to the static/ dir.
    relative_path = path[len('/static/'):]
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    file_path = os.path.normpath(os.path.join(static_dir, relative_path))
    if not file_path.startswith(static_dir + os.sep) or not os.path.isfile(file_path):
        return json_response('Not found', 404)

    _, ext = os.path.splitext(file_path)
    content_type = STATIC_CONTENT_TYPES.get(ext, 'application/octet-stream')

    if ext in BINARY_STATIC_EXTENSIONS:
        with open(file_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode('ascii')
        return {
            'statusCode': 200,
            'headers': {'Content-Type': content_type},
            'body': content,
            'isBase64Encoded': True,
        }

    with open(file_path, 'r') as f:
        content = f.read()
    return {
        'statusCode': 200,
        'headers': {'Content-Type': content_type},
        'body': content,
    }
