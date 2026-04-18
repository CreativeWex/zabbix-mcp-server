"""Pydantic v2 DTOs for Zabbix API request/response objects.

These models handle differences between Zabbix 6.0 and 7.0 where applicable.
"""

from pydantic import BaseModel, Field


class ZabbixHost(BaseModel):
    """Represents a Zabbix host object."""

    hostid: str
    host: str
    name: str = ""
    status: int = 0
    available: int = 0
    error: str = ""
    interfaces: list[dict[str, object]] = Field(default_factory=list)
    groups: list[dict[str, object]] = Field(default_factory=list)
    macros: list[dict[str, object]] = Field(default_factory=list)


class ZabbixProblem(BaseModel):
    """Represents a Zabbix problem/event object."""

    eventid: str
    objectid: str = ""
    name: str = ""
    severity: int = 0
    clock: int = 0
    acknowledged: int = 0
    hosts: list[dict[str, object]] = Field(default_factory=list)
    tags: list[dict[str, object]] = Field(default_factory=list)


class ZabbixItem(BaseModel):
    """Represents a Zabbix item (metric) object."""

    itemid: str
    name: str
    key_: str
    hostid: str
    value_type: int = 0
    units: str = ""
    lastvalue: str = ""
    lastclock: int = 0
    hosts: list[dict[str, object]] = Field(default_factory=list)


class ZabbixHistoryPoint(BaseModel):
    """Represents a single Zabbix history data point."""

    itemid: str
    clock: int
    value: str
    ns: int = 0


class ZabbixTrigger(BaseModel):
    """Represents a Zabbix trigger object."""

    triggerid: str
    description: str
    expression: str
    priority: int = 0
    status: int = 0
    state: int = 0
    lastchange: int = 0
    hosts: list[dict[str, object]] = Field(default_factory=list)


class ZabbixMaintenance(BaseModel):
    """Represents a Zabbix maintenance period object."""

    maintenanceid: str
    name: str
    active_since: int = 0
    active_till: int = 0
    hostids: list[str] = Field(default_factory=list)
    groupids: list[str] = Field(default_factory=list)


class ZabbixHostGroup(BaseModel):
    """Represents a Zabbix host group object."""

    groupid: str
    name: str


class ZabbixTemplate(BaseModel):
    """Represents a Zabbix template object."""

    templateid: str
    host: str
    name: str = ""


class ZabbixEvent(BaseModel):
    """Represents a Zabbix event object."""

    eventid: str
    objectid: str = ""
    value: int = 0  # 0=OK, 1=PROBLEM
    clock: int = 0
    name: str = ""
    severity: int = 0
    hosts: list[dict[str, object]] = Field(default_factory=list)


class ZabbixMacro(BaseModel):
    """Represents a Zabbix user macro object."""

    hostmacroid: str
    hostid: str
    macro: str
    value: str
    description: str = ""
