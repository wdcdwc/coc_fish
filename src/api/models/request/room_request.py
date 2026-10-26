from dataclasses import dataclass

@dataclass
class CreateRoomRequest:
    room_name: str
    phone_id: str
    type: str
    permission: str
    duration: int #单位小时

    def is_valid(self):
        return (self.room_name and 0 < len(self.room_name) < 10 and self.type and self.permission
                and self.duration)