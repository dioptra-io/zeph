"""API drivers."""
from io import BytesIO
from uuid import uuid4

from httpx import HTTPStatusError
from iris_client import IrisClient

from zeph.typing import Network


def create_measurement(client: IrisClient, definition: dict) -> dict:
    res = client.post("/measurements", json=definition)
    try:
        res.raise_for_status()
    except HTTPStatusError as e:
        raise RuntimeError(res.content) from e
    return dict(res.json())  # make mypy happy...


def get_agents(client: IrisClient, tag: str) -> dict[str, dict]:
    agents = client.all("/agents", params=dict(tag=tag))
    return {agent["uuid"]: agent for agent in agents}


def get_measurement_agents(client: IrisClient, measurement_uuid: str) -> list[str]:
    measurement = client.get(f"/measurements/{measurement_uuid}").json()
    return [agent["agent_uuid"] for agent in measurement["agents"]]


def upload_prefix_list(
    client: IrisClient,
    prefixes: set[Network],
    protocol: str,
    min_ttl: int,
    max_ttl: int,
) -> str:
    key = f"zeph__{uuid4()}.csv"
    file = BytesIO(
        "\n".join(
            f"{prefix},{protocol},{min_ttl},{max_ttl},6" for prefix in prefixes
        ).encode()
    )
    res = client.post("/targets", files={"target_file": (key, file)})
    try:
        res.raise_for_status()
    except HTTPStatusError as e:
        raise RuntimeError(res.content) from e
    return key
