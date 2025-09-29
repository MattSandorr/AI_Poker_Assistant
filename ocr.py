import os, time, cv2, numpy as np, easyocr
from PIL import ImageGrab
from typing import Dict, List, Optional
from config import *
import json 

SCAN_DELAY = 0.15  

class GameState:
    def __init__(self):
        self.pot = "N/A"
        self.board = []
        self.hero_cards = []
        self.players = {}

    def update_pot(self, v): self.pot = v
    def update_board(self, v): self.board = v
    def update_hero_cards(self, v): self.hero_cards = v
    def update_players(self, bankrolls, vpips, positions, actions, bets):
        self.players = {}
        for name in bankrolls.keys():
            self.players[name] = {
                "bankroll": bankrolls.get(name, "N/A"),
                "vpip": vpips.get(name, "--"),
                "position": positions.get(name, "--"),
                "action": actions.get(name, "--"),
                "bet": bets.get(name, "N/A"),
            }

    def to_json(self) -> str:
        state = {
            "pot": self.pot,
            "board": self.board,
            "hero_cards": self.hero_cards,
            "players": self.players,
        }
        return json.dumps(state, indent=2, ensure_ascii=False)

class OCR:
    def __init__(self, game_state: GameState):
        self.state = game_state
        
        print("Initializing OCR reader...")
        self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        print("OCR reader ready")

        self.seated_players: List[str] = []
        self.bankrolls: Dict[str, str] = {}
        self.vpips: Dict[str, str] = {}
        self.positions: Dict[str, str] = {}
        self.actions: Dict[str, str] = {}
        self.bets: Dict[str, str] = {}

        self.prev_hash: str = ""
        self.folded_players: set = set()
        self.last_street_count: int = 0
        
        self.last_hero_cards = []
        self.last_board = []
        self.hand_just_ended = False

    def _grab(self, region, color=False):
        """Keep original grab method but with slight performance improvement"""
        img = np.array(ImageGrab.grab(bbox=region))
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        if not color:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.resize(img, (0, 0), fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)

    def _text(self, region, color=False):
        """Keep original text method"""
        return self.reader.readtext(self._grab(region, color), detail=0)

    def _first(self, region):
        """Keep original _first method"""
        txt = self._text(region)
        return txt[0] if txt else "N/A"

    def _pot(self):
        """Keep original pot detection"""
        raw = self._text(POT_REGION)
        for t in raw:
            for part in t.replace(",", "").split():
                try:
                    float(part)
                    return part
                except ValueError:
                    pass
        return "N/A"

    def _suit(self, region):
        """Keep ORIGINAL working suit detection - don't change this"""
        rgb = np.mean(self._grab(region, color=True).reshape(-1, 3), axis=0)
        suit_rgb = {'♣': (27, 108, 27), '♥': (21, 82, 145), '♦': (162, 32, 33), '♠': (41, 43, 41)}
        dist = lambda a, b: np.sqrt(((np.array(a) - b) ** 2).sum())
        return min(suit_rgb, key=lambda s: dist(rgb, suit_rgb[s]))

    def _smart_card_correction(self, text_raw):
        """NEW: Conservative OCR correction for card values only"""
        if not text_raw:
            return None
            
        text = text_raw.strip().upper()
        
        valid_cards = ['A', 'K', 'Q', 'J', '10', '2', '3', '4', '5', '6', '7', '8', '9']
        if text in valid_cards:
            return text
        
        corrections = {
            '0': 'Q',      # Zero often misread as Q
            'O': 'Q',      # Letter O misread as Q  
        }
        
        if text in corrections:
            return corrections[text]
            
        # various ways OCR might see 10
        if text in ['10', 'TO', '1O', 'IO', 'LO']:
            return '10'
            
        if text.isdigit() and len(text) == 1:
            digit = int(text)
            if 2 <= digit <= 9:
                return text
                
        return None

    def _hero_cards(self):
        """UPDATED: Hero card detection with smart correction"""
        def card(region, suit_reg):
            card_texts = self._text(region)
            for raw_text in card_texts:
                corrected_value = self._smart_card_correction(raw_text)
                if corrected_value:
                    suit = self._suit(suit_reg)
                    return f"{corrected_value}{suit}"
            return None
        
        c1 = card(HERO_CARD_1, SUIT_HERO_1)
        c2 = card(HERO_CARD_2, SUIT_HERO_2)
        return [c for c in (c1, c2) if c]

    def _board(self):
        """UPDATED: Board detection with smart correction"""
        cards = []
        boards = [BOARD_CARD_1, BOARD_CARD_2, BOARD_CARD_3, BOARD_CARD_4, BOARD_CARD_5]
        suits = [SUIT_CARD_1, SUIT_CARD_2, SUIT_CARD_3, SUIT_CARD_4, SUIT_CARD_5]
        
        for r, s in zip(boards, suits):
            card_texts = self._text(r)
            if card_texts:
                corrected_value = self._smart_card_correction(card_texts[0])
                if corrected_value:
                    suit = self._suit(s)
                    cards.append(f"{corrected_value}{suit}")
        return cards

    def _bankrolls(self):
        """Keep ORIGINAL bankroll detection logic"""
        regs = {
            "Hero": BANK_HERO, "Player 2": BANK_PLAYER_2, "Player 3": BANK_PLAYER_3,
            "Player 4": BANK_PLAYER_4, "Player 5": BANK_PLAYER_5,
            "Player 6": BANK_PLAYER_6, "Player 7": BANK_PLAYER_7
        }
        br = {p: self._first(r) for p, r in regs.items()}
        self.seated_players = [p for p, v in br.items() if v != "N/A"]
        return br

    def _vpips(self):
        """Keep ORIGINAL VPIP detection logic"""
        regs = {
            "Hero": VPIP_HERO, "Player 2": VPIP_PLAYER_2, "Player 3": VPIP_PLAYER_3,
            "Player 4": VPIP_PLAYER_4, "Player 5": VPIP_PLAYER_5,
            "Player 6": VPIP_PLAYER_6, "Player 7": VPIP_PLAYER_7
        }
        return {p: self._first(r) + "%" for p, r in regs.items() if p in self.seated_players}

    def _positions(self):
        """Keep ORIGINAL position detection logic"""
        btn_rgb = (99, 182, 231)
        regs = {
            "Hero": POSITION_HERO, "Player 2": POSITION_PLAYER_2, "Player 3": POSITION_PLAYER_3,
            "Player 4": POSITION_PLAYER_4, "Player 5": POSITION_PLAYER_5,
            "Player 6": POSITION_PLAYER_6, "Player 7": POSITION_PLAYER_7
        }
        dist = lambda a, b: np.sqrt(((np.array(a) - b) ** 2).sum())
        dists = {}
        for p in self.seated_players:
            try:
                avg = np.mean(self._grab(regs[p], color=True).reshape(-1, 3), axis=0)
                dists[p] = dist(avg, btn_rgb)
            except:
                dists[p] = float('inf')
        
        if not dists:
            return {p: "--" for p in self.seated_players}
            
        btn = min(dists, key=dists.get)
        try:
            order = self.seated_players[self.seated_players.index(btn):] + self.seated_players[:self.seated_players.index(btn)]
            labels = ["BTN", "SB", "BB", "UTG", "MP", "CO", "HJ"][:len(order)]
            return dict(zip(order, labels))
        except:
            return {p: "--" for p in self.seated_players}

    def _actions(self):
        """Keep ORIGINAL action detection logic"""
        regs = {
            "Hero": ACTION_HERO, "Player 2": ACTION_2, "Player 3": ACTION_3,
            "Player 4": ACTION_4, "Player 5": ACTION_5,
            "Player 6": ACTION_6, "Player 7": ACTION_7
        }
        acts = {}
        for p in self.seated_players:
            if p in regs:
                words = " ".join(self._text(regs[p])).lower()
                if "fold" in words:
                    self.folded_players.add(p)
                    acts[p] = "Fold"
                elif p in self.folded_players:
                    acts[p] = "Fold"
                elif "raise" in words:
                    acts[p] = "Raise"
                elif "call" in words:
                    acts[p] = "Call"
                else:
                    acts[p] = "--"
            else:
                acts[p] = "--"
        return acts

    def _bets(self):
        """Keep ORIGINAL bet detection logic"""
        regs = {
            "Hero": BET_AMOUNT_HERO, "Player 2": BET_AMOUNT_2, "Player 3": BET_AMOUNT_3,
            "Player 4": BET_AMOUNT_4, "Player 5": BET_AMOUNT_5,
            "Player 6": BET_AMOUNT_6, "Player 7": BET_AMOUNT_7
        }
        return {p: self._first(regs[p]) for p in self.seated_players}

    def refresh_all(self) -> Optional[str]:
        """Keep ORIGINAL refresh logic with hand reset detection"""
        pot = self._pot()
        board = self._board()
        hero = self._hero_cards()
        self.bankrolls = self._bankrolls()
        self.vpips = self._vpips()
        self.positions = self._positions()

        hand_reset = False
        
        # Scenario 1: hand ended adn cards disappeared
        if len(self.last_hero_cards) > 0 and len(hero) == 0:
            hand_reset = True
            print("Hand reset detected: Hero cards disappeared")
        
        # Scenario 2: Board reset 
        if len(self.last_board) > 0 and len(board) == 0:
            hand_reset = True
            print("Hand reset detected: Board cleared")
        
        # Scenario 3: New hero cards dealt 
        if len(hero) == 2 and len(self.last_hero_cards) == 2:
            if set(hero) != set(self.last_hero_cards):
                hand_reset = True
                print(f"Hand reset detected: New cards {hero} (was {self.last_hero_cards})")

        # Check for street change
        street = len(board)
        if street != self.last_street_count or hand_reset:
            self.actions = {p: "--" for p in self.seated_players}
            self.bets = {p: "N/A" for p in self.seated_players}
            if hand_reset:
                self.folded_players = set()  
            self.last_street_count = street
        else:
            self.actions = self._actions()
            self.bets = self._bets()

        snapshot = (pot, tuple(board), tuple(hero),
                    tuple(sorted(self.bankrolls.items())),
                    tuple(sorted(self.vpips.items())),
                    tuple(sorted(self.positions.items())),
                    tuple(sorted(self.actions.items())),
                    tuple(sorted(self.bets.items())))
        hash_ = str(snapshot)
        
        changed = hash_ != self.prev_hash or hand_reset
        json_state = None
        
        if changed:
            self.prev_hash = hash_
            self.state.update_pot(pot)
            self.state.update_board(board)
            self.state.update_hero_cards(hero)
            self.state.update_players(self.bankrolls, self.vpips, self.positions, self.actions, self.bets)
            json_state = self.state.to_json()
            
            try:
                with open("game_state.json", "w", encoding="utf-8") as f:
                    f.write(json_state)
            except Exception as e:
                print(f"Warning: Could not save game state: {e}")
            
            if hand_reset or len(hero) == 2 or len(board) != len(self.last_board):
                print("=== GAME STATE UPDATE ===")
                print(f"Pot: {pot}, Board: {board}, Hero: {hero}")
                if hand_reset:
                    print(">>> HAND RESET DETECTED <<<")
        
        self.last_hero_cards = hero.copy()
        self.last_board = board.copy()
        
        return json_state
    
    def _clr(self): 
        os.system("cls" if os.name == "nt" else "clear")

    def _row(self, *c, w=10): 
        return "  ".join(str(x).ljust(w) for x in c)

    def display(self, first=False):
        """Keep ORIGINAL display method"""
        self._clr()
        print(("INITIAL STATE" if first else "LIVE STATE").center(60, "="), "\n")
        print(f"Pot   : {self.state.pot}")
        print(f"Board : {', '.join(self.state.board) if self.state.board else 'N/A'}")
        print(f"Hero  : {', '.join(self.state.hero_cards) if self.state.hero_cards else 'N/A'}\n")
        
        if self.seated_players:
            print(self._row("Player", "Pos", "Bank", "VPIP", "Action", "Bet"))
            print(self._row("-" * 6, "-" * 3, "-" * 5, "-" * 4, "-" * 6, "-" * 3))
            for p in self.seated_players:
                print(self._row(
                    p,
                    self.positions.get(p, "--"),
                    self.bankrolls.get(p, "N/A"),
                    self.vpips.get(p, "--"),
                    self.actions.get(p, "--"),
                    self.bets.get(p, "--")
                ))

    def start(self):
        """Keep ORIGINAL start method"""
        print("OCR started – press q to quit")
        self.refresh_all()
        while True:
            json_state = self.refresh_all()
            if json_state:
                pass
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            time.sleep(SCAN_DELAY)

if __name__ == "__main__":
    print("Testing Complete Fixed OCR...")
    OCR(GameState()).start()
