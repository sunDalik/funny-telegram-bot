import random

class Wall:
    def __init__(self):
        self.tiles = [
            '🀇', '🀈', '🀉', '🀊', '🀋', '🀌', '🀍', '🀎', '🀏',  # Man (characters)
            '🀙', '🀚', '🀛', '🀜', '🀝', '🀞', '🀟', '🀠', '🀡',  # Pin (circles)
            '🀐', '🀑', '🀒', '🀓', '🀔', '🀕', '🀖', '🀗', '🀘',  # Sou (bamboo)
            '🀀', '🀁', '🀂', '🀃', '🀆', '🀅', '🀄'  # Honor tiles
        ] * 4
        self.dead_wall = []
        self.shuffle()
    
    def shuffle(self):
        random.shuffle(self.tiles)
        self.dead_wall = [self.tiles.pop() for _ in range(14)]
    
    def draw_tiles(self, count):
        return [self.tiles.pop() for _ in range(count)]
    
    def draw_dora_indicators(self):
        return self.dead_wall[:3]
    
    def reveal_new_dora(self):
        if len(self.dead_wall) > 3:
            new_dora = self.dead_wall.pop(3)
            self.dead_wall.insert(0, new_dora)
            return new_dora
        return None

    def remaining_tiles(self):
        return len(self.tiles)

    def kan_called(self):
        if self.remaining_tiles() > 0:
            self.dead_wall.append(self.tiles.pop())
