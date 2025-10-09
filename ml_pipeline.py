import json
import re
from typing import Dict, List, Optional, Union

VALID_CARD_PATTERN = re.compile(r'^(A|K|Q|J|10|[2-9])[♠♥♦♣]$')
VALID_POSITION_PATTERN = re.compile(r'^(BTN|SB|BB|UTG|MP|CO|HJ)$')

def clean_game_state(json_state: str) -> Optional[Dict]:
    """
    Enhanced game state cleaning with robust validation and error recovery
    """
    if not json_state or json_state.strip() == "":
        return None
        
    try:
        data = json.loads(json_state)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return None
    
    if not isinstance(data, dict):
        print("Invalid data format: expected dictionary")
        return None

    cleaned_state = {
        'pot': clean_pot_value(data.get('pot')),
        'board': clean_card_list(data.get('board', [])),
        'hero_cards': clean_card_list(data.get('hero_cards', [])),
        'players': clean_players_data(data.get('players', {}))
    }
    
    if not validate_game_state(cleaned_state):
        return None
    
    return cleaned_state

def clean_pot_value(pot_value) -> Union[float, str]:
    """Clean and validate pot value"""
    if pot_value is None or pot_value == "N/A":
        return 0.0
    
    if isinstance(pot_value, str):
        clean_pot = pot_value.replace('$', '').replace(',', '').replace(' ', '')
        
        if clean_pot == '' or clean_pot.upper() == 'N/A':
            return 0.0
            
        try:
            return float(clean_pot)
        except ValueError:
            numbers = re.findall(r'\d+\.?\d*', clean_pot)
            if numbers:
                try:
                    return float(numbers[0])
                except ValueError:
                    pass
    
    try:
        return float(pot_value)
    except (ValueError, TypeError):
        return 0.0

def clean_card_list(card_list) -> List[str]:
    """Clean and validate a list of cards"""
    if not isinstance(card_list, list):
        return []
    
    cleaned_cards = []
    for card in card_list:
        cleaned_card = clean_single_card(card)
        if cleaned_card:
            cleaned_cards.append(cleaned_card)
    
    return cleaned_cards

def clean_single_card(card) -> Optional[str]:
    """Clean and validate a single card"""
    if not isinstance(card, str):
        return None
    
    card = card.strip()
    
    if not card or len(card) < 2:
        return None
    
    card = normalize_card_format(card)
    
    if VALID_CARD_PATTERN.match(card):
        return card
    
    repaired_card = repair_card_ocr_errors(card)
    if repaired_card and VALID_CARD_PATTERN.match(repaired_card):
        return repaired_card
    
    return None

def normalize_card_format(card: str) -> str:
    """Normalize card to standard format"""
    card = card.upper().strip()
    
    if card.startswith('10'):
        return '10' + card[2:]
    elif card.startswith('T'):
        return '10' + card[1:]
    
    # Ensure proper suit symbols
    suit_replacements = {
        'S': '♠', 'SPADES': '♠', 'SPADE': '♠',
        'H': '♥', 'HEARTS': '♥', 'HEART': '♥',
        'D': '♦', 'DIAMONDS': '♦', 'DIAMOND': '♦',
        'C': '♣', 'CLUBS': '♣', 'CLUB': '♣'
    }
    
    for text_suit, symbol in suit_replacements.items():
        if card.endswith(text_suit):
            return card[:-len(text_suit)] + symbol
    
    return card

def repair_card_ocr_errors(card: str) -> Optional[str]:
    """Attempt to repair common OCR errors in card reading"""
    if len(card) < 2:
        return None
    
    value_corrections = {
        '0': 'Q',    # 0 often mistaken for Q
        'O': 'Q',    # O often mistaken for Q
        'I': '1',    # I often mistaken for 1 
        'L': '1',    # L often mistaken for 1
        'S': '5',    # S often mistaken for 5
        'B': '8',    # B often mistaken for 8
        'G': '6',    # G often mistaken for 6
    }
    
    if len(card) >= 2:
        value_part = card[:-1]
        suit_part = card[-1]
        
        if value_part in value_corrections:
            corrected_value = value_corrections[value_part]
        else:
            corrected_value = value_part
        
        corrected_card = corrected_value + suit_part
        return normalize_card_format(corrected_card)
    
    return None

def clean_players_data(players_data) -> Dict:
    """Clean and validate player data"""
    if not isinstance(players_data, dict):
        return {}
    
    cleaned_players = {}
    
    for player_name, player_info in players_data.items():
        if not isinstance(player_info, dict):
            continue
        
        # Skip players with no data
        bankroll = player_info.get('bankroll', 'N/A')
        if bankroll == 'N/A' or not bankroll:
            continue
        
        cleaned_player = {
            'bankroll': clean_bankroll_value(bankroll),
            'vpip': clean_vpip_value(player_info.get('vpip', '--')),
            'position': clean_position_value(player_info.get('position', '--')),
            'action': clean_action_value(player_info.get('action', '--')),
            'bet': clean_bet_value(player_info.get('bet', 'N/A'))
        }
        
        # Only include players with bankroll
        if cleaned_player['bankroll'] != 'N/A':
            cleaned_players[str(player_name)] = cleaned_player
    
    return cleaned_players

