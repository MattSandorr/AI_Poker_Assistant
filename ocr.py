# ocr.py
# ---------------------------------------------------------------------------#
import os, time, cv2, numpy as np, easyocr
from PIL import ImageGrab
from typing import Dict, List
from config import *

SCAN_DELAY = 0.20  # seconds between scans

class GameState:
    def __init__(self):
        self.pot = "N/A"
        self.board = []
        self.hero_cards = []

    def update_pot(self, v): self.pot = v
    def update_board(self, v): self.board = v
    def update_hero_cards(self, v): self.hero_cards = v

class OCR:
    def __init__(self, game_state: GameState):
        self.state = game_state
        self.reader = easyocr.Reader(['en'])

        self.seated_players: List[str] = []
        self.bankrolls: Dict[str, str] = {}
        self.vpips: Dict[str, str] = {}
        self.positions: Dict[str, str] = {}
        self.actions: Dict[str, str] = {}
        self.bets: Dict[str, str] = {}

        self.prev_hash: str = ""
        self.folded_players: set = set()
        self.last_street_count: int = 0

    def _grab(self, region, color=False):
        img = np.array(ImageGrab.grab(bbox=region))
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        if not color:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.resize(img, (0, 0), fx=2, fy=2)

    def _text(self, region, color=False):
        return self.reader.readtext(self._grab(region, color), detail=0)

    def _first(self, region):
        txt = self._text(region)
        return txt[0] if txt else "N/A"

    def _pot(self):
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
        rgb = np.mean(self._grab(region, color=True).reshape(-1, 3), axis=0)
        suit_rgb = {'♣': (27, 108, 27), '♥': (21, 82, 145), '♦': (162, 32, 33), '♠': (41, 43, 41)}
        dist = lambda a, b: np.sqrt(((np.array(a) - b) ** 2).sum())
        return min(suit_rgb, key=lambda s: dist(rgb, suit_rgb[s]))

    def _hero_cards(self):
        def card(region, suit_reg):
            for t in self._text(region):
                t = 'Q' if t.strip() == '0' else t.strip()
                if t in list("AKQJ") + [str(n) for n in range(2, 11)]:
                    return f"{t}{self._suit(suit_reg)}"
            return None
        c1 = card(HERO_CARD_1, SUIT_HERO_1)
        c2 = card(HERO_CARD_2, SUIT_HERO_2)
        return [c for c in (c1, c2) if c]

    def _board(self):
        cards, boards, suits = [], \
            [BOARD_CARD_1, BOARD_CARD_2, BOARD_CARD_3, BOARD_CARD_4, BOARD_CARD_5], \
            [SUIT_CARD_1, SUIT_CARD_2, SUIT_CARD_3, SUIT_CARD_4, SUIT_CARD_5]
        for r, s in zip(boards, suits):
            card = self._text(r)
            if card:
                t = card[0].strip()
                t = 'Q' if t == '0' else t
                if t in list("AKQJ") + [str(n) for n in range(2, 11)]:
                    cards.append(f"{t}{self._suit(s)}")
        return cards

    def _bankrolls(self):
        regs = {
            "Hero": BANK_HERO, "Player 2": BANK_PLAYER_2, "Player 3": BANK_PLAYER_3,
            "Player 4": BANK_PLAYER_4, "Player 5": BANK_PLAYER_5,
            "Player 6": BANK_PLAYER_6, "Player 7": BANK_PLAYER_7
        }
        br = {p: self._first(r) for p, r in regs.items()}
        self.seated_players = [p for p, v in br.items() if v != "N/A"]
        return br

    def _vpips(self):
        regs = {
            "Hero": VPIP_HERO, "Player 2": VPIP_PLAYER_2, "Player 3": VPIP_PLAYER_3,
            "Player 4": VPIP_PLAYER_4, "Player 5": VPIP_PLAYER_5,
            "Player 6": VPIP_PLAYER_6, "Player 7": VPIP_PLAYER_7
        }
        return {p: self._first(r) + "%" for p, r in regs.items() if p in self.seated_players}

    def _positions(self):
        btn_rgb = (99, 182, 231)
        regs = {
            "Hero": POSITION_HERO, "Player 2": POSITION_PLAYER_2, "Player 3": POSITION_PLAYER_3,
            "Player 4": POSITION_PLAYER_4, "Player 5": POSITION_PLAYER_5,
            "Player 6": POSITION_PLAYER_6, "Player 7": POSITION_PLAYER_7
        }
        dist = lambda a, b: np.sqrt(((np.array(a) - b) ** 2).sum())
        dists = {}
        for p in self.seated_players:
            avg = np.mean(self._grab(regs[p], color=True).reshape(-1, 3), axis=0)
            dists[p] = dist(avg, btn_rgb)
        btn = min(dists, key=dists.get)
        order = self.seated_players[self.seated_players.index(btn):] + self.seated_players[:self.seated_players.index(btn)]
        labels = ["BTN", "SB", "BB", "UTG", "MP", "CO", "HJ"][:len(order)]
        return dict(zip(order, labels))

    def _actions(self):
        regs = {
            "Hero": ACTION_HERO, "Player 2": ACTION_2, "Player 3": ACTION_3,
            "Player 4": ACTION_4, "Player 5": ACTION_5,
            "Player 6": ACTION_6, "Player 7": ACTION_7
        }
        acts = {}
        for p in self.seated_players:
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
        return acts

    def _bets(self):
        regs = {
            "Hero": BET_AMOUNT_HERO, "Player 2": BET_AMOUNT_2, "Player 3": BET_AMOUNT_3,
            "Player 4": BET_AMOUNT_4, "Player 5": BET_AMOUNT_5,
            "Player 6": BET_AMOUNT_6, "Player 7": BET_AMOUNT_7
        }
        return {p: self._first(regs[p]) for p in self.seated_players}

    def refresh_all(self) -> bool:
        pot = self._pot()
        board = self._board()
        hero = self._hero_cards()
        self.bankrolls = self._bankrolls()
        self.vpips = self._vpips()
        self.positions = self._positions()

        # Check for street change
        street = len(board)
        if street != self.last_street_count:
            self.actions = {p: "--" for p in self.seated_players}
            self.bets = {p: "N/A" for p in self.seated_players}
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
        changed = hash_ != self.prev_hash
        if changed:
            self.prev_hash = hash_
            self.state.update_pot(pot)
            self.state.update_board(board)
            self.state.update_hero_cards(hero)
        return changed

    def _clr(self): os.system("cls" if os.name == "nt" else "clear")

    def _row(self, *c, w=10): return "  ".join(str(x).ljust(w) for x in c)

    def display(self, first=False):
        self._clr()
        print(("INITIAL STATE" if first else "LIVE STATE").center(60, "="), "\n")
        print(f"Pot   : {self.state.pot}")
        print(f"Board : {', '.join(self.state.board) if self.state.board else 'N/A'}")
        print(f"Hero  : {', '.join(self.state.hero_cards) if self.state.hero_cards else 'N/A'}\n")
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
        print("OCR started – press q to quit")
        self.refresh_all()
        self.display(first=True)
        while True:
            if self.refresh_all():
                self.display()
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            time.sleep(SCAN_DELAY)

if __name__ == "__main__":
    OCR(GameState()).start()
