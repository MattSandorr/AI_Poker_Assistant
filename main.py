"""
Poker RL Assistant - Main Application

Provides an overlay window showing game state and RL bot recommendations
for online poker games. Uses OCR for game state extraction and reinforcement
learning for decision making.
"""
import tkinter as tk
import threading
import time
import json
import atexit
from collections import deque
from ocr import OCR, GameState
import ml_pipeline
from rl_poker_bot import PokerRLBot

#Config
UPDATE_INTERVAL_FAST = 500    # When cards are dealt
UPDATE_INTERVAL_NORMAL = 1000 # Normal gameplay
UPDATE_INTERVAL_SLOW = 2000   # Waiting for new hand

class PerformanceMonitor:
    def __init__(self):
        self.timings = deque(maxlen=50)
        self.bottleneck_threshold = 1.0  # sec
        
    def record_timing(self, operation, duration):
        self.timings.append((operation, duration, time.time()))
        if duration > self.bottleneck_threshold:
            print(f"BOTTLENECK: {operation} took {duration:.2f}s")
    
    def get_average_timing(self, operation):
        recent_timings = [t for t in self.timings if t[0] == operation and time.time() - t[2] < 30]
        if recent_timings:
            return sum(t[1] for t in recent_timings) / len(recent_timings)
        return 0

class PokerOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Poker RL Assistant")
        self.root.attributes('-topmost', True)
        self.root.geometry("380x300+50+50")
        self.root.configure(bg='black')
        self.root.wm_attributes("-alpha", 0.85)

        self.text = tk.StringVar()
        self.text.set("Initializing Optimized Poker RL Bot...")
        
        self.label = tk.Label(
            self.root,
            textvariable=self.text,
            fg='cyan',
            bg='black',
            font=("Consolas", 9),
            justify="left",
            wraplength=360
        )
        self.label.pack(padx=10, pady=10)

        # Thread management
        self.worker_running = False
        self.worker_lock = threading.Lock()
        self.consecutive_errors = 0
        
        self.perf_monitor = PerformanceMonitor()
        
        self.current_update_interval = UPDATE_INTERVAL_NORMAL
        
        # Initialize 
        self.game_state = GameState()
        self.ocr = OCR(self.game_state)
        
        print("Starting RL Bot...")
        self.rl_bot = PokerRLBot()
        
        # tracking the performence
        self.update_count = 0
        self.hands_seen = 0
        self.last_game_state = None
        
        atexit.register(self.cleanup)

        self.root.after(1000, self.update_overlay)

    def get_dynamic_interval(self):
        """Adjust update frequency based on game state"""
        if len(self.game_state.hero_cards) == 2:
            return UPDATE_INTERVAL_FAST
        elif self.game_state.pot != "N/A" and self.game_state.pot != "0":
            return UPDATE_INTERVAL_NORMAL
        else:
            return UPDATE_INTERVAL_SLOW

    def update_overlay(self):
        def worker():
            if not self.worker_lock.acquire(blocking=False):
                return              # Skip if another worker is running
            
            self.worker_running = True
            worker_start_time = time.time()
            
            try:
                ocr_start = time.time()
                json_state = self.ocr.refresh_all()
                ocr_duration = time.time() - ocr_start
                self.perf_monitor.record_timing("OCR", ocr_duration)
                
                current_state = {
                    'pot': self.game_state.pot,
                    'board': self.game_state.board,
                    'hero_cards': self.game_state.hero_cards,
                    'players': self.game_state.players
                }
                
                # Skip processing if state unchanged and no JSON update
                if not json_state and self.state_unchanged(current_state):
                    self.display_cached_state()
                    return
                
                # ML pipeline cleaning
                pipeline_start = time.time()
                current_json = json.dumps(current_state, ensure_ascii=False)
                cleaned_state = ml_pipeline.clean_game_state(current_json)
                pipeline_duration = time.time() - pipeline_start
                self.perf_monitor.record_timing("ML_Pipeline", pipeline_duration)

                if not cleaned_state:
                    self.text.set("Waiting for poker table...\n\nMake sure poker client is visible\nand you're seated at a table")
                    return

                hero_cards = cleaned_state.get('hero_cards', [])
                board = cleaned_state.get('board', [])
                pot = cleaned_state.get('pot', 'N/A')
                
                hero_info = cleaned_state.get('players', {}).get('Hero', {})
                position = hero_info.get('position', '--')
                bankroll = hero_info.get('bankroll', 'N/A')
                
                # Build the display overlay
                display = f"Pot: {pot}\n"
                display += f"Board: {', '.join(board) if board else 'None'}\n"
                display += f"Hero ({position}): {', '.join(hero_cards) if hero_cards else 'None'}\n"
                display += f"Stack: {bankroll}\n\n"
                
                # Get RL recommendation with timing
                if len(hero_cards) == 2:
                    rl_start = time.time()
                    decision = self.rl_bot.solve(cleaned_state)
                    rl_duration = time.time() - rl_start
                    self.perf_monitor.record_timing("RL_Bot", rl_duration)

                    action = decision.get('best_action', 'CALL')
                    confidence = decision.get('confidence', 0.5)
                    hand_strength = decision.get('hand_strength', 0.0)
                    states_learned = decision.get('states_learned', 0)
                    
                    # Action display
                    action_emoji = {
                        'RAISE': '🚀', 'FOLD': '🛑', 'CALL': '✅', 'WAIT': '⏳'
                    }
                    
                    display += f"{action_emoji.get(action, '❓')} Recommendation: {action}\n"
                    display += f"Confidence: {confidence:.1%}\n"
                    display += f"Hand Strength: {hand_strength:.1%}\n\n"
                    display += f"Learning Progress:\n"
                    display += f"States: {states_learned}\n"
                    display += f"Hands: {self.rl_bot.total_hands_played}"
                    
                    # Count hands 
                    if json_state:
                        self.hands_seen += 1
                
                else:
                    display += "Waiting for cards...\n\n"
                    display += "Bot Learning Status:\n"
                    display += f"States Learned: {len(self.rl_bot.q_table)}\n"
                    display += f"Total Hands: {self.rl_bot.total_hands_played}\n"
                    
                    # Show active players
                    try:
                        active_players = len([
                            p for p in cleaned_state.get('players', {}).values() 
                            if p.get('bankroll', 'N/A') != 'N/A'
                        ])
                        display += f"Players: {active_players}"
                    except:
                        display += "Players: --"

                self.update_count += 1
                total_time = time.time() - worker_start_time
                
                if self.update_count % 10 == 0 or total_time > 2.0:
                    ocr_avg = self.perf_monitor.get_average_timing("OCR")
                    display += f"\n\nPerf: Total {total_time:.1f}s"
                    if ocr_avg > 1.0:
                        display += f", OCR avg: {ocr_avg:.1f}s"
                
                self.text.set(display)
                self.last_game_state = current_state.copy()
                
                self.consecutive_errors = 0
                
                self.current_update_interval = self.get_dynamic_interval()
                
            except Exception as e:
                self.handle_error(e)
                
            finally:
                self.worker_running = False
                self.worker_lock.release()

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            print(f"Failed to start worker thread: {e}")
        
        self.root.after(self.current_update_interval, self.update_overlay)

    def state_unchanged(self, current_state):
        """Check if game state has changed significantly"""
        if not self.last_game_state:
            return False
            
        key_fields = ['pot', 'board', 'hero_cards']
        for field in key_fields:
            if current_state.get(field) != self.last_game_state.get(field):
                return False
        return True

    def display_cached_state(self):
        """Show cached info when state hasn't changed"""
        if hasattr(self, '_cached_display'):
            self.text.set(self._cached_display + f"\n\n[Cached - no changes detected]")

    def handle_error(self, error):
        """Enhanced error handling with recovery"""
        self.consecutive_errors += 1
        
        error_msg = f"Error: {str(error)[:50]}...\n\n"
        
        if hasattr(self, 'rl_bot') and hasattr(self.rl_bot, 'q_table'):
            error_msg += f"Learning: {len(self.rl_bot.q_table)} states\n"
            error_msg += f"Hands: {getattr(self.rl_bot, 'total_hands_played', 0)}\n\n"
        
        if self.consecutive_errors < 3:
            error_msg += "Retrying..."
        elif self.consecutive_errors < 10:
            error_msg += "Multiple errors - slowing down"
            self.current_update_interval = min(self.current_update_interval * 1.5, 5000)
        else:
            error_msg += "Many errors - check setup"
            self.current_update_interval = 5000  
        
        self.text.set(error_msg)
        
        print(f"Worker error (#{self.consecutive_errors}): {error}")
        if self.consecutive_errors <= 2: 
            import traceback
            traceback.print_exc()

    def cleanup(self):
        """Save RL progress when closing"""
        if hasattr(self, 'rl_bot'):
            print("Saving RL progress...")
            try:
                self.rl_bot.end_session()
                print(f"Final stats: {len(self.rl_bot.q_table)} states, {self.rl_bot.total_hands_played} hands")
            except Exception as e:
                print(f"Error saving RL progress: {e}")

    def run(self):
        print("Starting Optimized Poker RL Assistant...")
        print("Performance improvements:")
        print("- Thread synchronization")
        print("- Dynamic update intervals") 
        print("- OCR optimization")
        print("- Smart state caching")
        print("\nMake sure your poker client is visible")
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("Bot stopped by user")
        finally:
            self.cleanup()


def check_basic_dependencies():
    """Check basic requirements only"""
    try:
        import numpy
        import cv2
        import easyocr
        print("Dependencies OK")
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Install with: pip install numpy opencv-python easyocr")
        return False

if __name__ == "__main__":
    print("Optimized Poker RL Bot Starting...")
    
    if not check_basic_dependencies():
        input("Press Enter to exit...")
        exit(1)
    
    try:
        overlay = PokerOverlay()
        overlay.run()
    except KeyboardInterrupt:
        print("\nPoker RL Bot stopped")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
