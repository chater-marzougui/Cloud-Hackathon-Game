from collections import defaultdict
import time

class GameState:
    def __init__(self, questions):
        self.questions = questions
        self.reset_game()
    
    def reset_game(self):
        """Reset the game state to initial values"""
        self.players = {}  # player_id -> socket_id
        self.scores = defaultdict(int)  # player_id -> score
        self.game_started = False
        self.current_question_index = -1
        self.current_winner = None
        self.question_timestamps = {}  # question_index -> timestamp
        self.question_winners = {}  # question_index -> player_id
        self.wrong_answers = defaultdict(int)  # player_id -> number of wrong answers
        self.answering_locked = False  # Lock to prevent race conditions in answer handling
    
    def add_player(self, player_id, socket_id):
        """Add a player to the game"""
        self.players[player_id] = socket_id
        self.scores[player_id] = 0
    
    def remove_player(self, player_id):
        """Remove a player from the game"""
        if player_id in self.players:
            del self.players[player_id]
    
    def start_game(self):
        """Start the game"""
        self.game_started = True
        self.current_question_index = -1
    
    def move_to_next_question(self):
        """Move to the next question"""
        self.current_question_index += 1
        self.current_winner = None
        self.answering_locked = False
        
        # Record timestamp for when the question was shown
        if self.current_question_index < len(self.questions):
            self.question_timestamps[self.current_question_index] = time.time()
            return True
        return False  # No more questions
    
    def get_current_question(self):
        """Get the current question data"""
        if 0 <= self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None
    
    def record_correct_answer(self, player_id):
        """Record a player as having answered correctly"""
        self.current_winner = player_id
        self.question_winners[self.current_question_index] = player_id
    
    def update_score(self, player_id, points):
        """Update a player's score"""
        self.scores[player_id] += points
        if points < 0:
            self.wrong_answers[player_id] += 1
    
    def get_player_score(self, player_id):
        """Get a player's current score"""
        return self.scores.get(player_id, 0)
    
    def is_game_over(self):
        """Check if the game is over (all questions answered)"""
        return self.current_question_index >= len(self.questions) - 1 and self.current_winner is not None
    
    def get_final_scores(self):
        """Get the final scores and statistics"""
        result = []
        for player_id, score in self.scores.items():
            correct_answers = sum(1 for winner in self.question_winners.values() if winner == player_id)
            player_data = {
                'player_id': player_id,
                'score': score,
                'correct_answers': correct_answers,
                'wrong_answers': self.wrong_answers[player_id],
                'class': player_id[:6]  # Extract class info (e.g., INDP2A from INDP2A1)
            }
            result.append(player_data)
        
        # Sort by score (descending)
        result.sort(key=lambda x: x['score'], reverse=True)
        
        # Add rank
        for i, player_data in enumerate(result):
            player_data['rank'] = i + 1
        
        return result
    
    def get_player_socket_id(self, player_id):
        """Get the socket ID for a player"""
        return self.players.get(player_id)

    def lock_answering(self):
        """Lock answering to prevent race conditions"""
        self.answering_locked = True
        
    def is_answering_locked(self):
        """Check if answering is locked"""
        return self.answering_locked