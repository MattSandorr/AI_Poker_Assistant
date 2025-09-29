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
