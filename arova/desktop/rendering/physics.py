import math

class Spring:
    """
    Damped harmonic oscillator for fluid UI transitions.
    """
    def __init__(self, value: float = 0.0, target: float = 0.0, stiffness: float = 150.0, damping: float = 15.0):
        self.value = value
        self.target = target
        self.velocity = 0.0
        self.stiffness = stiffness
        self.damping = damping
        
    def update(self, dt: float) -> bool:
        """Returns True if the spring is still moving (not at rest)."""
        force = -self.stiffness * (self.value - self.target)
        self.velocity += force * dt
        self.velocity *= (1.0 - min(self.damping * dt, 1.0))
        self.value += self.velocity * dt
        
        # At rest check
        if abs(self.velocity) < 0.001 and abs(self.target - self.value) < 0.001:
            self.value = self.target
            self.velocity = 0.0
            return False
        return True

def interpolate_color(c1: tuple, c2: tuple, progress: float) -> tuple:
    """Interpolates RGBA tuples."""
    return tuple(c1[i] + (c2[i] - c1[i]) * progress for i in range(4))
