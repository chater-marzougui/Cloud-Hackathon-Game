from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
import time
from game_state import GameState

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cloud_clash_secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Load questions from JSON file
with open('data/questions.json', 'r') as f:
    questions = json.load(f)

# Initialize game state
game_state = GameState(questions)

# Valid player IDs (excluding INDP2C players as requested)
VALID_PLAYERS = [
    'INDP2A1', 'INDP2A2', 
    'INDP2B1', 'INDP2B2',
    # 'INDP2C1', 'INDP2C2',
    'INDP2D1', 'INDP2D2',
    'INDP2E1', 'INDP2E2',
    'INDP2F1', 'INDP2F2',
    'MmeASMA', 'MmeABIR',
]

# Admin configuration
ADMIN_KEY = "cloud_clash_secret!"

@app.route('/')
def index():
    return render_template('lobby.html', valid_players=VALID_PLAYERS)

@app.route('/quiz')
def quiz():
    player_id = session.get('player_id')
    if not player_id or player_id not in VALID_PLAYERS:
        return redirect(url_for('index'))
    return render_template('quiz.html')

@app.route('/leaderboard')
def leaderboard():
    scores = game_state.get_final_scores()
    return render_template('leaderboard.html', scores=scores)

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/player-info')
def player_info():
    player_id = session.get('player_id')
    if not player_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    return jsonify({
        'player_id': player_id,
        'score': game_state.get_player_score(player_id)
    })


