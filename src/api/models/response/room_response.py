from dataclasses import dataclass
from typing import Optional


@dataclass
class RoomInfoResponse:
    room_id: int = None
    room_name: str = None
    phone_url: str = None
    permission: str = None
    owner: Optional[int] = None
    owner_name: Optional[str] = None
    current_user: int = None
    current_user_name: str = None
    create_time: str = None
    end_time: str | None = None
    specific_solder: Optional[str] = None
    duration: int = 0
    fish_server: str | None = None


@dataclass()
class CreateRoomResponse:
    room_id: int
    room_name: str
    phone_id: str

@dataclass
class UpdateRoomWhiteListResponse:
    room_id: int
    white_list: list

@dataclass
class UpdateRoomPermissionResponse:
    room_id: int
    permission:str

@dataclass
class UpdateRoomCurrentUserResponse:
    room_id: int | None
    current_user: int | None
    current_user_name: str | None
    owner: int | None
    owner_name: str | None
    mode: str | None
    phone_url: str | None
    duration: int = 6