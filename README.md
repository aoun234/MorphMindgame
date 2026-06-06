# MorphMind AI v2.0 🎮
**Shape-Based Maze Escape — AI Agents + Machine Learning**

---

## 🚀 Setup (VS Code)
```bash
pip install -r requirements.txt
python main.py
```

---

## 🎮 Controls
| Key | Action |
|-----|--------|
| WASD / Arrows | Move |
| P | Pause |
| ESC | Back / Quit |
| R | Restart (on game over) |

---

## 🏆 How to Win
1. Collect all **yellow keys** (number depends on difficulty)
2. Reach the **cyan portal** — it opens when all keys are collected
3. Complete all **3 levels** to escape!

---

## ⚙️ Difficulty System
| Difficulty | Enemies | Speed | Damage | Keys |
|------------|---------|-------|--------|------|
| EASY | 2 | Slow | 8 | 2 |
| NORMAL | 3 | Medium | 12 | 3 |
| HARD | 4 | Fast | 18 | 4 |
| INSANE | 5 | Very fast | 25 | 5 |

---

## 🤖 AI & ML System
| Enemy Label | Color | Behaviour |
|-------------|-------|-----------|
| P | Red | **Patrol** — random waypoints |
| D | Orange | **Detect** — slow approach |
| C | Bright Red | **Chase** — A* pathfinding |
| ML | Purple | **Predict** — ML ambush intercept |

ML trains every ~5 seconds. Once active, purple enemies intercept your predicted position!

---

## ⚡ Powerups
| Icon | Effect |
|------|--------|
| ⚡ Speed | +60% speed for 5 seconds |
| 🛡 Shield | Blocks all damage for 5 seconds |
| ♥ Health | Restores 30 HP |

---

## 📁 File Structure
```
MorphMindAI/
├── main.py         ← App, menus, game loop, powerups, HUD
├── player.py       ← Movement, trail, particles, HUD
├── enemy.py        ← FSM + A* + ML, glow, detection ring
├── ai_system.py    ← A* pathfinding algorithm
├── ml_model.py     ← Logistic Regression predictor
├── map.py          ← 3-level maze rendering
├── settings.py     ← Constants, palette, difficulty, level data
└── requirements.txt
```