@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle incoming chat messages from players"""
    player_id = session.get('player_id')
    if not player_id or player_id not in VALID_PLAYERS:
        emit('error', {'message': 'Invalid player'})
        return
    
    message = data.get('message')
    if not message or not isinstance(message, str):
        return
    
    # Sanitize the message (basic)
    message = message.strip()
    if not message or len(message) > 500:  # Limit message length
        return
    
    # Broadcast the message to all players
    emit('chat_message', {
        'sender': player_id,
        'message': message,
        'timestamp': time.time()
    }, broadcast=True)

# New route to set player ID in session
@app.route('/set-player/<player_id>')
def set_player(player_id):
    if player_id in VALID_PLAYERS:
        session['player_id'] = player_id
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

# New route to check game status
@app.route('/api/game-status')
def game_status():
    return jsonify({
        'game_started': game_state.game_started,
        'current_question': game_state.current_question_index + 1 if game_state.game_started else 0
    })

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    
    # Check if there's a player_id in the session
    player_id = session.get('player_id')
    if player_id and player_id in VALID_PLAYERS:
        print(f"Reconnecting player {player_id} with socket {request.sid}")
        # Re-associate this socket with the player
        game_state.add_player(player_id, request.sid)
        join_room(player_id)
        
        # If game is already in progress, send current question to this player
        if game_state.game_started:
            send_question_to_player(player_id)

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    # Find and remove the player if they disconnect
    player_id = None
    for pid, sid in game_state.players.items():
        if sid == request.sid:
            player_id = pid
            break
    
    if player_id:
        print(f"Player {player_id} disconnected")
        game_state.remove_player(player_id)
        emit('player_left', {
            'player_id': player_id,
            'players': list(game_state.players.keys())
        }, broadcast=True)

@socketio.on('admin_connect')
def handle_admin_connect():
    # Send current game state to admin
    emit('player_joined', {
        'players': list(game_state.players.keys())
    })
    
    if game_state.game_started:
        current_q = game_state.get_current_question()
        if current_q:
            emit('new_question', {
                'question_number': game_state.current_question_index + 1,
                'question': current_q['question'],
                'total_questions': len(questions)
            })

@socketio.on('join_game')
def handle_join(data):
    player_id = data.get('player_id')
    
    # Validate player ID
    if player_id not in VALID_PLAYERS:
        emit('join_error', {'message': 'Invalid player ID or excluded player type'})
        return
    
    # Check if player already joined
    if player_id in game_state.players:
        emit('join_error', {'message': 'This player ID is already in use'})
        return
    
    # Add player to game state
    game_state.add_player(player_id, request.sid)
    session['player_id'] = player_id
    print(f"Player {player_id} joined with socket {request.sid}")
    
    # Join a room with the player's ID for direct messaging
    join_room(player_id)
    
    # Notify all clients about the new player
    emit('player_joined', {
        'player_id': player_id,
        'players': list(game_state.players.keys())
    }, broadcast=True)
    
    # Check if all expected players have joined
    if len(game_state.players) == len(VALID_PLAYERS):
        emit('all_players_ready', broadcast=True)
    
    # If game is already in progress, send current question to this player
    if game_state.game_started:
        send_question_to_player(player_id)

@socketio.on('start_game')
def handle_start_game(data):
    # Check if game already started
    if game_state.game_started:
        emit('game_already_started', broadcast=True)
        return
    
    # Check if request is from admin (with admin key)
    admin_key = data.get('admin_key')
    if admin_key and admin_key != ADMIN_KEY:
        emit('error', {'message': 'Invalid admin key'})
        return
    
    # Regular start requires at least 2 players to make it competitive
    if len(game_state.players) < 2 and not admin_key:
        emit('error', {'message': 'Need at least 2 players to start'})
        return
    
    # Start the game
    game_state.start_game()
    print(f"Game started by {request.sid}")
    
    # Explicitly notify all clients that game is starting
    emit('game_starting', {'message': 'Game is starting!'}, broadcast=True)
    
    # Send the first question
    send_next_question()

@socketio.on('submit_answer')
def handle_answer(data):
    player_id = session.get('player_id')
    if not player_id or player_id not in VALID_PLAYERS:
        emit('error', {'message': 'Invalid player'})
        return
    
    answer = data.get('answer')
    if not answer:
        return
    
    # Check if game is in progress
    if not game_state.game_started:
        emit('error', {'message': 'Game not started'})
        return
    
    # Check if question is still active
    if game_state.current_winner is not None or game_state.is_answering_locked():
        emit('too_late', {'message': 'Someone already answered correctly!'})
        return
    
    current_q = game_state.get_current_question()
    if current_q is None:
        emit('error', {'message': 'No active question'})
        return
    
    # Lock answering to prevent race conditions
    game_state.lock_answering()
    
    correct_answer = current_q['correct_answer']
    
    # Normalize answers for comparison (lowercase and strip)
    submitted_answer = str(answer).strip().lower()
    expected_answer = str(correct_answer).strip().lower()
    
    if submitted_answer == expected_answer:
        # Correct answer
        game_state.record_correct_answer(player_id)
        game_state.update_score(player_id, 1)
        
        emit('correct_answer', {
            'player_id': player_id,
            'correct_answer': correct_answer
        }, broadcast=True)
        
        # Admin notification
        emit('admin_correct_answer', {
            'player_id': player_id,
            'correct_answer': correct_answer,
            'time_taken': time.time() - game_state.question_timestamps[game_state.current_question_index]
        }, broadcast=True)
        
        # Wait a moment before moving to next question
        socketio.sleep(3)
        send_next_question()
    else:
        # Wrong answer, -2 points as requested
        game_state.update_score(player_id, -2)
        emit('wrong_answer', {
            'message': 'Wrong answer! -2 points',
            'correct_answer': None  # Don't reveal the correct answer yet
        })
        
        # Admin notification of wrong answer
        emit('admin_wrong_answer', {
            'player_id': player_id,
            'answer': answer,
            'correct_answer': correct_answer
        }, broadcast=True)
        
        # Unlock answering since this was wrong
        game_state.answering_locked = False

@socketio.on('admin_skip_question')
def admin_skip_question(data):
    if data.get('admin_key') == ADMIN_KEY:
        send_next_question()
        emit('admin_log', {'message': 'Admin skipped question'}, broadcast=True)

@socketio.on('admin_reset_game')
def admin_reset_game(data):
    if data.get('admin_key') == ADMIN_KEY:
        game_state.reset_game()
        emit('game_reset', broadcast=True)
        emit('admin_log', {'message': 'Admin reset the game'}, broadcast=True)

def send_question_to_player(player_id):
    """Send the current question to a specific player"""
    current_q = game_state.get_current_question()
    if current_q:
        socket_id = game_state.get_player_socket_id(player_id)
        if socket_id:
            question_data = {
                'question_number': game_state.current_question_index + 1,
                'question': current_q['question'],
                'options': current_q.get('options', []),
                'total_questions': len(questions)
            }
            print(f"Sending current question #{game_state.current_question_index + 1} to {player_id}")
            emit('new_question', question_data, room=player_id)

def send_next_question():
    """Send the next question to all players"""
    has_next = game_state.move_to_next_question()
    
    if has_next:
        current_q = game_state.get_current_question()
        if current_q:
            # Log which players are receiving questions
            print(f"Sending question #{game_state.current_question_index + 1} to {len(game_state.players)} players")
            for player_id in game_state.players.keys():
                print(f"  - {player_id} (socket: {game_state.players[player_id]})")
            
            # Send just the question and options, not the answer
            question_data = {
                'question_number': game_state.current_question_index + 1,
                'question': current_q['question'],
                'options': current_q.get('options', []),
                'total_questions': len(questions)
            }
            
            # Also send to admin with more details
            admin_question_data = question_data.copy()
            admin_question_data['correct_answer'] = current_q['correct_answer']
            
            emit('new_question', question_data, broadcast=True)
            emit('admin_new_question', admin_question_data, broadcast=True)
    else:
        # End of game
        final_scores = game_state.get_final_scores()
        emit('game_over', {'scores': final_scores}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)