def clean_bankroll_value(bankroll) -> Union[str, float]:
    """Clean bankroll value"""
    if bankroll is None or str(bankroll).strip() == '':
        return 'N/A'
    
    bankroll_str = str(bankroll).replace('$', '').replace(',', '').strip()
    
    if bankroll_str.upper() == 'N/A' or bankroll_str == '':
        return 'N/A'
    
    try:
        float(bankroll_str)
        return bankroll_str
    except ValueError:
        numbers = re.findall(r'\d+\.?\d*', bankroll_str)
        if numbers:
            return numbers[0]
        return 'N/A'

def clean_vpip_value(vpip) -> str:
    """Clean VPIP percentage value"""
    if vpip is None:
        return '--'
    
    vpip_str = str(vpip).strip()
    
    if vpip_str in ['--', 'N/A', '']:
        return '--'
    
    if not vpip_str.endswith('%') and vpip_str != '--':
        try:
            float(vpip_str)
            return vpip_str + '%'
        except ValueError:
            return '--'
    
    if vpip_str.endswith('%'):
        try:
            percentage = float(vpip_str[:-1])
            if 0 <= percentage <= 100:
                return vpip_str
        except ValueError:
            pass
    
    return '--'

def clean_position_value(position) -> str:
    """Clean and validate position"""
    if position is None:
        return '--'
    
    position_str = str(position).strip().upper()
    
    if position_str in ['--', 'N/A', '']:
        return '--'
    
    if VALID_POSITION_PATTERN.match(position_str):
        return position_str
    
    position_corrections = {
        'BUTTON': 'BTN',
        'BU': 'BTN',
        'SMALL': 'SB',
        'SMALL_BLIND': 'SB',
        'BIG': 'BB',
        'BIG_BLIND': 'BB',
        'UNDER_THE_GUN': 'UTG',
        'MIDDLE': 'MP',
        'CUTOFF': 'CO',
        'HIJACK': 'HJ'
    }
    
    return position_corrections.get(position_str, '--')

def clean_action_value(action) -> str:
    """Clean and validate player action"""
    if action is None:
        return '--'
    
    action_str = str(action).strip().lower()
    
    if action_str in ['--', 'n/a', '']:
        return '--'
    
    # Standardize actions
    if any(word in action_str for word in ['fold', 'folded']):
        return 'Fold'
    elif any(word in action_str for word in ['raise', 'bet', 'all-in', 'allin']):
        return 'Raise'
    elif any(word in action_str for word in ['call', 'check']):
        return 'Call'
    else:
        return '--'

def clean_bet_value(bet) -> str:
    """Clean bet amount"""
    if bet is None:
        return 'N/A'
    
    bet_str = str(bet).replace('$', '').replace(',', '').strip()
    
    if bet_str.upper() in ['N/A', '--', '']:
        return 'N/A'
    
    try:
        float(bet_str)
        return bet_str
    except ValueError:
        numbers = re.findall(r'\d+\.?\d*', bet_str)
        if numbers:
            return numbers[0]
        return 'N/A'

def validate_game_state(state: Dict) -> bool:
    """Validate the cleaned game state"""
    if not isinstance(state, dict):
        return False
    
    required_fields = ['pot', 'board', 'hero_cards', 'players']
    if not all(field in state for field in required_fields):
        return False
    
    if not isinstance(state['pot'], (int, float)) or state['pot'] < 0:
        return False
    
    if not isinstance(state['board'], list) or len(state['board']) > 5:
        return False
    
    if not isinstance(state['hero_cards'], list) or len(state['hero_cards']) > 2:
        return False
    
    if not isinstance(state['players'], dict):
        return False
    
    return True

def get_game_state_summary(state: Dict) -> str:
    """Generate a summary of the game state for debugging"""
    if not state:
        return "Empty state"
    
    summary = []
    summary.append(f"Pot: {state.get('pot', 'N/A')}")
    
    board = state.get('board', [])
    summary.append(f"Board ({len(board)}): {', '.join(board) if board else 'Empty'}")
    
    hero_cards = state.get('hero_cards', [])
    summary.append(f"Hero ({len(hero_cards)}): {', '.join(hero_cards) if hero_cards else 'Empty'}")
    
    players = state.get('players', {})
    active_players = len([p for p in players.values() if p.get('bankroll') != 'N/A'])
    summary.append(f"Players: {active_players} active")
    
    return " | ".join(summary)

if __name__ == "__main__":
    test_json = '''
    {
        "pot": "25.50",
        "board": ["A♠", "K♣", "Q♦"],
        "hero_cards": ["10♥", "J♠"],
        "players": {
            "Hero": {
                "bankroll": "200.00",
                "vpip": "25%",
                "position": "BTN",
                "action": "Call",
                "bet": "5"
            },
            "Player 2": {
                "bankroll": "150",
                "vpip": "45%",
                "position": "SB",
                "action": "--",
                "bet": "N/A"
            }
        }
    }
    '''
    
    result = clean_game_state(test_json)
    if result:
        print(" success!")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"Summary: {get_game_state_summary(result)}")
    else:
        print(" failed")

