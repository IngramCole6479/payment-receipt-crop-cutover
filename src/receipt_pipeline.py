"""Application-shaped payment receipt workflow."""

from __future__ import annotations

import base64
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .infrai_client import InfraiClient


@dataclass(frozen=True)
class PaymentEvent:
    payment_id: str
    filename: str
    image_bytes: bytes
    amount: int
    risk_score: float


@dataclass(frozen=True)
class AuditNotification:
    payment_id: str
    decision: str
    variants: tuple[str, ...]
    audit_url: str


def risk_decision(score: float) -> str:
    return "review" if score >= 0.70 else "accepted"


def _data_uri(event: PaymentEvent) -> str:
    encoded = base64.b64encode(event.image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def process_receipt(event: PaymentEvent, client: InfraiClient, bucket: str = "payment-receipts") -> AuditNotification:
    client.ensure_bucket(bucket)
    uploaded = client.upload(_data_uri(event), event.filename)
    image_id = str(uploaded["data"]["id"])
    ratios = ("1:1", "4:5", "16:9")
    variants = tuple(f"{event.payment_id}-{ratio.replace(':', 'x')}" for ratio in ratios)
    for ratio in ratios:
        client.smart_crop(image_id, ratio)
    audit_key = f"audit/{event.payment_id}.json"
    signed = client.presign_get(bucket, audit_key)
    data = signed.get("data", {})
    url = str(data.get("url", "")) if isinstance(data, dict) else ""
    return AuditNotification(event.payment_id, risk_decision(event.risk_score), variants, url)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 -m src.receipt_pipeline IMAGE")
    image_path = Path(sys.argv[1])
    event = PaymentEvent("pay_demo_001", image_path.name, image_path.read_bytes(), 12500, 0.32)
    result = process_receipt(event, InfraiClient.from_environment())
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
