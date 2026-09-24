import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ReservationState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RESERVATION_STATE_UNSPECIFIED: _ClassVar[ReservationState]
    RESERVATION_STATE_HELD: _ClassVar[ReservationState]
    RESERVATION_STATE_COMMITTED: _ClassVar[ReservationState]
    RESERVATION_STATE_RELEASED: _ClassVar[ReservationState]
    RESERVATION_STATE_EXPIRED: _ClassVar[ReservationState]
RESERVATION_STATE_UNSPECIFIED: ReservationState
RESERVATION_STATE_HELD: ReservationState
RESERVATION_STATE_COMMITTED: ReservationState
RESERVATION_STATE_RELEASED: ReservationState
RESERVATION_STATE_EXPIRED: ReservationState

class StockItem(_message.Message):
    __slots__ = ("sku_id", "quantity")
    SKU_ID_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    sku_id: str
    quantity: int
    def __init__(self, sku_id: _Optional[str] = ..., quantity: _Optional[int] = ...) -> None: ...

class ReserveStockRequest(_message.Message):
    __slots__ = ("reservation_id", "order_id", "items", "ttl_seconds")
    RESERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    TTL_SECONDS_FIELD_NUMBER: _ClassVar[int]
    reservation_id: str
    order_id: str
    items: _containers.RepeatedCompositeFieldContainer[StockItem]
    ttl_seconds: int
    def __init__(self, reservation_id: _Optional[str] = ..., order_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[StockItem, _Mapping]]] = ..., ttl_seconds: _Optional[int] = ...) -> None: ...

class ReserveStockResponse(_message.Message):
    __slots__ = ("reservation_id", "state", "expires_at", "created")
    RESERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    CREATED_FIELD_NUMBER: _ClassVar[int]
    reservation_id: str
    state: ReservationState
    expires_at: _timestamp_pb2.Timestamp
    created: bool
    def __init__(self, reservation_id: _Optional[str] = ..., state: _Optional[_Union[ReservationState, str]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., created: _Optional[bool] = ...) -> None: ...

class CommitReservationRequest(_message.Message):
    __slots__ = ("reservation_id",)
    RESERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    reservation_id: str
    def __init__(self, reservation_id: _Optional[str] = ...) -> None: ...

class CommitReservationResponse(_message.Message):
    __slots__ = ("state",)
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: ReservationState
    def __init__(self, state: _Optional[_Union[ReservationState, str]] = ...) -> None: ...

class ReleaseReservationRequest(_message.Message):
    __slots__ = ("reservation_id", "reason")
    RESERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    reservation_id: str
    reason: str
    def __init__(self, reservation_id: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class ReleaseReservationResponse(_message.Message):
    __slots__ = ("state",)
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: ReservationState
    def __init__(self, state: _Optional[_Union[ReservationState, str]] = ...) -> None: ...

class GetStockRequest(_message.Message):
    __slots__ = ("sku_ids",)
    SKU_IDS_FIELD_NUMBER: _ClassVar[int]
    sku_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, sku_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class StockLevel(_message.Message):
    __slots__ = ("sku_id", "available", "reserved")
    SKU_ID_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    RESERVED_FIELD_NUMBER: _ClassVar[int]
    sku_id: str
    available: int
    reserved: int
    def __init__(self, sku_id: _Optional[str] = ..., available: _Optional[int] = ..., reserved: _Optional[int] = ...) -> None: ...

class GetStockResponse(_message.Message):
    __slots__ = ("levels",)
    LEVELS_FIELD_NUMBER: _ClassVar[int]
    levels: _containers.RepeatedCompositeFieldContainer[StockLevel]
    def __init__(self, levels: _Optional[_Iterable[_Union[StockLevel, _Mapping]]] = ...) -> None: ...

class SetStockRequest(_message.Message):
    __slots__ = ("sku_id", "quantity")
    SKU_ID_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    sku_id: str
    quantity: int
    def __init__(self, sku_id: _Optional[str] = ..., quantity: _Optional[int] = ...) -> None: ...

class SetStockResponse(_message.Message):
    __slots__ = ("level",)
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    level: StockLevel
    def __init__(self, level: _Optional[_Union[StockLevel, _Mapping]] = ...) -> None: ...
