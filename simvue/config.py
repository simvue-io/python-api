from dataclasses import dataclass

@dataclass
class HeartbeatConfig:
    sleep: int = 1
    interval: int = 60
