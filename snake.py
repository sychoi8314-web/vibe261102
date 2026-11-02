"""간단한 뱀 게임 (tkinter 사용, 표준 라이브러리만 필요)

조작: 방향키 또는 WASD로 이동, 스페이스로 일시정지, R로 재시작
"""
import random
import tkinter as tk

CELL = 20          # 한 칸 크기(px)
COLS, ROWS = 30, 20
SPEED_START = 150  # ms, 작을수록 빠름
SPEED_MIN = 60

DIRS = {
    "Up": (0, -1), "w": (0, -1),
    "Down": (0, 1), "s": (0, 1),
    "Left": (-1, 0), "a": (-1, 0),
    "Right": (1, 0), "d": (1, 0),
}


class SnakeGame:
    def __init__(self, root):
        self.root = root
        root.title("Snake")
        root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=COLS * CELL, height=ROWS * CELL,
                                bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack()
        self.label = tk.Label(root, font=("Consolas", 12))
        self.label.pack(fill="x")
        root.bind("<Key>", self.on_key)
        self.best = 0
        self.reset()
        self.tick()

    def reset(self):
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.next_dir = (1, 0)
        self.score = 0
        self.speed = SPEED_START
        self.paused = False
        self.game_over = False
        self.place_food()
        self.draw()

    def place_food(self):
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in self.snake]
        self.food = random.choice(free) if free else None

    def on_key(self, event):
        key = event.keysym
        if key in ("r", "R"):
            self.reset()
        elif key == "space" and not self.game_over:
            self.paused = not self.paused
            self.draw()
        elif key in DIRS or key.lower() in DIRS:
            d = DIRS.get(key) or DIRS[key.lower()]
            # 반대 방향으로는 바로 돌 수 없음
            if (d[0] + self.direction[0], d[1] + self.direction[1]) != (0, 0):
                self.next_dir = d

    def step(self):
        self.direction = self.next_dir
        hx, hy = self.snake[0]
        new_head = (hx + self.direction[0], hy + self.direction[1])

        # 벽 또는 자기 몸과 충돌 (꼬리는 이번에 빠지므로 제외)
        body = self.snake[:-1] if new_head != self.food else self.snake
        if (not (0 <= new_head[0] < COLS and 0 <= new_head[1] < ROWS)
                or new_head in body):
            self.game_over = True
            self.best = max(self.best, self.score)
            return

        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 1
            self.speed = max(SPEED_MIN, self.speed - 3)
            self.place_food()
            if self.food is None:  # 판을 다 채움
                self.game_over = True
                self.best = max(self.best, self.score)
        else:
            self.snake.pop()

    def draw(self):
        c = self.canvas
        c.delete("all")
        if self.food:
            fx, fy = self.food
            c.create_oval(fx * CELL + 3, fy * CELL + 3,
                          (fx + 1) * CELL - 3, (fy + 1) * CELL - 3,
                          fill="#e74c3c", outline="")
        for i, (x, y) in enumerate(self.snake):
            color = "#2ecc71" if i == 0 else "#27ae60"
            c.create_rectangle(x * CELL + 1, y * CELL + 1,
                               (x + 1) * CELL - 1, (y + 1) * CELL - 1,
                               fill=color, outline="")

        w, h = COLS * CELL, ROWS * CELL
        if self.game_over:
            c.create_text(w // 2, h // 2 - 15, text="GAME OVER",
                          fill="white", font=("Consolas", 28, "bold"))
            c.create_text(w // 2, h // 2 + 20, text="R 키로 다시 시작",
                          fill="#bbbbbb", font=("Consolas", 14))
        elif self.paused:
            c.create_text(w // 2, h // 2, text="일시정지",
                          fill="white", font=("Consolas", 24, "bold"))

        self.label.config(text=f"점수: {self.score}    최고: {self.best}")

    def tick(self):
        if not self.paused and not self.game_over:
            self.step()
        self.draw()
        self.root.after(self.speed, self.tick)


if __name__ == "__main__":
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()
