# AI Poker Assistant

A personal project leveraging computer vision and reinforcement learning to analyze real-time poker gameplay and support strategic decision-making on ClubGG.

## Features

### Real-Time Screen Reading
Captures live game data—including cards, player actions, positions, and pot size—using **EasyOCR** and **OpenCV**. Configurable regions allow adaptation to different table layouts and screen resolutions.

### Reinforcement Learning Agent
Implements a **Q-Learning agent** with epsilon-greedy exploration, experience replay, and adaptive learning rates to optimize strategy through self-play.

### Multi-Threaded GUI Overlay
Built with **Tkinter** to deliver real-time recommendations while monitoring performance and ensuring responsive updates.

### Modular, Pixel-Based Detection
Designed for precision and flexibility, allowing the system to adapt to various screen setups and game environments.

## Tech Stack

- **Languages:** Python
- **Libraries/Frameworks:** EasyOCR, OpenCV, NumPy, Tkinter
- **Techniques:** Reinforcement Learning (Q-Learning), Machine Learning, Computer Vision

## Project Purpose

Developed as a personal tool to improve my poker skills in simulated ClubGG games with friends. **This project is strictly educational and recreational**; it does not involve real-money gambling or cheating.

config.py
Defines screen coordinates for OCR capture regions. Each constant specifies where to look on screen for specific game elements (pot size, cards, player bankrolls, positions, etc.) This can be alterned to any location on a screen I picked the top left.

main.py
Creates a transparent overlay window using tkinter that displays game state and recommendations in real-time. Manages threading to prevent UI blocking, monitors performance, and coordinates between the OCR, ML pipeline, and RL components.

ml_pipeline.py
Data cleaning and validation layer. Takes raw OCR outputand normalizes it into consistent format. Fixes common OCR errors, validates cards, cleans pot/bankroll values, standardizes position names, and filters out invalid data.

ocr.py
Captures screenshots of specific screen regions and uses EasyOCR to extract text/cards. Handles suit detection via color analysis(RGB). Tracks game state changes to detect when new hands start. Maintains player positions, actions, and bankrolls.

rl_poker_bot.py
The reinforcement learning uses Q-learning to make poker decisions (fold/call/raise). Evaluates hand strength by analyzing card ranks, suits, pairs, straights, flushes, and board texture threats. Learns from experience over time, storing state-action values in a Q-table. 

OCR reads → ML pipeline cleans → RL bot decides → Main app displays everything in an overlay window.
